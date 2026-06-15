"""
Group views — thin controllers.

All business logic is delegated to apps.groups.services.
Views are responsible only for:
  - Deserializing input
  - Calling the correct service function
  - Serializing output
  - Returning the correct HTTP status

Endpoints:
    GET    /api/groups/                   list user's groups
    POST   /api/groups/                   create group
    GET    /api/groups/{id}/              group detail
    PATCH  /api/groups/{id}/              rename / update group (admin only)
    DELETE /api/groups/{id}/              soft-delete group (admin only)
    GET    /api/groups/{id}/members/      list active members
    POST   /api/groups/{id}/invite/       invite by email (admin only)
    DELETE /api/groups/{id}/members/{uid}/ remove member (admin only)
"""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models import Group, GroupMembership
from apps.groups.permissions import IsGroupAdmin, IsGroupMember
from apps.groups.serializers import (
    GroupCreateSerializer,
    GroupInvitationSerializer,
    GroupMemberSerializer,
    GroupSerializer,
    GroupUpdateSerializer,
    InviteSerializer,
)
from apps.groups import services
from apps.groups.services import GroupServiceError


def _handle_service_error(exc: Exception) -> Response:
    """Convert service-layer exceptions to DRF responses."""
    if isinstance(exc, PermissionDenied):
        return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, Http404):
        return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, GroupServiceError):
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    raise exc  # unexpected — let Django 500 handler catch it


# ─────────────────────────────────────────────────────────────────────────────
# GET/POST /api/groups/
# ─────────────────────────────────────────────────────────────────────────────

class GroupListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return GroupCreateSerializer if self.request.method == "POST" else GroupSerializer

    def get_queryset(self):
        """Return only groups where the requesting user is an active member."""
        return (
            Group.objects.filter(
                memberships__user=self.request.user,
                memberships__is_active=True,
                is_deleted=False,
            )
            .distinct()
            .prefetch_related("memberships__user")
            .select_related("created_by")
            .order_by("-created_at")
        )

    def create(self, request, *args, **kwargs):
        serializer = GroupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        group = services.create_group(
            user=request.user,
            name=serializer.validated_data["name"],
            description=serializer.validated_data.get("description", ""),
        )
        return Response(
            GroupSerializer(group).data,
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────────────────────
# GET/PATCH/DELETE /api/groups/{id}/
# ─────────────────────────────────────────────────────────────────────────────

class GroupDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = GroupSerializer

    def get_object(self) -> Group:
        try:
            group = Group.objects.prefetch_related(
                "memberships__user"
            ).select_related("created_by").get(
                pk=self.kwargs["pk"], is_deleted=False
            )
        except Group.DoesNotExist:
            raise Http404("Group not found.")
        self.check_object_permissions(self.request, group)
        return group

    def check_object_permissions(self, request, obj):
        # Enforce IsGroupMember at the object level
        if not GroupMembership.objects.filter(
            group=obj, user=request.user, is_active=True
        ).exists():
            from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
            raise DRFPermissionDenied("You are not an active member of this group.")


class GroupUpdateView(generics.UpdateAPIView):
    """PATCH /api/groups/{id}/ — rename or update description (admin only)."""

    permission_classes = [IsAuthenticated]
    http_method_names = ["patch"]

    def _get_group(self) -> Group:
        try:
            group = Group.objects.get(pk=self.kwargs["pk"], is_deleted=False)
        except Group.DoesNotExist:
            raise Http404("Group not found.")
        return group

    def patch(self, request, *args, **kwargs):
        group = self._get_group()
        serializer = GroupUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            updated = services.update_group(
                group=group,
                requesting_user=request.user,
                name=serializer.validated_data.get("name"),
                description=serializer.validated_data.get("description"),
            )
        except (PermissionDenied, GroupServiceError) as exc:
            return _handle_service_error(exc)
        return Response(GroupSerializer(updated).data)


class GroupDeleteView(APIView):
    """DELETE /api/groups/{id}/ — soft-delete group (admin only, settled balances required)."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        try:
            group = Group.objects.get(pk=kwargs["pk"], is_deleted=False)
        except Group.DoesNotExist:
            return Response({"error": "Group not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            services.delete_group(group=group, requesting_user=request.user)
        except (PermissionDenied, GroupServiceError) as exc:
            return _handle_service_error(exc)
        return Response({"message": "Group deleted successfully."}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/groups/{id}/members/
# ─────────────────────────────────────────────────────────────────────────────

class GroupMembersView(generics.ListAPIView):
    """List active members of a group. Accessible by any active member."""

    permission_classes = [IsAuthenticated]
    serializer_class = GroupMemberSerializer

    def get_queryset(self):
        try:
            group = Group.objects.get(pk=self.kwargs["pk"], is_deleted=False)
        except Group.DoesNotExist:
            raise Http404("Group not found.")
        # Verify requester is a member
        if not GroupMembership.objects.filter(
            group=group, user=self.request.user, is_active=True
        ).exists():
            from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
            raise DRFPermissionDenied("You are not a member of this group.")
        return (
            GroupMembership.objects.filter(group=group, is_active=True)
            .select_related("user")
            .order_by("joined_at")
        )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/groups/{id}/invite/
# ─────────────────────────────────────────────────────────────────────────────

class GroupInviteView(APIView):
    """Invite a user by email (admin only)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            group = Group.objects.get(pk=kwargs["pk"], is_deleted=False)
        except Group.DoesNotExist:
            return Response({"error": "Group not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = InviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = services.invite_user(
                group=group,
                email=serializer.validated_data["email"],
                invited_by=request.user,
            )
        except (PermissionDenied, GroupServiceError) as exc:
            return _handle_service_error(exc)

        action = result["action"]
        if action in ("added", "readded"):
            return Response(
                {
                    "action": action,
                    "member": GroupMemberSerializer(result["membership"]).data,
                },
                status=status.HTTP_201_CREATED,
            )
        # invited — pending invitation created
        return Response(
            {
                "action": "invited",
                "invitation": GroupInvitationSerializer(result["invitation"]).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/groups/{id}/members/{uid}/
# ─────────────────────────────────────────────────────────────────────────────

class RemoveMemberView(APIView):
    """Remove an active member from a group (admin only)."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        try:
            group = Group.objects.get(pk=kwargs["pk"], is_deleted=False)
        except Group.DoesNotExist:
            return Response({"error": "Group not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            services.remove_member(
                group=group,
                target_user_id=kwargs["uid"],
                requesting_user=request.user,
            )
        except (PermissionDenied, Http404, GroupServiceError) as exc:
            return _handle_service_error(exc)

        return Response({"message": "Member removed successfully."}, status=status.HTTP_200_OK)
