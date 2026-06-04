from django.urls import path
from .views import (
    LoginView, LogoutView, CookieTokenRefreshView, MeView,
    UserListCreateView, UserDetailView, UserPasswordResetView,
)

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/refresh/', CookieTokenRefreshView.as_view(), name='auth-refresh'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    path('users/', UserListCreateView.as_view(), name='user-list'),
    path('users/<uuid:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('users/<uuid:pk>/reset-password/', UserPasswordResetView.as_view(), name='user-reset-password'),
]
