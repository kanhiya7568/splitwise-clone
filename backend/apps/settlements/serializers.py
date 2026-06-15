"""
Settlement serializers.

SettlementSerializer       — read (list + detail responses)
SettlementCreateSerializer — write input for POST
SettlementUpdateSerializer — write input for PATCH (all fields optional)
"""

from decimal import Decimal

from rest_framework import serializers

from apps.settlements.models import Settlement
from apps.users.serializers import UserSerializer


class SettlementSerializer(serializers.ModelSerializer):
    """Full settlement representation for list and detail responses."""

    payer = UserSerializer(read_only=True)
    receiver = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Settlement
        fields = [
            "id",
            "group",
            "payer",
            "receiver",
            "created_by",
            "amount",
            "note",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SettlementCreateSerializer(serializers.Serializer):
    """Input for POST /api/groups/{id}/settlements/"""

    payer_id = serializers.IntegerField(min_value=1)
    receiver_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    note = serializers.CharField(max_length=1000, required=False, default="", allow_blank=True)

    def validate(self, data: dict) -> dict:
        if data["payer_id"] == data["receiver_id"]:
            raise serializers.ValidationError(
                {"receiver_id": "Payer and receiver must be different users."}
            )
        return data

    def to_service_args(self, group, created_by) -> dict:
        d = self.validated_data
        return {
            "group": group,
            "created_by": created_by,
            "payer_id": d["payer_id"],
            "receiver_id": d["receiver_id"],
            "amount": d["amount"],
            "note": d.get("note", ""),
        }


class SettlementUpdateSerializer(serializers.Serializer):
    """Input for PATCH /api/groups/{id}/settlements/{sid}/"""

    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"), required=False
    )
    note = serializers.CharField(max_length=1000, required=False, allow_blank=True)

    def validate(self, data: dict) -> dict:
        if not data:
            raise serializers.ValidationError("Provide at least one field to update.")
        return data

    def to_service_args(self) -> dict:
        d = self.validated_data
        return {
            "amount": d.get("amount"),
            "note": d.get("note"),
        }
