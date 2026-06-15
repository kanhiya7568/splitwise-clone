"""
Expense API custom permissions.

IsExpenseGroupMember — gate on all expense endpoints (active group member)
IsExpenseCreatorOrAdmin — gate on edit/delete (creator or group admin)
"""

from rest_framework.permissions import BasePermission

from apps.groups.models import GroupMembership


class IsExpenseGroupMember(BasePermission):
    """
    Object-level permission.
    obj must be an Expense instance.
    Grants access if request.user is an active member of expense.group.
    """
    message = "You must be an active member of this group."

    def has_object_permission(self, request, view, obj):
        return GroupMembership.objects.filter(
            group=obj.group, user=request.user, is_active=True
        ).exists()


class IsExpenseCreatorOrAdmin(BasePermission):
    """
    Object-level permission for edit/delete.
    obj must be an Expense instance.
    Grants access if request.user is the expense creator OR a group admin.
    """
    message = "Only the expense creator or a group admin can modify this expense."

    def has_object_permission(self, request, view, obj):
        if obj.created_by_id == request.user.id:
            return True
        return GroupMembership.objects.filter(
            group=obj.group,
            user=request.user,
            is_active=True,
            role=GroupMembership.ROLE_ADMIN,
        ).exists()
