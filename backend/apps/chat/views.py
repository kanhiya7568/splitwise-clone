"""
Chat REST views.

GET /api/expenses/{expense_id}/messages/
    Returns paginated message history for an expense.
    Only active group members may access.
    Soft-deleted messages are included (content masked to "[deleted]").
"""

from django.http import Http404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import Message
from apps.chat.serializers import MessageSerializer
from apps.expenses.models import Expense
from apps.groups.models import GroupMembership


class MessageHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, expense_id: int):
        # Fetch expense
        try:
            expense = Expense.objects.select_related("group").get(
                pk=expense_id, is_deleted=False
            )
        except Expense.DoesNotExist:
            return Response({"error": "Expense not found."}, status=404)

        # Check group membership
        is_member = GroupMembership.objects.filter(
            group=expense.group,
            user=request.user,
            is_active=True,
        ).exists()
        if not is_member:
            return Response(
                {"error": "You must be an active member of this group."},
                status=403,
            )

        qs = (
            Message.objects
            .filter(expense=expense)
            .select_related("sender")
            .order_by("created_at")  # chronological
        )

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            MessageSerializer(page, many=True).data
        )
