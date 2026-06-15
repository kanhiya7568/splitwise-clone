"""
CSV Import Service.

Handles: parsing → normalization → anomaly detection → import → reporting.

Design decisions:
  - Never crash entire import on a single bad row.
  - Never silently guess. Every decision is logged in ImportIssue.
  - USD→INR rate: 83.50 (fixed, documented in ImportSession.usd_to_inr_rate).
  - Duplicate detection: same date + same payer (normalised) + amount within ±1.
  - Settlement detection: split_type blank AND only 1 participant AND description
    contains payment keywords.
  - All monetary values stored as Decimal; no float arithmetic.
"""

import csv
import io
import re
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.expenses.models import Expense, ExpenseSplit
from apps.expenses.services import create_expense
from apps.groups.models import Group, GroupMembership
from apps.imports.models import ImportIssue, ImportSession
from apps.settlements.models import Settlement
from apps.users.models import User

# ── Constants ──────────────────────────────────────────────────────────────────

USD_TO_INR = Decimal("83.5000")

KNOWN_SPLIT_TYPES = {"equal", "unequal", "percentage", "shares"}

# Map of display-name → canonical name normalisation
SPLIT_TYPE_ALIASES = {
    "share": "shares",
    "equal split": "equal",
    "percentage split": "percentage",
    "unequal split": "unequal",
}

SETTLEMENT_KEYWORDS = ["paid", "repaid", "returned", "refund", "payback", "reimburse"]

DATE_FORMATS = [
    "%Y-%m-%d",   # 2026-02-01 (ISO, preferred)
    "%d/%m/%Y",   # 01/03/2026
    "%m/%d/%Y",   # ambiguous when day ≤ 12
    "%d-%m-%Y",   # 01-03-2026
    "%b %d",      # Mar 14  (year assumed current)
    "%B %d",      # March 14
    "%b %d %Y",   # Mar 14 2026
    "%d %b %Y",   # 14 Mar 2026
]

CSV_COLUMNS = ["date", "description", "paid_by", "amount", "currency", "split_type", "split_with", "split_details", "notes"]


# ── Name normalisation ─────────────────────────────────────────────────────────

def normalise_name(raw: str) -> str:
    """Strip whitespace and title-case. 'priya' → 'Priya', 'Priya S' → 'Priya S'."""
    return raw.strip().title() if raw else ""


def resolve_user_name(raw: str, group: Group) -> tuple[User | None, list[str]]:
    """
    Try to find a group member whose first_name matches the normalised raw name.
    Returns (user_or_none, [warnings]).
    """
    warnings = []
    normalised = normalise_name(raw)
    if not normalised:
        return None, ["Empty user name"]

    members = group.memberships.filter(is_active=True).select_related("user")

    # 1. Exact first-name match (case-insensitive)
    for m in members:
        if m.user.first_name.lower() == normalised.split()[0].lower():
            if normalised != m.user.first_name:
                warnings.append(f"Name normalised: '{raw}' → '{m.user.first_name}'")
            return m.user, warnings

    # 2. Exact match on first component of name (handles 'Priya S' → 'Priya')
    for m in members:
        if normalised.split()[0].lower() == m.user.first_name.lower():
            if normalised != m.user.first_name:
                warnings.append(f"Name normalised: '{raw}' → '{m.user.first_name}' (partial match on first name)")
            return m.user, warnings

    # 3. Fuzzy match (SequenceMatcher ≥ 0.65)
    for m in members:
        ratio = SequenceMatcher(None, normalised.lower(), m.user.first_name.lower()).ratio()
        if ratio >= 0.65:
            warnings.append(f"Fuzzy name match: '{raw}' → '{m.user.first_name}' (score={ratio:.2f})")
            return m.user, warnings

    return None, [f"Unknown user: '{raw}' not found among active group members"]


# ── Date parsing ───────────────────────────────────────────────────────────────

def parse_date(raw: str) -> tuple[date | None, str | None, bool]:
    """
    Returns (date_obj, canonical_iso_string, is_ambiguous).
    'Mar 14' is ambiguous (year unknown). '10/03/2026' is ambiguous (day-first assumed).
    """
    raw = raw.strip()
    if not raw:
        return None, None, False

    # Detect ambiguous shorthand like "Mar 14" or "March 14" (no year)
    shorthand_match = re.match(r"^([A-Za-z]+)\s+(\d{1,2})$", raw)
    if shorthand_match:
        try:
            parsed = datetime.strptime(raw + f" {date.today().year}", "%b %d %Y")
            return parsed.date(), parsed.date().isoformat(), True
        except ValueError:
            pass

    # Try each known format; track if ambiguous (DD/MM vs MM/DD)
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(raw, fmt)
            if fmt == "%b %d":  # year was not in the string
                parsed = parsed.replace(year=date.today().year)
                return parsed.date(), parsed.date().isoformat(), True
            is_ambiguous = fmt == "%m/%d/%Y"  # could be day/month
            return parsed.date(), parsed.date().isoformat(), is_ambiguous
        except ValueError:
            continue

    return None, None, False


# ── Amount parsing ─────────────────────────────────────────────────────────────

def parse_amount(raw: str) -> tuple[Decimal | None, list[str]]:
    """Remove commas, validate, return Decimal. Flags precision issues."""
    warnings = []
    cleaned = str(raw).replace(",", "").strip()
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None, [f"Cannot parse amount: '{raw}'"]

    # Precision warning if > 2 decimal places
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if quantized != value:
        warnings.append(f"Amount {value} rounded to {quantized} (was {len(cleaned.split('.')[-1])} dp)")
    return quantized, warnings


# ── Split participants ─────────────────────────────────────────────────────────

def parse_participants(raw: str, group: Group) -> tuple[list[User], list[str]]:
    """Parse semicolon-separated names. Returns (resolved_users, warnings)."""
    if not raw or not raw.strip():
        return [], ["split_with is empty"]
    warnings = []
    users = []
    seen_ids = set()
    for name in raw.split(";"):
        user, w = resolve_user_name(name.strip(), group)
        warnings.extend(w)
        if user and user.id not in seen_ids:
            users.append(user)
            seen_ids.add(user.id)
    return users, warnings


# ── Duplicate detection ────────────────────────────────────────────────────────

def is_likely_duplicate(
    row_date: date,
    row_description: str,
    row_amount: Decimal,
    payer_name: str,
    seen_expenses: list[dict],
) -> bool:
    """
    True if we've already seen an expense with:
      - Same date ±0 days
      - Same payer (normalised)
      - Amount within ±1 INR
      - Description similarity ≥ 0.65
    """
    norm_payer = normalise_name(payer_name)
    for prev in seen_expenses:
        if prev["date"] != row_date:
            continue
        if normalise_name(prev["paid_by"]) != norm_payer:
            continue
        if abs(prev["amount"] - row_amount) > 1:
            continue
        ratio = SequenceMatcher(None, row_description.lower(), prev["description"].lower()).ratio()
        if ratio >= 0.65:
            return True
    return False


# ── Settlement detection ───────────────────────────────────────────────────────

def looks_like_settlement(description: str, split_type: str, participants: list[User]) -> bool:
    """
    A row is a settlement-disguised-as-expense when:
      - split_type is blank OR participants list has only 1 person
      - AND description contains payment keywords.
    """
    desc_lower = description.lower()
    has_keyword = any(kw in desc_lower for kw in SETTLEMENT_KEYWORDS)
    no_split = not split_type.strip()
    single_participant = len(participants) <= 1
    return has_keyword and (no_split or single_participant)


# ── Core import service ────────────────────────────────────────────────────────

@transaction.atomic
def process_csv_import(
    csv_content: str,
    uploaded_by: User,
    group: Group,
    file_name: str = "expenses_export.csv",
) -> ImportSession:
    """
    Main entry point.
    Parses CSV, detects all anomalies, imports valid rows, records every decision.
    Returns a fully populated ImportSession.
    """
    session = ImportSession.objects.create(
        uploaded_by=uploaded_by,
        uploaded_file_name=file_name,
        target_group=group,
        status=ImportSession.STATUS_PROCESSING,
        raw_csv=csv_content,
        usd_to_inr_rate=USD_TO_INR,
    )

    reader = csv.DictReader(io.StringIO(csv_content.strip()))
    rows = list(reader)
    session.total_rows = len(rows)

    seen_expenses: list[dict] = []
    imported = 0
    skipped = 0
    issues_created = 0

    def log_issue(
        row_num: int,
        anomaly_type: str,
        severity: str,
        action: str,
        notes: str,
        original: dict,
    ) -> None:
        nonlocal issues_created
        ImportIssue.objects.create(
            import_session=session,
            csv_row_number=row_num,
            anomaly_type=anomaly_type,
            severity=severity,
            original_data={k: str(v) for k, v in original.items()},
            action_taken=action,
            resolution_notes=notes,
        )
        issues_created += 1

    for row_idx, raw_row in enumerate(rows, start=2):  # row 1 is header
        row = {k.strip(): v.strip() if v else "" for k, v in raw_row.items()}
        original = dict(row)
        row_ok = True

        # ── 1. Date ────────────────────────────────────────────────────────────
        expense_date, iso_date, is_ambiguous = parse_date(row.get("date", ""))

        if expense_date is None:
            log_issue(row_idx, ImportIssue.ANOMALY_MISSING_FIELD, ImportIssue.SEVERITY_ERROR,
                      ImportIssue.ACTION_SKIPPED, f"Could not parse date '{row.get('date', '')}'", original)
            skipped += 1
            continue

        date_fmt_raw = row.get("date", "")
        if not date_fmt_raw.startswith("202"):  # Not ISO
            sev = ImportIssue.SEVERITY_WARNING if not is_ambiguous else ImportIssue.SEVERITY_WARNING
            atype = ImportIssue.ANOMALY_AMBIGUOUS_DATE if is_ambiguous else ImportIssue.ANOMALY_DATE_FORMAT
            note = f"Date '{date_fmt_raw}' interpreted as {iso_date}. "
            if is_ambiguous:
                note += "Year was absent or format is DD/MM/YYYY — assumed day-first (DD/MM). "
                note += "If this is wrong, the expense date is incorrect."
            log_issue(row_idx, atype, sev, ImportIssue.ACTION_NORMALIZED, note, original)

        # ── 2. Description ─────────────────────────────────────────────────────
        description = row.get("description", "").strip()
        if not description:
            log_issue(row_idx, ImportIssue.ANOMALY_MISSING_FIELD, ImportIssue.SEVERITY_ERROR,
                      ImportIssue.ACTION_SKIPPED, "description is blank", original)
            skipped += 1
            continue

        # ── 3. Amount ──────────────────────────────────────────────────────────
        amount, amount_warnings = parse_amount(row.get("amount", ""))
        if amount is None:
            log_issue(row_idx, ImportIssue.ANOMALY_INVALID_AMOUNT, ImportIssue.SEVERITY_ERROR,
                      ImportIssue.ACTION_SKIPPED, amount_warnings[0], original)
            skipped += 1
            continue

        if amount == Decimal("0"):
            log_issue(row_idx, ImportIssue.ANOMALY_ZERO_AMOUNT, ImportIssue.SEVERITY_WARNING,
                      ImportIssue.ACTION_SKIPPED, "Amount is zero — row skipped per policy.", original)
            skipped += 1
            continue

        if amount < Decimal("0"):
            log_issue(row_idx, ImportIssue.ANOMALY_NEGATIVE_AMOUNT, ImportIssue.SEVERITY_WARNING,
                      ImportIssue.ACTION_TREATED_AS_REFUND,
                      f"Negative amount {amount} treated as refund. "
                      "Policy: negative amounts represent refunds/reimbursements. "
                      "Row skipped — record refund manually as a settlement.",
                      original)
            skipped += 1
            continue

        for w in amount_warnings:
            log_issue(row_idx, ImportIssue.ANOMALY_DECIMAL_PRECISION, ImportIssue.SEVERITY_INFO,
                      ImportIssue.ACTION_ROUNDED, w, original)

        # ── 4. Currency conversion ─────────────────────────────────────────────
        currency = row.get("currency", "INR").upper().strip() or "INR"
        original_amount = amount
        original_currency = currency
        if currency == "USD":
            converted = (amount * USD_TO_INR).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            log_issue(row_idx, ImportIssue.ANOMALY_CURRENCY_CONVERSION, ImportIssue.SEVERITY_INFO,
                      ImportIssue.ACTION_CURRENCY_CONVERTED,
                      f"USD {original_amount} converted to INR {converted} "
                      f"using rate 1 USD = {USD_TO_INR} INR (fixed rate, import session #{session.id}). "
                      "Original currency and amount preserved in notes.",
                      original)
            amount = converted
            currency = "INR"
        elif currency not in ("INR",):
            log_issue(row_idx, ImportIssue.ANOMALY_CURRENCY_CONVERSION, ImportIssue.SEVERITY_WARNING,
                      ImportIssue.ACTION_SKIPPED,
                      f"Unsupported currency '{currency}'. Only INR and USD supported. Row skipped.",
                      original)
            skipped += 1
            continue

        # ── 5. Payer ───────────────────────────────────────────────────────────
        payer_raw = row.get("paid_by", "")
        payer, payer_warnings = resolve_user_name(payer_raw, group)

        for w in payer_warnings:
            is_norm = "normalised" in w.lower() or "fuzzy" in w.lower()
            if payer:
                log_issue(row_idx, ImportIssue.ANOMALY_NAME_NORMALIZATION, ImportIssue.SEVERITY_INFO,
                          ImportIssue.ACTION_NORMALIZED, w, original)
            else:
                log_issue(row_idx, ImportIssue.ANOMALY_UNKNOWN_USER, ImportIssue.SEVERITY_ERROR,
                          ImportIssue.ACTION_SKIPPED, w, original)

        if payer is None:
            skipped += 1
            continue

        # ── 6. Participants ────────────────────────────────────────────────────
        split_with_raw = row.get("split_with", "")
        participants, participant_warnings = parse_participants(split_with_raw, group)

        for w in participant_warnings:
            if "Unknown user" in w:
                log_issue(row_idx, ImportIssue.ANOMALY_UNKNOWN_USER, ImportIssue.SEVERITY_WARNING,
                          ImportIssue.ACTION_NORMALIZED,
                          f"{w}. Unknown participant excluded from split.", original)
            elif "normalised" in w.lower() or "fuzzy" in w.lower():
                log_issue(row_idx, ImportIssue.ANOMALY_NAME_NORMALIZATION, ImportIssue.SEVERITY_INFO,
                          ImportIssue.ACTION_NORMALIZED, w, original)

        # ── 7. Split type normalisation ────────────────────────────────────────
        split_type_raw = row.get("split_type", "").strip().lower()
        split_type = SPLIT_TYPE_ALIASES.get(split_type_raw, split_type_raw)

        if split_type_raw and split_type_raw not in KNOWN_SPLIT_TYPES and split_type in KNOWN_SPLIT_TYPES:
            log_issue(row_idx, ImportIssue.ANOMALY_SPLIT_TYPE_INVALID, ImportIssue.SEVERITY_INFO,
                      ImportIssue.ACTION_NORMALIZED,
                      f"Split type '{split_type_raw}' normalised to '{split_type}'.", original)

        if split_type and split_type not in KNOWN_SPLIT_TYPES:
            log_issue(row_idx, ImportIssue.ANOMALY_SPLIT_TYPE_INVALID, ImportIssue.SEVERITY_WARNING,
                      ImportIssue.ACTION_NORMALIZED,
                      f"Unknown split type '{split_type_raw}', defaulting to 'equal'.", original)
            split_type = "equal"

        if not split_type:
            split_type = "equal"

        # ── 8. Settlement detection ────────────────────────────────────────────
        if looks_like_settlement(description, row.get("split_type", ""), participants):
            log_issue(row_idx, ImportIssue.ANOMALY_SETTLEMENT_AS_EXPENSE, ImportIssue.SEVERITY_WARNING,
                      ImportIssue.ACTION_CONVERTED_SETTLEMENT,
                      f"Row looks like a settlement (description='{description}', "
                      f"split_type='{row.get('split_type', '')}', participants={len(participants)}). "
                      "Converted to Settlement record instead of Expense.",
                      original)
            # Create settlement if we have payer + 1 participant
            if len(participants) == 1 and participants[0] != payer:
                try:
                    from django.db import transaction as _txn
                    with _txn.atomic():
                        Settlement.objects.create(
                            group=group,
                            payer=payer,
                            receiver=participants[0],
                            amount=amount,
                            note=f"[CSV Import] {description}. Original date: {iso_date}.",
                        )
                    imported += 1
                except Exception as e:
                    log_issue(row_idx, ImportIssue.ANOMALY_SETTLEMENT_AS_EXPENSE, ImportIssue.SEVERITY_ERROR,
                              ImportIssue.ACTION_SKIPPED,
                              f"Could not create settlement: {e}", original)
                    skipped += 1
            else:
                skipped += 1
            continue

        # ── 9. Duplicate detection ─────────────────────────────────────────────
        if is_likely_duplicate(expense_date, description, amount, payer_raw, seen_expenses):
            log_issue(row_idx, ImportIssue.ANOMALY_DUPLICATE, ImportIssue.SEVERITY_WARNING,
                      ImportIssue.ACTION_FLAGGED_DUPLICATE,
                      f"Row matches a previously seen expense on {iso_date} by {payer_raw} "
                      f"for amount {original_amount} {original_currency}. "
                      "Flagged — not imported. Requires manual review.",
                      original)
            skipped += 1
            continue

        # ── 10. Validate participants non-empty ────────────────────────────────
        if not participants:
            log_issue(row_idx, ImportIssue.ANOMALY_MISSING_FIELD, ImportIssue.SEVERITY_ERROR,
                      ImportIssue.ACTION_SKIPPED,
                      "No valid participants resolved for split. Cannot import.", original)
            skipped += 1
            continue

        # Ensure payer is in participants (Splitwise rule)
        if payer not in participants:
            participants.insert(0, payer)
            log_issue(row_idx, ImportIssue.ANOMALY_PARTICIPANT_MISMATCH, ImportIssue.SEVERITY_INFO,
                      ImportIssue.ACTION_NORMALIZED,
                      f"Payer '{payer.first_name}' was not in split_with list. Added automatically.",
                      original)

        # ── 11. Build splits payload ───────────────────────────────────────────
        n = len(participants)
        per_person = (amount / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        remainder = amount - per_person * n

        splits_payload = []
        for i, u in enumerate(participants):
            share = per_person + (remainder if i == 0 else Decimal("0"))
            splits_payload.append({"user_id": u.id, "amount": str(share)})

        # ── 12. Build expense description (include original currency note) ─────
        final_description = description
        if original_currency == "USD":
            final_description = (
                f"{description} [Originally {original_currency} {original_amount}; "
                f"converted at 1 USD = {USD_TO_INR} INR]"
            )

        # ── 13. Create expense via service ────────────────────────────────────
        try:
            expense_data = {
                "description": final_description,
                "amount": str(amount),
                "category": infer_category(description),
                "expense_date": iso_date,
                "split_type": "unequal",  # always store as explicit splits
                "paid_by": payer.id,
                "splits": splits_payload,
            }
            expense_obj = _create_expense_direct(
                group=group,
                created_by=uploaded_by,
                data=expense_data,
                payer=payer,
                participants=participants,
                amount=amount,
                expense_date=expense_date,
                description=final_description,
                split_type=split_type,
            )
            seen_expenses.append({
                "date": expense_date,
                "description": description,
                "amount": amount,
                "paid_by": payer_raw,
                "expense_id": expense_obj.id,
            })
            imported += 1

        except Exception as exc:
            log_issue(row_idx, ImportIssue.ANOMALY_SPLIT_INCONSISTENCY, ImportIssue.SEVERITY_ERROR,
                      ImportIssue.ACTION_SKIPPED,
                      f"Failed to create expense: {exc}", original)
            skipped += 1

    # ── Finalise session ───────────────────────────────────────────────────────
    session.imported_rows = imported
    session.skipped_rows = skipped
    session.valid_rows = imported
    session.anomaly_count = issues_created
    session.status = ImportSession.STATUS_COMPLETED
    session.completed_at = timezone.now()
    session.save()

    return session


def _create_expense_direct(
    group: Group,
    created_by: User,
    data: dict,
    payer: User,
    participants: list[User],
    amount: Decimal,
    expense_date: date,
    description: str,
    split_type: str,
) -> Expense:
    """Create Expense + ExpenseSplit rows directly (bypassing full service validation for import)."""
    n = len(participants)
    per_person = (amount / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    remainder = amount - per_person * n

    with transaction.atomic():
        expense = Expense.objects.create(
            group=group,
            paid_by=payer,
            created_by=created_by,
            description=description,
            amount=amount,
            category=infer_category(description),
            expense_date=expense_date,
            split_type=split_type if split_type in KNOWN_SPLIT_TYPES else "equal",
        )
        for i, user in enumerate(participants):
            share = per_person + (remainder if i == 0 else Decimal("0"))
            ExpenseSplit.objects.create(
                expense=expense,
                user=user,
                amount=share,
            )
    return expense


def infer_category(description: str) -> str:
    """Keyword-based category inference."""
    desc = description.lower()
    if any(w in desc for w in ["rent", "electricity", "wifi", "maid", "cleaning", "cylinder"]):
        return "utilities"
    if any(w in desc for w in ["dinner", "lunch", "pizza", "groceries", "snack", "brunch", "birthday cake"]):
        return "food"
    if any(w in desc for w in ["flight", "scooter", "cab", "airport", "transport"]):
        return "transport"
    if any(w in desc for w in ["hotel", "villa", "booking", "accommodation"]):
        return "accommodation"
    if any(w in desc for w in ["movie", "entertainment", "party"]):
        return "entertainment"
    if any(w in desc for w in ["furniture", "deposit", "housewarming", "cleaning supplies"]):
        return "general"
    return "general"


def generate_import_report(session: ImportSession) -> dict[str, Any]:
    """Generate structured report for a completed ImportSession."""
    issues = session.issues.all()
    by_type: dict[str, int] = {}
    for issue in issues:
        by_type[issue.get_anomaly_type_display()] = by_type.get(issue.get_anomaly_type_display(), 0) + 1

    return {
        "session_id": session.id,
        "file": session.uploaded_file_name,
        "status": session.status,
        "total_rows": session.total_rows,
        "imported_rows": session.imported_rows,
        "skipped_rows": session.skipped_rows,
        "anomaly_count": session.anomaly_count,
        "usd_to_inr_rate": str(session.usd_to_inr_rate),
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "anomaly_breakdown": by_type,
        "issues": [
            {
                "row": i.csv_row_number,
                "type": i.get_anomaly_type_display(),
                "severity": i.severity,
                "action": i.get_action_taken_display(),
                "notes": i.resolution_notes,
                "original_data": i.original_data,
            }
            for i in issues
        ],
    }
