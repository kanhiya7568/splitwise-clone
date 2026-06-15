"""
Expense views — thin controllers.

All business logic delegated to apps.expenses.services (Module 5A).
Balance hooks are already wired inside services; views add nothing financial.

Endpoints:
    GET    /api/groups/{gid}/expenses/          list (filtered, paginated)
    POST   /api/groups/{gid}/expenses/          create expense
    GET    /api/groups/{gid}/expenses/{eid}/    retrieve expense
    PATCH  /api/groups/{gid}/expenses/{eid}/    update expense
    DELETE /api/groups/{gid}/expenses/{eid}/    soft-delete expense
"""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.expenses import services
from apps.expenses.filters import apply_expense_filters
from apps.expenses.models import Expense
from apps.expenses.permissions import IsExpenseCreatorOrAdmin, IsExpenseGroupMember
from apps.expenses.serializers import (
    ExpenseCreateSerializer,
    ExpenseSerializer,
    ExpenseUpdateSerializer,
)
from apps.expenses.services import ExpenseServiceError
from apps.groups.models import Group, GroupMembership


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _get_group_or_404(pk: int) -> Group:
    try:
        return Group.objects.get(pk=pk, is_deleted=False)
    except Group.DoesNotExist:
        raise Http404("Group not found.")


def _get_expense_or_404(pk: int, group: Group) -> Expense:
    try:
        return (
            Expense.objects
            .select_related("paid_by", "created_by", "group")
            .prefetch_related("splits__user")
            .get(pk=pk, group=group, is_deleted=False)
        )
    except Expense.DoesNotExist:
        raise Http404("Expense not found.")


def _require_group_member(group: Group, user) -> None:
    if not GroupMembership.objects.filter(group=group, user=user, is_active=True).exists():
        raise PermissionDenied("You must be an active member of this group.")


def _handle_error(exc: Exception) -> Response:
    if isinstance(exc, PermissionDenied):
        return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, Http404):
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, ExpenseServiceError):
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    raise exc


class _ExpensePaginator(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ─────────────────────────────────────────────────────────────────────────────
# GET/POST /api/groups/{gid}/expenses/
# ─────────────────────────────────────────────────────────────────────────────

class ExpenseListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, gid: int):
        group = _get_group_or_404(gid)
        try:
            qs = services.get_expense_history(group, request.user)
        except (PermissionDenied, ExpenseServiceError) as exc:
            return _handle_error(exc)

        qs = apply_expense_filters(qs, request)
        paginator = _ExpensePaginator()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(ExpenseSerializer(page, many=True).data)

    def post(self, request, gid: int):
        group = _get_group_or_404(gid)
        serializer = ExpenseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            expense, _ = services.create_expense(**serializer.to_service_args(group, request.user))
        except (PermissionDenied, ExpenseServiceError) as exc:
            return _handle_error(exc)
        return Response(
            ExpenseSerializer(expense).data,
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/groups/{gid}/expenses/{eid}/
# ─────────────────────────────────────────────────────────────────────────────

class ExpenseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, gid: int, eid: int):
        group = _get_group_or_404(gid)
        try:
            _require_group_member(group, request.user)
        except PermissionDenied as exc:
            return _handle_error(exc)
        expense = _get_expense_or_404(eid, group)
        return Response(ExpenseSerializer(expense).data)


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/groups/{gid}/expenses/{eid}/
# ─────────────────────────────────────────────────────────────────────────────

class ExpenseUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, gid: int, eid: int):
        group = _get_group_or_404(gid)
        expense = _get_expense_or_404(eid, group)

        # Check creator-or-admin permission
        perm = IsExpenseCreatorOrAdmin()
        if not perm.has_object_permission(request, self, expense):
            return Response({"error": perm.message}, status=status.HTTP_403_FORBIDDEN)

        serializer = ExpenseUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            updated, _ = services.update_expense(
                expense, request.user, **serializer.to_service_args(expense)
            )
        except (PermissionDenied, ExpenseServiceError) as exc:
            return _handle_error(exc)
        return Response(ExpenseSerializer(updated).data)


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/groups/{gid}/expenses/{eid}/
# ─────────────────────────────────────────────────────────────────────────────

class ExpenseDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, gid: int, eid: int):
        group = _get_group_or_404(gid)
        expense = _get_expense_or_404(eid, group)

        perm = IsExpenseCreatorOrAdmin()
        if not perm.has_object_permission(request, self, expense):
            return Response({"error": perm.message}, status=status.HTTP_403_FORBIDDEN)

        try:
            services.delete_expense(expense, request.user)
        except (PermissionDenied, ExpenseServiceError) as exc:
            return _handle_error(exc)
        return Response({"message": "Expense deleted."}, status=status.HTTP_200_OK)
