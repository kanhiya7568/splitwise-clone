"""
Custom User model.

Design decisions documented in AI_CONTEXT.md Section 14 (Authentication Design):

1. Extends AbstractBaseUser + PermissionsMixin.
   - AbstractBaseUser: provides password hashing, last_login, is_active.
   - PermissionsMixin: adds groups, user_permissions, is_superuser for Django admin.

2. email is the USERNAME_FIELD (login identifier, not username).
   - Unique constraint enforced at both DB level and serializer level.

3. No username field — email is the sole identifier.
   Per approved requirement: "No username."

4. db_table = 'users' matches the schema in AI_CONTEXT.md Section 11.

5. AUTH_USER_MODEL = 'users.User' must be set in settings BEFORE
   the first migration is created. Changing it later requires data migration.

6. Password rules (≥8 chars, uppercase, lowercase, digit) are enforced
   in the authentication serializer, not in the model. This keeps the model
   clean and allows different validation rules per endpoint if needed.
"""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.users.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """
    Application user account.

    Fields:
        email       — unique login identifier
        first_name  — required display name
        last_name   — required display name
        is_active   — controls login access (True by default)
        is_staff    — controls Django admin access
        created_at  — registration timestamp
        updated_at  — last profile update
    """

    email = models.EmailField(
        unique=True,
        db_index=True,
        help_text="Primary identifier used to log in. Must be unique.",
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)

    # Django auth flags
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to disable login without deleting the account.",
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Grants access to the Django admin site.",
    )

    # Audit timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    # Email is the login field — no username
    USERNAME_FIELD = "email"
    # Required when running createsuperuser interactively
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        db_table = "users"
        ordering = ["email"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        """Return first_name + last_name, stripped of leading/trailing spaces."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        """Return first_name only (used by Django admin header)."""
        return self.first_name
