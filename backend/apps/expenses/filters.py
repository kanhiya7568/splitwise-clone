"""
Expense query filters.

apply_expense_filters(queryset, request) reads GET query parameters
and applies filters to the provided queryset.

Supported query params:
    date_from   YYYY-MM-DD  expense_date >= date_from
    date_to     YYYY-MM-DD  expense_date <= date_to
    category    str         exact match on Expense.category
    created_by  int         user ID of the expense creator
    split_type  str         equal | unequal | percentage | shares

All filters are optional and additive (AND logic).
Invalid or unrecognised values are silently ignored.
"""

from datetime import datetime

from apps.expenses.models import Expense


def apply_expense_filters(queryset, request):
    """
    Apply URL query-param filters to an Expense queryset.

    Args:
        queryset: An Expense QuerySet (already filtered by group/is_deleted).
        request:  The DRF request object.

    Returns:
        Filtered QuerySet.
    """
    params = request.query_params

    # date_from
    date_from = params.get("date_from")
    if date_from:
        try:
            parsed = datetime.strptime(date_from, "%Y-%m-%d").date()
            queryset = queryset.filter(expense_date__gte=parsed)
        except ValueError:
            pass  # invalid date ignored

    # date_to
    date_to = params.get("date_to")
    if date_to:
        try:
            parsed = datetime.strptime(date_to, "%Y-%m-%d").date()
            queryset = queryset.filter(expense_date__lte=parsed)
        except ValueError:
            pass

    # category
    category = params.get("category")
    valid_categories = [c[0] for c in Expense.CATEGORY_CHOICES]
    if category and category in valid_categories:
        queryset = queryset.filter(category=category)

    # created_by
    created_by = params.get("created_by")
    if created_by:
        try:
            queryset = queryset.filter(created_by_id=int(created_by))
        except (ValueError, TypeError):
            pass

    # split_type
    split_type = params.get("split_type")
    valid_splits = [s[0] for s in Expense.SPLIT_CHOICES]
    if split_type and split_type in valid_splits:
        queryset = queryset.filter(split_type=split_type)

    return queryset
