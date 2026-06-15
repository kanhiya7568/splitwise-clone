"""
Authentication tests — Module 2.

Test coverage:
  RegisterView   — valid registration, duplicate email, password rules, missing fields
  LoginView      — valid login, wrong password, non-existent email, inactive user
  LogoutView     — valid logout, already blacklisted, missing token, unauthenticated
  TokenRefreshView — valid refresh, blacklisted token, invalid token
  MeView         — authenticated, unauthenticated

Run with:
    python manage.py test apps.authentication
or:
    pytest apps/authentication/tests.py -v
"""

import json

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_user(
    email="test@example.com",
    password="Secure123",
    first_name="Test",
    last_name="User",
    is_active=True,
) -> User:
    user = User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    user.is_active = is_active
    user.save()
    return user


def get_tokens_for_user(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def auth_header(access_token: str) -> dict:
    return {"HTTP_AUTHORIZATION": f"Bearer {access_token}"}


# ─────────────────────────────────────────────────────────────────────────────
# Registration Tests
# ─────────────────────────────────────────────────────────────────────────────

class RegisterViewTests(APITestCase):
    """Tests for POST /api/auth/register/"""

    def setUp(self):
        self.url = reverse("auth_register")
        self.valid_payload = {
            "first_name": "Riya",
            "last_name": "Sharma",
            "email": "riya@example.com",
            "password": "Secure123",
        }

    def test_register_success_returns_201(self):
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_register_success_returns_tokens(self):
        response = self.client.post(self.url, self.valid_payload, format="json")
        data = response.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertIsNotNone(data["access_token"])
        self.assertIsNotNone(data["refresh_token"])

    def test_register_success_returns_user_object(self):
        response = self.client.post(self.url, self.valid_payload, format="json")
        data = response.json()
        self.assertIn("user", data)
        self.assertEqual(data["user"]["email"], "riya@example.com")
        self.assertEqual(data["user"]["first_name"], "Riya")
        self.assertEqual(data["user"]["last_name"], "Sharma")
        self.assertNotIn("password", data["user"])

    def test_register_success_creates_user_in_db(self):
        self.client.post(self.url, self.valid_payload, format="json")
        self.assertTrue(User.objects.filter(email="riya@example.com").exists())

    def test_register_email_is_case_insensitive(self):
        self.client.post(self.url, self.valid_payload, format="json")
        payload = {**self.valid_payload, "email": "RIYA@EXAMPLE.COM"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_email_returns_400(self):
        self.client.post(self.url, self.valid_payload, format="json")
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.json())

    def test_register_missing_email_returns_400(self):
        payload = {**self.valid_payload}
        del payload["email"]
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_password_returns_400(self):
        payload = {**self.valid_payload}
        del payload["password"]
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_first_name_returns_400(self):
        payload = {**self.valid_payload}
        del payload["first_name"]
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_too_short_returns_400(self):
        payload = {**self.valid_payload, "password": "Ab1"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_no_uppercase_returns_400(self):
        payload = {**self.valid_payload, "password": "secure123"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_no_lowercase_returns_400(self):
        payload = {**self.valid_payload, "password": "SECURE123"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_no_digit_returns_400(self):
        payload = {**self.valid_payload, "password": "SecurePass"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_with_special_chars_succeeds(self):
        """Special characters are optional — should not cause failure."""
        payload = {**self.valid_payload, "password": "Secure123!@#"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_register_invalid_email_format_returns_400(self):
        payload = {**self.valid_payload, "email": "not-an-email"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_does_not_require_auth(self):
        """Registration must be accessible without any token."""
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────────────────────────────────────
# Login Tests
# ─────────────────────────────────────────────────────────────────────────────

class LoginViewTests(APITestCase):
    """Tests for POST /api/auth/login/"""

    def setUp(self):
        self.url = reverse("auth_login")
        self.user = create_user(email="arjun@example.com", password="Travel123")
        self.valid_payload = {
            "email": "arjun@example.com",
            "password": "Travel123",
        }

    def test_login_success_returns_200(self):
        response = self.client.post(self.url, self.valid_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_success_returns_tokens(self):
        response = self.client.post(self.url, self.valid_payload, format="json")
        data = response.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)

    def test_login_success_returns_user(self):
        response = self.client.post(self.url, self.valid_payload, format="json")
        data = response.json()
        self.assertIn("user", data)
        self.assertEqual(data["user"]["email"], "arjun@example.com")

    def test_login_wrong_password_returns_400(self):
        payload = {**self.valid_payload, "password": "WrongPass1"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_nonexistent_email_returns_400(self):
        payload = {**self.valid_payload, "email": "nobody@example.com"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_wrong_and_nonexistent_same_error_message(self):
        """
        Both wrong password and non-existent email must return the same
        error message to prevent user enumeration attacks.
        """
        wrong_pw = self.client.post(
            self.url,
            {**self.valid_payload, "password": "WrongPass1"},
            format="json",
        ).json()
        wrong_email = self.client.post(
            self.url,
            {**self.valid_payload, "email": "nobody@example.com"},
            format="json",
        ).json()
        self.assertEqual(wrong_pw.get("error"), wrong_email.get("error"))

    def test_login_inactive_user_returns_400(self):
        inactive = create_user(
            email="inactive@example.com",
            password="Inactive1",
            is_active=False,
        )
        response = self.client.post(
            self.url,
            {"email": "inactive@example.com", "password": "Inactive1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_missing_email_returns_400(self):
        response = self.client.post(
            self.url, {"password": "Travel123"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_missing_password_returns_400(self):
        response = self.client.post(
            self.url, {"email": "arjun@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_email_case_insensitive(self):
        """Login should work with uppercase version of registered email."""
        payload = {**self.valid_payload, "email": "ARJUN@EXAMPLE.COM"}
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# Logout Tests
# ─────────────────────────────────────────────────────────────────────────────

class LogoutViewTests(APITestCase):
    """Tests for POST /api/auth/logout/"""

    def setUp(self):
        self.url = reverse("auth_logout")
        self.user = create_user(email="priya@example.com", password="Social123")
        self.tokens = get_tokens_for_user(self.user)

    def test_logout_success_returns_200(self):
        response = self.client.post(
            self.url,
            {"refresh_token": self.tokens["refresh"]},
            format="json",
            **auth_header(self.tokens["access"]),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["message"], "Logged out successfully.")

    def test_logout_blacklists_refresh_token(self):
        """After logout, the refresh token must be rejected on /token/refresh/."""
        self.client.post(
            self.url,
            {"refresh_token": self.tokens["refresh"]},
            format="json",
            **auth_header(self.tokens["access"]),
        )
        refresh_url = reverse("auth_token_refresh")
        response = self.client.post(
            refresh_url,
            {"refresh": self.tokens["refresh"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_already_blacklisted_returns_400(self):
        """Attempting to blacklist an already-blacklisted token must return 400."""
        self.client.post(
            self.url,
            {"refresh_token": self.tokens["refresh"]},
            format="json",
            **auth_header(self.tokens["access"]),
        )
        response = self.client.post(
            self.url,
            {"refresh_token": self.tokens["refresh"]},
            format="json",
            **auth_header(self.tokens["access"]),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_missing_token_returns_400(self):
        response = self.client.post(
            self.url,
            {},
            format="json",
            **auth_header(self.tokens["access"]),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_invalid_token_returns_400(self):
        response = self.client.post(
            self.url,
            {"refresh_token": "this.is.not.a.valid.token"},
            format="json",
            **auth_header(self.tokens["access"]),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_requires_authentication(self):
        """Logout without access token must return 401."""
        response = self.client.post(
            self.url,
            {"refresh_token": self.tokens["refresh"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────────────────────────────────────
# Token Refresh Tests
# ─────────────────────────────────────────────────────────────────────────────

class TokenRefreshViewTests(APITestCase):
    """Tests for POST /api/auth/token/refresh/"""

    def setUp(self):
        self.url = reverse("auth_token_refresh")
        self.user = create_user(email="refresh@example.com", password="Refresh123")
        self.tokens = get_tokens_for_user(self.user)

    def test_refresh_success_returns_200(self):
        response = self.client.post(
            self.url, {"refresh": self.tokens["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_refresh_returns_new_access_token(self):
        response = self.client.post(
            self.url, {"refresh": self.tokens["refresh"]}, format="json"
        )
        self.assertIn("access", response.json())

    def test_refresh_invalid_token_returns_401(self):
        response = self.client.post(
            self.url, {"refresh": "bad.token.string"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_missing_token_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# Me Tests
# ─────────────────────────────────────────────────────────────────────────────

class MeViewTests(APITestCase):
    """Tests for GET /api/auth/me/"""

    def setUp(self):
        self.url = reverse("auth_me")
        self.user = create_user(
            email="me@example.com",
            password="MyPass123",
            first_name="Meera",
            last_name="Joshi",
        )
        self.tokens = get_tokens_for_user(self.user)

    def test_me_authenticated_returns_200(self):
        response = self.client.get(self.url, **auth_header(self.tokens["access"]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_me_returns_correct_user(self):
        response = self.client.get(self.url, **auth_header(self.tokens["access"]))
        data = response.json()
        self.assertEqual(data["email"], "me@example.com")
        self.assertEqual(data["first_name"], "Meera")
        self.assertEqual(data["last_name"], "Joshi")
        self.assertEqual(data["full_name"], "Meera Joshi")

    def test_me_does_not_expose_password(self):
        response = self.client.get(self.url, **auth_header(self.tokens["access"]))
        data = response.json()
        self.assertNotIn("password", data)
        self.assertNotIn("password_hash", data)

    def test_me_unauthenticated_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_invalid_token_returns_401(self):
        response = self.client.get(
            self.url, **{"HTTP_AUTHORIZATION": "Bearer invalid.token.here"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_only_allows_get(self):
        """POST to /me/ should return 405 Method Not Allowed."""
        response = self.client.post(
            self.url, {}, format="json", **auth_header(self.tokens["access"])
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
