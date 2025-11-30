import requests
from django.conf import settings
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from .serializers import UserSerializer, ProfileSerializer, UserPasswordSerializer
from .models import Stream, Ban, ChatMessage, Profile # Import Profile
from django.contrib.auth import update_session_auth_hash # For password change
from rest_framework import permissions, serializers # Added serializers import

class SignUpView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class LoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if user:
            token, _ = Token.objects.get_or_create(user=user)
            return Response({'token': token.key, 'username': user.username, 'nickname': user.profile.nickname})
        else:
            return Response({'error': 'Invalid Credentials'}, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        token = getattr(request.user, 'auth_token', None)
        if token:
            token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class StreamInfoView(APIView):
    def get(self, request, username):
        try:
            user = User.objects.get(username=username)
            stream = Stream.objects.get(user=user)
            return Response({
                'username': user.username,
                'nickname': user.profile.nickname if hasattr(user, 'profile') else None, # Include nickname
                'stream_key': stream.stream_key,
                'stream_url': stream.stream_url,
                'stream_uid': stream.viewer_url,
            })
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Stream.DoesNotExist:
            return Response({'error': 'Stream not found'}, status=status.HTTP_404_NOT_FOUND)

class UserListView(APIView):
    def get(self, request):
        live_streams_data = {}
        try:
            headers = {'Authorization': f'Bearer {settings.CLOUDFLARE_API_TOKEN}'}
            url = f"https://api.cloudflare.com/client/v4/accounts/{settings.CLOUDFLARE_ACCOUNT_ID}/stream/live_inputs"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            live_inputs = response.json().get('result', [])
            
            for inp in live_inputs:
                if inp.get('status') == 'live' and inp.get('uid'):
                    live_streams_data[inp['uid']] = inp.get('thumbnail')

        except requests.exceptions.RequestException as e:
            print(f"Could not fetch live status from Cloudflare: {e}")

        users = User.objects.select_related('stream', 'profile').all().order_by('username')
        response_data = []
        for user in users:
            is_live = False
            thumbnail = None
            if hasattr(user, 'stream') and user.stream and user.stream.viewer_url in live_streams_data:
                is_live = True
                thumbnail = live_streams_data[user.stream.viewer_url]
            
            response_data.append({
                'username': user.username,
                'nickname': user.profile.nickname, # Include nickname
                'is_live': is_live,
                'thumbnail': thumbnail,
            })
            
        return Response(response_data)

class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        serializer = ProfileSerializer(profile)
        return Response(serializer.data)

    def put(self, request):
        profile = request.user.profile
        serializer = ProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = UserPasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            if not user.check_password(serializer.validated_data.get('old_password')):
                return Response({'old_password': ['Wrong password.']}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.validated_data.get('new_password'))
            user.save()
            update_session_auth_hash(request, user)  # Important to keep user logged in
            return Response({'status': 'password set'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class IsStreamer(permissions.BasePermission):
    """
    Custom permission to only allow the streamer to view their banned list.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.username == view.kwargs.get('username')

class BannedUsersListView(generics.ListAPIView):
    permission_classes = [IsStreamer]

    def get_queryset(self):
        streamer_username = self.kwargs['username']
        streamer = User.objects.get(username=streamer_username)
        return Ban.objects.filter(streamer=streamer)

    def get_serializer(self, *args, **kwargs):
        class BannedUserSerializer(serializers.ModelSerializer):
            banned_username = serializers.CharField(source='banned_user.username')
            class Meta:
                model = Ban
                fields = ('banned_username',)
        
        return BannedUserSerializer(*args, **kwargs)

class BanView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        streamer = request.user
        banned_user_username = request.data.get('banned_user')
        
        if streamer.username == banned_user_username:
            return Response({'error': 'You cannot ban yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            banned_user = User.objects.get(username=banned_user_username)
            Ban.objects.get_or_create(streamer=streamer, banned_user=banned_user)
            return Response({'status': f'{banned_user_username} has been banned.'}, status=status.HTTP_201_CREATED)
        except User.DoesNotExist:
            return Response({'error': 'User to ban not found.'}, status=status.HTTP_404_NOT_FOUND)

class UnbanView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        streamer = request.user
        banned_user_username = request.data.get('banned_user')
        try:
            banned_user = User.objects.get(username=banned_user_username)
            ban_instance = Ban.objects.get(streamer=streamer, banned_user=banned_user)
            ban_instance.delete()
            return Response({'status': f'{banned_user_username} has been unbanned.'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'User to unban not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Ban.DoesNotExist:
            return Response({'error': 'Ban record not found.'}, status=status.HTTP_404_NOT_FOUND)
