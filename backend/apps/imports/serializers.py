from rest_framework import serializers
from .models import ImportSession, ImportIssue


class ImportIssueSerializer(serializers.ModelSerializer):
    anomaly_type_display = serializers.CharField(source="get_anomaly_type_display", read_only=True)
    severity_display = serializers.CharField(source="get_severity_display", read_only=True)
    action_taken_display = serializers.CharField(source="get_action_taken_display", read_only=True)

    class Meta:
        model = ImportIssue
        fields = [
            "id", "csv_row_number", "anomaly_type", "anomaly_type_display",
            "severity", "severity_display", "original_data",
            "action_taken", "action_taken_display", "resolution_notes", "created_at",
        ]
        read_only_fields = fields


class ImportSessionSerializer(serializers.ModelSerializer):
    issues = ImportIssueSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ImportSession
        fields = [
            "id", "uploaded_file_name", "status", "status_display",
            "uploaded_by_name", "target_group",
            "total_rows", "valid_rows", "imported_rows", "skipped_rows", "anomaly_count",
            "usd_to_inr_rate", "started_at", "completed_at", "issues",
        ]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj: ImportSession) -> str:
        u = obj.uploaded_by
        return f"{u.first_name} {u.last_name}".strip()


class ImportSessionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view (no nested issues)."""
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ImportSession
        fields = [
            "id", "uploaded_file_name", "status", "status_display",
            "total_rows", "imported_rows", "skipped_rows", "anomaly_count",
            "started_at", "completed_at",
        ]
        read_only_fields = fields
