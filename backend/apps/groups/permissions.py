"""
Group custom DRF permissions.

IsGroupMember  — allows any active group member (read/write)
IsGroupAdmin   — allows only active admins (admin-only actions)

Usage in views:
    permission_classes = [IsAuthenticated, IsGroupMember]
    permission_classes = [IsAuthenticated, IsGroupAdmin]

These are object-level permissions — they require the view to call
self.check_object_permissions(request, group_instance).
"""

from rest_framework.permissions import BasePermission

from apps.groups.models import GroupMembership


class IsGroupMember(BasePermission):
    """
    Grants access if the requesting user is an active member of the group.
    Applied at object level — the `obj` passed must be a Group instance.
    """

    message = "You must be an active member of this group to perform this action."

    def has_object_permission(self, request, view, obj):
        return GroupMembership.objects.filter(
            group=obj,
            user=request.user,
            is_active=True,
        ).exists()


class IsGroupAdmin(BasePermission):
    """
    Grants access only if the requesting user is an active admin of the group.
    Applied at object level — the `obj` passed must be a Group instance.
    """

    message = "Only group admins can perform this action."

    def has_object_permission(self, request, view, obj):
        return GroupMembership.objects.filter(
            group=obj,
            user=request.user,
            is_active=True,
            role=GroupMembership.ROLE_ADMIN,
        ).exists()
