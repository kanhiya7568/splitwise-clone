"""
Message serializers.

MessageSerializer       — read (list + history responses)
"""

from rest_framework import serializers

from apps.chat.models import Message
from apps.users.serializers import UserSerializer


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    content = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ["id", "expense", "sender", "content", "is_deleted", "created_at"]
        read_only_fields = fields

    def get_content(self, obj: Message) -> str:
        """Mask soft-deleted message content in API responses."""
        return "[deleted]" if obj.is_deleted else obj.content
