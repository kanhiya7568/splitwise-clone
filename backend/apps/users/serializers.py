"""
User serializer (read-only).

Placed in apps/users/ so it can be imported by both:
  - apps/authentication/ (register/login responses)
  - any other app that needs to embed user data in responses

Never exposes password_hash, is_staff, or is_superuser.
"""

from rest_framework import serializers

from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the User model.

    Used in API responses wherever a user object needs to be embedded
    (registration response, login response, /me/ endpoint, expense splits,
    settlement payer/receiver, chat message sender, group member list).
    """

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "created_at",
        ]
        read_only_fields = fields

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name()
