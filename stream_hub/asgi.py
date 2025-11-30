import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stream_hub.settings')
django.setup()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import api.routing
from api.token_auth_middleware import TokenAuthMiddleware

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        TokenAuthMiddleware(
            URLRouter(
                api.routing.websocket_urlpatterns
            )
        )
    ),
})