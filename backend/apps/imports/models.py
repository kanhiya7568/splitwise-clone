"""
Import module models: ImportSession, ImportIssue.

ImportSession tracks each CSV upload end-to-end.
ImportIssue records every anomaly found, with action taken and audit notes.
"""

from django.conf import settings
from django.db import models


class ImportSession(models.Model):
    """One row per CSV file uploaded by a user."""

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="import_sessions",
    )
    uploaded_file_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    target_group = models.ForeignKey(
        "groups.Group",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_sessions",
    )

    # Counters populated after processing
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    imported_rows = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)
    anomaly_count = models.PositiveIntegerField(default=0)

    # USD→INR rate used during this import (documented for auditability)
    usd_to_inr_rate = models.DecimalField(max_digits=8, decimal_places=4, default="83.5000")

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Raw CSV stored for re-processing / audit
    raw_csv = models.TextField(blank=True)

    class Meta:
        db_table = "import_sessions"
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"ImportSession #{self.id} — {self.uploaded_file_name} ({self.status})"


class ImportIssue(models.Model):
    """One row per anomaly detected during an import session."""

    # ── Anomaly types ─────────────────────────────────────────────────────────
    ANOMALY_DUPLICATE = "duplicate"
    ANOMALY_MISSING_FIELD = "missing_field"
    ANOMALY_INVALID_AMOUNT = "invalid_amount"
    ANOMALY_NEGATIVE_AMOUNT = "negative_amount"
    ANOMALY_ZERO_AMOUNT = "zero_amount"
    ANOMALY_DATE_FORMAT = "date_format"
    ANOMALY_AMBIGUOUS_DATE = "ambiguous_date"
    ANOMALY_CURRENCY_CONVERSION = "currency_conversion"
    ANOMALY_UNKNOWN_USER = "unknown_user"
    ANOMALY_PARTICIPANT_MISMATCH = "participant_mismatch"
    ANOMALY_SETTLEMENT_AS_EXPENSE = "settlement_as_expense"
    ANOMALY_SPLIT_INCONSISTENCY = "split_inconsistency"
    ANOMALY_NAME_NORMALIZATION = "name_normalization"
    ANOMALY_MEMBERSHIP_VIOLATION = "membership_violation"
    ANOMALY_SPLIT_TYPE_INVALID = "split_type_invalid"
    ANOMALY_DECIMAL_PRECISION = "decimal_precision"

    ANOMALY_TYPES = [
        (ANOMALY_DUPLICATE, "Duplicate Expense"),
        (ANOMALY_MISSING_FIELD, "Missing Required Field"),
        (ANOMALY_INVALID_AMOUNT, "Invalid Amount"),
        (ANOMALY_NEGATIVE_AMOUNT, "Negative Amount (Refund)"),
        (ANOMALY_ZERO_AMOUNT, "Zero Amount"),
        (ANOMALY_DATE_FORMAT, "Date Format Issue"),
        (ANOMALY_AMBIGUOUS_DATE, "Ambiguous Date"),
        (ANOMALY_CURRENCY_CONVERSION, "Currency Conversion Required"),
        (ANOMALY_UNKNOWN_USER, "Unknown User"),
        (ANOMALY_PARTICIPANT_MISMATCH, "Participant Mismatch"),
        (ANOMALY_SETTLEMENT_AS_EXPENSE, "Settlement Disguised as Expense"),
        (ANOMALY_SPLIT_INCONSISTENCY, "Split Inconsistency"),
        (ANOMALY_NAME_NORMALIZATION, "Name Normalization Applied"),
        (ANOMALY_MEMBERSHIP_VIOLATION, "Membership Timeline Violation"),
        (ANOMALY_SPLIT_TYPE_INVALID, "Invalid Split Type"),
        (ANOMALY_DECIMAL_PRECISION, "Decimal Precision Adjusted"),
    ]

    # ── Severity ──────────────────────────────────────────────────────────────
    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_ERROR = "error"
    SEVERITY_CRITICAL = "critical"
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, "Info"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_ERROR, "Error"),
        (SEVERITY_CRITICAL, "Critical"),
    ]

    # ── Action taken ──────────────────────────────────────────────────────────
    ACTION_IMPORTED = "imported"
    ACTION_SKIPPED = "skipped"
    ACTION_CONVERTED_SETTLEMENT = "converted_to_settlement"
    ACTION_NORMALIZED = "normalized_and_imported"
    ACTION_CURRENCY_CONVERTED = "currency_converted_and_imported"
    ACTION_FLAGGED_DUPLICATE = "flagged_duplicate_pending_review"
    ACTION_TREATED_AS_REFUND = "treated_as_refund"
    ACTION_ROUNDED = "rounded_and_imported"

    ACTION_CHOICES = [
        (ACTION_IMPORTED, "Imported"),
        (ACTION_SKIPPED, "Skipped"),
        (ACTION_CONVERTED_SETTLEMENT, "Converted to Settlement"),
        (ACTION_NORMALIZED, "Normalized and Imported"),
        (ACTION_CURRENCY_CONVERTED, "Currency Converted and Imported"),
        (ACTION_FLAGGED_DUPLICATE, "Flagged as Duplicate — Pending Review"),
        (ACTION_TREATED_AS_REFUND, "Treated as Refund — Expense Skipped"),
        (ACTION_ROUNDED, "Rounded to 2dp and Imported"),
    ]

    import_session = models.ForeignKey(
        ImportSession,
        on_delete=models.CASCADE,
        related_name="issues",
    )
    csv_row_number = models.PositiveIntegerField()
    anomaly_type = models.CharField(max_length=50, choices=ANOMALY_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    # Original CSV row data preserved for full auditability
    original_data = models.JSONField(default=dict)
    action_taken = models.CharField(max_length=50, choices=ACTION_CHOICES)
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "import_issues"
        ordering = ["csv_row_number"]

    def __str__(self) -> str:
        return f"Row {self.csv_row_number}: {self.get_anomaly_type_display()} [{self.severity}]"
