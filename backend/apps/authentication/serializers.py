"""
Authentication serializers.

RegisterSerializer  — validates and creates a new user
LoginSerializer     — validates credentials and returns authenticated user
LogoutSerializer    — validates the refresh token to be blacklisted

Password validation rules (FR-AUTH-02):
  - Minimum 8 characters
  - At least 1 uppercase letter
  - At least 1 lowercase letter
  - At least 1 digit
  - Special characters optional
"""

import re

from django.contrib.auth import authenticate
from rest_framework import serializers

from apps.users.models import User
from apps.users.serializers import UserSerializer


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def validate_password_strength(value: str) -> str:
    """
    Shared password validation function.
    Raises serializers.ValidationError with a descriptive message on failure.
    Returns the validated value unchanged on success.
    """
    errors = []

    if len(value) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", value):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", value):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", value):
        errors.append("Password must contain at least one digit.")

    if errors:
        raise serializers.ValidationError(errors)

    return value


# ─────────────────────────────────────────────────────────────────────────────
# RegisterSerializer
# ─────────────────────────────────────────────────────────────────────────────

class RegisterSerializer(serializers.ModelSerializer):
    """
    Validates and creates a new user account.

    Input:
        first_name, last_name, email, password

    Output (via view):
        user object + access_token + refresh_token

    Notes:
        - password is write_only — never returned in response
        - email uniqueness validated at DB level (unique=True on model)
          and again here to return a clear 400 before hitting the DB
        - password hashed via UserManager.create_user() → set_password()
    """

    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        help_text="Min 8 chars, 1 uppercase, 1 lowercase, 1 digit.",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "password"]
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": True},
        }

    def validate_email(self, value: str) -> str:
        """Check email uniqueness before hitting the DB constraint."""
        normalised = value.lower().strip()
        if User.objects.filter(email__iexact=normalised).exists():
            raise serializers.ValidationError(
                "A user with this email address already exists."
            )
        return normalised

    def validate_password(self, value: str) -> str:
        return validate_password_strength(value)

    def validate_first_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("First name cannot be blank.")
        return value.strip()

    def validate_last_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError("Last name cannot be blank.")
        return value.strip()

    def create(self, validated_data: dict) -> User:
        """Delegates to UserManager.create_user() which hashes the password."""
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# LoginSerializer
# ─────────────────────────────────────────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    """
    Validates email + password credentials.

    On success, adds the authenticated User instance to validated_data['user'].
    The view then generates JWT tokens for that user.

    Security notes:
      - Returns the same generic error for wrong email AND wrong password
        (prevents user enumeration via timing or message differences).
      - Uses Django's authenticate() which handles password hashing comparison.
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, data: dict) -> dict:
        email = data.get("email", "").lower().strip()
        password = data.get("password", "")

        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")

        # Django's authenticate uses USERNAME_FIELD ('email') for lookup
        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )

        if user is None:
            raise serializers.ValidationError(
                "Invalid email or password. Please check your credentials."
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "This account has been deactivated. Please contact support."
            )

        data["user"] = user
        return data


# ─────────────────────────────────────────────────────────────────────────────
# LogoutSerializer
# ─────────────────────────────────────────────────────────────────────────────

class LogoutSerializer(serializers.Serializer):
    """
    Accepts the refresh token to be blacklisted on logout.

    The token is validated by the view (RefreshToken constructor raises
    TokenError if the token is invalid, expired, or already blacklisted).
    """

    refresh_token = serializers.CharField(
        help_text="The refresh token issued at login. Will be blacklisted."
    )
