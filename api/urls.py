from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('stream/<str:username>/', views.StreamInfoView.as_view(), name='stream-info'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('password/change/', views.PasswordChangeView.as_view(), name='password_change'),
    path('stream/<str:username>/banned/', views.BannedUsersListView.as_view(), name='banned-users'),
    path('ban/', views.BanView.as_view(), name='ban'),
    path('unban/', views.UnbanView.as_view(), name='unban'),
]