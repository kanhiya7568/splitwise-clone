"""
Settlement views — thin controllers.

All business logic delegated to settlements.services.

Endpoints:
    GET    /api/groups/{gid}/settlements/          list settlements
    POST   /api/groups/{gid}/settlements/          create settlement
    GET    /api/groups/{gid}/settlements/{sid}/    retrieve settlement
    PATCH  /api/groups/{gid}/settlements/{sid}/    edit settlement
    DELETE /api/groups/{gid}/settlements/{sid}/    delete settlement
"""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models import Group
from apps.settlements import services
from apps.settlements.models import Settlement
from apps.settlements.serializers import (
    SettlementCreateSerializer,
    SettlementSerializer,
    SettlementUpdateSerializer,
)
from apps.settlements.services import SettlementServiceError


def _get_group_or_404(pk: int) -> Group:
    try:
        return Group.objects.get(pk=pk, is_deleted=False)
    except Group.DoesNotExist:
        raise Http404("Group not found.")


def _get_settlement_or_404(pk: int) -> Settlement:
    try:
        return Settlement.objects.select_related(
            "payer", "receiver", "created_by", "group"
        ).get(pk=pk)
    except Settlement.DoesNotExist:
        raise Http404("Settlement not found.")


def _handle_error(exc: Exception) -> Response:
    if isinstance(exc, PermissionDenied):
        return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, Http404):
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, SettlementServiceError):
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    raise exc


# ─────────────────────────────────────────────────────────────────────────────
# GET/POST /api/groups/{gid}/settlements/
# ─────────────────────────────────────────────────────────────────────────────

class SettlementListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, gid: int):
        group = _get_group_or_404(gid)
        try:
            qs = services.get_settlement_history(group, request.user)
        except (PermissionDenied, SettlementServiceError) as exc:
            return _handle_error(exc)

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(SettlementSerializer(page, many=True).data)

    def post(self, request, gid: int):
        group = _get_group_or_404(gid)
        serializer = SettlementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            settlement = services.create_settlement(
                **serializer.to_service_args(group, request.user)
            )
        except (PermissionDenied, SettlementServiceError) as exc:
            return _handle_error(exc)
        return Response(SettlementSerializer(settlement).data, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/groups/{gid}/settlements/{sid}/
# ─────────────────────────────────────────────────────────────────────────────

class SettlementDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, gid: int, sid: int):
        group = _get_group_or_404(gid)
        settlement = _get_settlement_or_404(sid)
        if settlement.group_id != group.pk:
            return Response({"error": "Settlement not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            services._require_active_member(group, request.user)
        except PermissionDenied as exc:
            return _handle_error(exc)
        return Response(SettlementSerializer(settlement).data)


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/groups/{gid}/settlements/{sid}/
# ─────────────────────────────────────────────────────────────────────────────

class SettlementUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, gid: int, sid: int):
        _get_group_or_404(gid)
        settlement = _get_settlement_or_404(sid)
        serializer = SettlementUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            updated = services.update_settlement(
                settlement, request.user, **serializer.to_service_args()
            )
        except (PermissionDenied, SettlementServiceError) as exc:
            return _handle_error(exc)
        return Response(SettlementSerializer(updated).data)


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/groups/{gid}/settlements/{sid}/
# ─────────────────────────────────────────────────────────────────────────────

class SettlementDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, gid: int, sid: int):
        _get_group_or_404(gid)
        settlement = _get_settlement_or_404(sid)
        try:
            services.delete_settlement(settlement, request.user)
        except (PermissionDenied, SettlementServiceError) as exc:
            return _handle_error(exc)
        return Response({"message": "Settlement deleted."}, status=status.HTTP_200_OK)
