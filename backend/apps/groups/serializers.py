"""
Group serializers.

GroupSerializer           — full group read (nested members, created_by)
GroupCreateSerializer     — create input (name, description)
GroupUpdateSerializer     — update input (name and/or description, both optional)
GroupMemberSerializer     — membership row with embedded user
InviteSerializer          — invite input (email)
"""

from rest_framework import serializers

from apps.groups.models import Group, GroupInvitation, GroupMembership
from apps.users.serializers import UserSerializer


class GroupMemberSerializer(serializers.ModelSerializer):
    """Membership row with embedded user info. Used in group detail response."""

    user = UserSerializer(read_only=True)

    class Meta:
        model = GroupMembership
        fields = ["id", "user", "role", "joined_at"]
        read_only_fields = fields


class GroupSerializer(serializers.ModelSerializer):
    """Full group representation — used for list and detail responses."""

    created_by = UserSerializer(read_only=True)
    members = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "description",
            "created_by",
            "members",
            "member_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_members(self, obj: Group):
        qs = obj.memberships.filter(is_active=True).select_related("user").order_by("joined_at")
        return GroupMemberSerializer(qs, many=True).data

    def get_member_count(self, obj: Group) -> int:
        return obj.memberships.filter(is_active=True).count()


class GroupCreateSerializer(serializers.Serializer):
    """Input for creating a new group."""

    name = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=1000, required=False, default="", allow_blank=True)

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Group name cannot be blank.")
        return value


class GroupUpdateSerializer(serializers.Serializer):
    """
    Input for renaming/updating a group.
    Both fields optional — PATCH semantics.
    At least one must be provided.
    """

    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True)

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Group name cannot be blank.")
        return value

    def validate(self, data: dict) -> dict:
        if not data:
            raise serializers.ValidationError(
                "Provide at least one field to update (name or description)."
            )
        return data


class InviteSerializer(serializers.Serializer):
    """Input for inviting a user by email."""

    email = serializers.EmailField()

    def validate_email(self, value: str) -> str:
        return value.lower().strip()


class GroupInvitationSerializer(serializers.ModelSerializer):
    """Read serializer for pending invitations (used in invite response)."""

    group = serializers.PrimaryKeyRelatedField(read_only=True)
    invited_by = UserSerializer(read_only=True)

    class Meta:
        model = GroupInvitation
        fields = ["id", "group", "email", "invited_by", "status", "created_at", "expires_at"]
        read_only_fields = fields
