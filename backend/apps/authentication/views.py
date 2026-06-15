"""
Authentication views.

RegisterView      POST /api/auth/register/     — create account + return tokens
LoginView         POST /api/auth/login/        — validate credentials + return tokens
LogoutView        POST /api/auth/logout/       — blacklist refresh token
TokenRefreshView  POST /api/auth/token/refresh/ — exchange refresh for new access token
MeView            GET  /api/auth/me/           — return current user's profile

Token strategy (per AI_CONTEXT.md Section 14):
  - Access token:  60 minutes, returned in JSON response body
  - Refresh token: 7 days, returned in JSON response body
    (httpOnly cookie is preferred but Render + Vercel cross-origin
     setup makes it unreliable without a custom domain; documented tradeoff)
  - On logout: refresh token is blacklisted via simplejwt's built-in blacklist
  - On refresh: old refresh token is automatically blacklisted (BLACKLIST_AFTER_ROTATION=True)
"""

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView

from apps.users.serializers import UserSerializer
from .serializers import LoginSerializer, LogoutSerializer, RegisterSerializer


def _token_response(user, http_status=status.HTTP_200_OK) -> Response:
    """
    Helper: generate access + refresh token pair for a user and return
    a standard response envelope.

    Called by both RegisterView and LoginView to keep response shape identical.
    """
    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "user": UserSerializer(user).data,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
        },
        status=http_status,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/register/
# ─────────────────────────────────────────────────────────────────────────────

class RegisterView(generics.CreateAPIView):
    """
    Register a new user account.

    Authentication: Not required (AllowAny).
    Throttle: AnonRateThrottle (20/hour per IP).

    Request body:
        {
            "first_name": "Riya",
            "last_name":  "Sharma",
            "email":      "riya@example.com",
            "password":   "SecurePass1"
        }

    Response 201:
        {
            "user": { id, email, first_name, last_name, full_name, created_at },
            "access_token":  "<60-min JWT>",
            "refresh_token": "<7-day JWT>"
        }

    Response 400:
        { "error": "...", "details": { "field": ["message"] } }
    """

    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    # Override throttle to use anon rate for unauthenticated endpoint
    throttle_scope = "anon"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return _token_response(user, http_status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/login/
# ─────────────────────────────────────────────────────────────────────────────

class LoginView(generics.GenericAPIView):
    """
    Authenticate a user and issue JWT tokens.

    Authentication: Not required (AllowAny).
    Throttle: AnonRateThrottle (20/hour per IP).

    Request body:
        { "email": "riya@example.com", "password": "SecurePass1" }

    Response 200:
        {
            "user": { id, email, first_name, last_name, full_name, created_at },
            "access_token":  "<60-min JWT>",
            "refresh_token": "<7-day JWT>"
        }

    Response 400:
        { "error": "Invalid email or password. Please check your credentials." }
    """

    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    throttle_scope = "anon"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return _token_response(user, http_status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/logout/
# ─────────────────────────────────────────────────────────────────────────────

class LogoutView(APIView):
    """
    Invalidate a refresh token (logout).

    Authentication: Required (IsAuthenticated via access token in header).

    How blacklisting works:
      - simplejwt maintains two tables:
          token_blacklist_outstandingtoken  — tracks every issued refresh token
          token_blacklist_blacklistedtoken  — marks tokens as invalid
      - RefreshToken(token_string).blacklist() writes to the blacklist table.
      - Subsequent calls to /token/refresh/ with a blacklisted token return 401.
      - The access token is NOT blacklisted (it's short-lived at 60 min;
        blacklisting access tokens requires a lookup on every request which is expensive).

    Request body:
        { "refresh_token": "<refresh-jwt>" }

    Response 200:
        { "message": "Logged out successfully." }

    Response 400:
        { "error": "Token is invalid or has already been blacklisted." }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token_string = serializer.validated_data["refresh_token"]

        try:
            token = RefreshToken(token_string)
            token.blacklist()
        except TokenError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/auth/token/refresh/
# ─────────────────────────────────────────────────────────────────────────────

class TokenRefreshView(BaseTokenRefreshView):
    """
    Exchange a valid refresh token for a new access token.

    Extends simplejwt's built-in TokenRefreshView.
    No custom logic needed — simplejwt handles:
      - Validating the refresh token (not expired, not blacklisted)
      - Issuing a new access token
      - If ROTATE_REFRESH_TOKENS=True: issuing a new refresh token
      - If BLACKLIST_AFTER_ROTATION=True: blacklisting the old refresh token

    Authentication: Not required.

    Request body:
        { "refresh": "<refresh-jwt>" }

    Response 200:
        { "access": "<new-access-jwt>", "refresh": "<new-refresh-jwt>" }

    Response 401:
        { "error": "Token is invalid or expired." }
    """
    # Inheriting entirely from BaseTokenRefreshView.
    # Documented here to make the endpoint explicit in code navigation.
    pass


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/auth/me/
# ─────────────────────────────────────────────────────────────────────────────

class MeView(generics.RetrieveAPIView):
    """
    Return the profile of the currently authenticated user.

    Authentication: Required (IsAuthenticated).

    Response 200:
        {
            "id": 1,
            "email": "riya@example.com",
            "first_name": "Riya",
            "last_name": "Sharma",
            "full_name": "Riya Sharma",
            "created_at": "2025-06-14T19:00:00Z"
        }

    Response 401:
        { "error": "Authentication credentials were not provided." }
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        # request.user is populated by JWTAuthentication from the Bearer token
        return self.request.user
