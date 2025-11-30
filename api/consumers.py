import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Stream, ChatMessage, Ban, Profile # Import Profile

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        self.user = self.scope.get('user')

        self.streamer = await self.get_streamer()
        if not self.streamer:
            await self.close()
            return

        self.stream = await self.get_stream_instance()
        if not self.stream:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        history = await self.get_chat_history()
        for message in history:
            payload = await self.build_message_payload(message.user, message.message)
            await self.send(text_data=json.dumps(payload))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        if not self.user.is_authenticated:
            await self.send_error("You must be logged in to chat.")
            return

        text_data_json = json.loads(text_data)
        message_text = text_data_json['message']

        is_banned = await self.is_user_banned()
        if is_banned:
            await self.send_error("You are banned from this chat.")
            return

        chat_message = await self.save_message(message_text)
        display_name = await self.get_user_display_name(self.user)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': chat_message.message,
                'username': self.user.username,
                'display_name': display_name,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username'],
            'display_name': event.get('display_name', event['username']),
        }))

    async def send_error(self, message):
        await self.send(text_data=json.dumps({
            'error': message,
        }))

    @database_sync_to_async
    def get_streamer(self):
        try:
            return User.objects.get(username=self.room_name)
        except User.DoesNotExist:
            return None

    @database_sync_to_async
    def get_stream_instance(self):
        try:
            return Stream.objects.get(user=self.streamer)
        except Stream.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_chat_history(self):
        messages = ChatMessage.objects.filter(stream=self.stream).order_by('timestamp')[:50] # Changed to oldest-first
        return list(messages)

    @database_sync_to_async
    def is_user_banned(self):
        return Ban.objects.filter(streamer=self.streamer, banned_user=self.user).exists()

    @database_sync_to_async
    def save_message(self, message_text):
        return ChatMessage.objects.create(
            user=self.user,
            stream=self.stream,
            message=message_text
        )

    @database_sync_to_async
    def get_user_display_name(self, user_instance):
        if user_instance.is_authenticated:
            try:
                return user_instance.profile.nickname
            except Profile.DoesNotExist:
                return user_instance.username # Fallback to username if no profile
        return "Anonymous"

    async def build_message_payload(self, user_instance, message_text):
        display_name = await self.get_user_display_name(user_instance)
        return {
            'message': message_text,
            'username': getattr(user_instance, 'username', 'Anonymous'),
            'display_name': display_name,
        }
