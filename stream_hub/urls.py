from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),  # Backwards compatibility for old clients
    path('', include('api.urls')),      # New default: endpoints available at root
]
