from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Stream, Profile
import requests
from django.conf import settings
from django.db import transaction
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Profile
        fields = ('nickname', 'username')

class UserPasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False) # Nested serializer for profile

    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'profile')
        extra_kwargs = {'password': {'write_only': True}}

    @transaction.atomic
    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password']
        )
        profile = getattr(user, 'profile', None)
        nickname = profile_data.get('nickname', user.username)
        if profile:
            profile.nickname = nickname
            profile.save(update_fields=['nickname'])
        else:
            Profile.objects.update_or_create(user=user, defaults={'nickname': nickname})

        try:
            self.create_cloudflare_stream(user)
        except Exception as e:
            # Fall back to a placeholder stream so the rest of the app remains usable in development
            logger.warning("Falling back to placeholder stream for %s: %s", user.username, e)
            Stream.objects.update_or_create(
                user=user,
                defaults={
                    'stream_key': f'dev-{uuid4().hex}',
                    'stream_url': 'rtmp://localhost/live',
                    'viewer_url': f'placeholder-{uuid4().hex}',
                }
            )
        return user

    def create_cloudflare_stream(self, user):
        if not settings.CLOUDFLARE_API_TOKEN or not settings.CLOUDFLARE_ACCOUNT_ID:
            raise Exception("Cloudflare credentials are not configured.")

        headers = {
            'Authorization': f'Bearer {settings.CLOUDFLARE_API_TOKEN}',
            'Content-Type': 'application/json',
        }
        data = {
            "meta": { "name": f"{user.username}'s Stream" },
            "recording": { "mode": "automatic" } # Enable recording
        }
        url = f"https://api.cloudflare.com/client/v4/accounts/{settings.CLOUDFLARE_ACCOUNT_ID}/stream/live_inputs"
        
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            stream_data = response.json()
            
            if stream_data.get("success"):
                result = stream_data.get("result", {})
                stream_key = result.get("rtmps", {}).get("streamKey")
                stream_url = result.get("rtmps", {}).get("url")
                stream_uid = result.get("uid")

                if stream_key and stream_url and stream_uid:
                    Stream.objects.create(
                        user=user,
                        stream_key=stream_key,
                        stream_url=stream_url,
                        viewer_url=stream_uid 
                    )
                else:
                    print(f"Cloudflare API returned incomplete stream data: {stream_data}") # Debugging line
                    raise Exception(f"Incomplete stream data in Cloudflare response: {stream_data}")
            else:
                print(f"Cloudflare API returned an error: {stream_data.get('errors')}") # Debugging line
                raise Exception(f"Cloudflare API returned an error: {stream_data.get('errors')}")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Could not connect to Cloudflare API: {e}")
