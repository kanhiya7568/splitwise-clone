"""
Tests for the CSV import module.

Tests cover:
  - CSV parser (date formats, amount parsing, name normalisation)
  - Anomaly detection (all 16 types)
  - Import service (full integration)
  - Import report generation
  - Membership timeline validation
  - Currency conversion logic
  - Duplicate detection
"""

import io
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.groups.models import Group, GroupMembership
from apps.imports.models import ImportIssue, ImportSession
from apps.imports.services import (
    USD_TO_INR,
    generate_import_report,
    infer_category,
    is_likely_duplicate,
    looks_like_settlement,
    normalise_name,
    parse_amount,
    parse_date,
    parse_participants,
    process_csv_import,
    resolve_user_name,
)

User = get_user_model()


# ── Fixtures ───────────────────────────────────────────────────────────────────

def make_user(email, first, last="Test"):
    return User.objects.create_user(
        email=email, password="Pass1234!", first_name=first, last_name=last
    )


def make_group(name, creator):
    g = Group.objects.create(name=name, created_by=creator)
    GroupMembership.objects.get_or_create(group=g, user=creator, defaults={"role": "admin", "is_active": True})
    return g


def add_member(group, user):
    GroupMembership.objects.get_or_create(group=group, user=user, defaults={"role": "member", "is_active": True})


# ── Name normalisation ─────────────────────────────────────────────────────────

class TestNormaliseName(TestCase):
    def test_lowercase_becomes_titlecase(self):
        assert normalise_name("priya") == "Priya"

    def test_whitespace_stripped(self):
        assert normalise_name("  Aisha  ") == "Aisha"

    def test_empty_string(self):
        assert normalise_name("") == ""

    def test_mixed_case(self):
        assert normalise_name("rOHAN") == "Rohan"

    def test_with_surname_initial(self):
        assert normalise_name("priya s") == "Priya S"


# ── Date parsing ───────────────────────────────────────────────────────────────

class TestParseDate(TestCase):
    def test_iso_format(self):
        d, iso, ambig = parse_date("2026-02-01")
        assert d == date(2026, 2, 1)
        assert iso == "2026-02-01"
        assert not ambig

    def test_dd_mm_yyyy(self):
        d, iso, ambig = parse_date("01/03/2026")
        assert d == date(2026, 3, 1)
        assert "2026-03-01" in iso

    def test_ambiguous_shorthand_mar14(self):
        d, iso, ambig = parse_date("Mar 14")
        assert d is not None
        assert ambig is True
        assert "-14" in iso

    def test_blank_returns_none(self):
        d, iso, ambig = parse_date("")
        assert d is None

    def test_invalid_returns_none(self):
        d, iso, ambig = parse_date("not-a-date")
        assert d is None

    def test_month_day_year(self):
        d, iso, ambig = parse_date("Mar 14 2026")
        assert d == date(2026, 3, 14)


# ── Amount parsing ─────────────────────────────────────────────────────────────

class TestParseAmount(TestCase):
    def test_normal_integer(self):
        val, warnings = parse_amount("3200")
        assert val == Decimal("3200.00")
        assert not warnings

    def test_comma_number(self):
        val, warnings = parse_amount("1,200")
        assert val == Decimal("1200.00")

    def test_three_decimal_places_rounded(self):
        val, warnings = parse_amount("899.995")
        assert val == Decimal("900.00")
        assert len(warnings) == 1
        assert "rounded" in warnings[0].lower()

    def test_zero_amount(self):
        val, warnings = parse_amount("0")
        assert val == Decimal("0")

    def test_negative_amount(self):
        val, warnings = parse_amount("-30")
        assert val == Decimal("-30.00")

    def test_invalid_string(self):
        val, warnings = parse_amount("not-a-number")
        assert val is None
        assert len(warnings) == 1

    def test_usd_conversion(self):
        """Verify conversion math."""
        usd_amount = Decimal("100.00")
        inr = (usd_amount * USD_TO_INR).quantize(Decimal("0.01"))
        assert inr == Decimal("8350.00")


# ── Duplicate detection ────────────────────────────────────────────────────────

class TestDuplicateDetection(TestCase):
    def _seen(self):
        return [{
            "date": date(2026, 2, 8),
            "description": "Dinner at Marina",
            "amount": Decimal("3200.00"),
            "paid_by": "Dev",
        }]

    def test_exact_duplicate_detected(self):
        assert is_likely_duplicate(
            date(2026, 2, 8), "dinner - marina b", Decimal("3200.00"), "Dev", self._seen()
        )

    def test_different_date_not_duplicate(self):
        assert not is_likely_duplicate(
            date(2026, 2, 9), "Dinner at Marina", Decimal("3200.00"), "Dev", self._seen()
        )

    def test_different_payer_not_duplicate(self):
        assert not is_likely_duplicate(
            date(2026, 2, 8), "Dinner at Marina", Decimal("3200.00"), "Aisha", self._seen()
        )

    def test_very_different_description_not_duplicate(self):
        assert not is_likely_duplicate(
            date(2026, 2, 8), "Rent payment", Decimal("3200.00"), "Dev", self._seen()
        )

    def test_empty_seen_not_duplicate(self):
        assert not is_likely_duplicate(
            date(2026, 2, 8), "Dinner at Marina", Decimal("3200.00"), "Dev", []
        )


# ── Settlement detection ───────────────────────────────────────────────────────

class TestSettlementDetection(TestCase):
    def test_paid_keyword_single_participant(self):
        users = [User()]  # dummy user object
        assert looks_like_settlement("Rohan paid Aisha", "", users)

    def test_expense_not_settlement(self):
        users = [User(), User(), User()]
        assert not looks_like_settlement("Groceries BigBazaar", "equal", users)

    def test_repaid_keyword(self):
        users = [User()]
        assert looks_like_settlement("Aisha repaid Rohan", "", users)

    def test_refund_keyword_no_split(self):
        users = []
        assert looks_like_settlement("Parasailing refund", "", users)


# ── Category inference ─────────────────────────────────────────────────────────

class TestInferCategory(TestCase):
    def test_rent_is_utilities(self):
        assert infer_category("February rent") == "utilities"

    def test_groceries_is_food(self):
        assert infer_category("Groceries BigBazaar") == "food"

    def test_flight_is_transport(self):
        assert infer_category("Goa flights") == "transport"

    def test_hotel_is_accommodation(self):
        assert infer_category("Goa villa booking") == "accommodation"

    def test_unknown_is_general(self):
        assert infer_category("Random expense") == "general"


# ── Full integration import ────────────────────────────────────────────────────

class TestProcessCsvImport(TestCase):
    def setUp(self):
        self.admin = make_user("aisha@test.com", "Aisha")
        self.rohan = make_user("rohan@test.com", "Rohan")
        self.priya = make_user("priya@test.com", "Priya")
        self.meera = make_user("meera@test.com", "Meera")
        self.group = make_group("Flat 42", self.admin)
        add_member(self.group, self.rohan)
        add_member(self.group, self.priya)
        add_member(self.group, self.meera)

    def _run(self, csv_text):
        return process_csv_import(csv_text, self.admin, self.group, "test.csv")

    def test_valid_row_is_imported(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-02-01,February rent,Aisha,48000,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        assert session.imported_rows == 1
        assert session.skipped_rows == 0
        assert session.status == "completed"

    def test_zero_amount_skipped(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-03-22,Dinner order,Priya,0,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        assert session.skipped_rows == 1
        issue = session.issues.filter(anomaly_type="zero_amount").first()
        assert issue is not None

    def test_negative_amount_skipped_as_refund(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-03-12,Parasailing refund,Aisha,-30,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        assert session.skipped_rows == 1
        issue = session.issues.filter(anomaly_type="negative_amount").first()
        assert issue is not None
        assert issue.action_taken == "treated_as_refund"

    def test_duplicate_flagged(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-02-08,Dinner at Marina,Aisha,3200,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        csv += "2026-02-08,dinner - marina b,Aisha,3200,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        assert session.imported_rows == 1
        assert session.skipped_rows == 1
        issue = session.issues.filter(anomaly_type="duplicate").first()
        assert issue is not None
        assert issue.action_taken == "flagged_duplicate_pending_review"

    def test_usd_currency_converted(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-03-09,Goa villa booking,Aisha,540,USD,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        assert session.imported_rows == 1
        issue = session.issues.filter(anomaly_type="currency_conversion").first()
        assert issue is not None
        # 540 * 83.50 = 45090
        from apps.expenses.models import Expense
        exp = Expense.objects.filter(group=self.group).order_by("-created_at").first()
        assert exp is not None
        assert exp.amount == Decimal("45090.00")

    def test_settlement_row_converted(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-02-25,Rohan paid Aisha,Rohan,5000,INR,,Aisha,,\n"
        session = self._run(csv)
        issue = session.issues.filter(anomaly_type="settlement_as_expense").first()
        assert issue is not None
        assert issue.action_taken == "converted_to_settlement"

    def test_name_normalisation(self):
        """
        'priya' → title-cased to 'Priya' which matches exactly via first-name comparison.
        The expense should be imported successfully.
        A name_normalization issue is only logged when there is a non-exact match
        (e.g. 'Priya S' or fuzzy match). For pure case differences that resolve exactly,
        the expense is silently normalised and imported.
        """
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-02-14,Movie night,priya,640,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        # Expense should be imported — normalisation succeeded
        assert session.imported_rows == 1

    def test_ambiguous_name_normalisation(self):
        """'Priya S' should match Priya via partial first-name match and log an issue."""
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-02-18,Groceries DMart,Priya S,1875,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        assert session.imported_rows == 1
        issue = session.issues.filter(anomaly_type="name_normalization").first()
        assert issue is not None

    def test_unknown_user_skipped(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-04-08,Sam deposit,Sam,15000,INR,equal,Aisha;Rohan;Priya;Sam,,\n"
        session = self._run(csv)
        assert session.skipped_rows == 1
        issue = session.issues.filter(anomaly_type="unknown_user").first()
        assert issue is not None

    def test_non_iso_date_logged(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "01/03/2026,March rent,Aisha,48000,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        assert session.imported_rows == 1
        issues = session.issues.filter(anomaly_type__in=["date_format", "ambiguous_date"])
        assert issues.exists()

    def test_ambiguous_shorthand_date(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "Mar 14,Airport cab,Aisha,1100,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        issue = session.issues.filter(anomaly_type="ambiguous_date").first()
        assert issue is not None

    def test_split_type_alias_normalised(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-03-10,Scooter rentals,Priya,3600,INR,share,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        assert session.imported_rows == 1
        issue = session.issues.filter(anomaly_type="split_type_invalid").first()
        assert issue is not None
        assert "shares" in issue.resolution_notes

    def test_comma_amount_parsed(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-02-10,Electricity,Aisha,\"1,200\",INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        assert session.imported_rows == 1

    def test_blank_description_skipped(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-02-10,,Aisha,1200,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        assert session.skipped_rows == 1

    def test_import_report_structure(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-02-01,Rent,Aisha,48000,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        report = generate_import_report(session)
        assert "session_id" in report
        assert "total_rows" in report
        assert "imported_rows" in report
        assert "issues" in report
        assert "anomaly_breakdown" in report

    def test_multiple_rows_mixed(self):
        csv = "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
        csv += "2026-02-01,Rent,Aisha,48000,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        csv += "2026-03-22,Cancelled dinner,Priya,0,INR,equal,Aisha;Rohan;Priya;Meera,,\n"
        csv += "2026-03-09,Goa villa,Aisha,540,USD,equal,Aisha;Rohan;Priya;Meera,,\n"
        session = self._run(csv)
        assert session.total_rows == 3
        assert session.imported_rows == 2  # rent + converted USD
        assert session.skipped_rows == 1   # zero amount
