"""
Custom UserManager.

Uses email as the primary identifier instead of username.
Required when the model extends AbstractBaseUser.
"""

from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    """
    Manager for the custom User model.

    create_user()      — for regular registration
    create_superuser() — for Django admin / management commands
    """

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields,
    ):
        """
        Create and persist a regular user.

        Args:
            email: Must be unique across all users.
            password: Plain text — hashed via set_password() before saving.
            **extra_fields: first_name, last_name, etc.

        Raises:
            ValueError: If email is empty.
        """
        if not email:
            raise ValueError("An email address is required.")

        email = self.normalize_email(email)  # lowercase the domain part
        user = self.model(email=email, **extra_fields)
        user.set_password(password)          # hashes via PBKDF2-SHA256
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields,
    ):
        """
        Create and persist a superuser with Django admin access.

        Called by: python manage.py createsuperuser
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)
