"""
Authentication URL patterns.

All routes prefixed with /api/auth/ via config/urls.py.

Full URL table:
    POST /api/auth/register/        RegisterView
    POST /api/auth/login/           LoginView
    POST /api/auth/logout/          LogoutView
    POST /api/auth/token/refresh/   TokenRefreshView
    GET  /api/auth/me/              MeView
"""

from django.urls import path

from .views import LoginView, LogoutView, MeView, RegisterView, TokenRefreshView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth_register"),
    path("login/", LoginView.as_view(), name="auth_login"),
    path("logout/", LogoutView.as_view(), name="auth_logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth_token_refresh"),
    path("me/", MeView.as_view(), name="auth_me"),
]
