"""
Group URL patterns.

Mounted at /api/ in config/urls.py.

Full URL table:
    GET    /api/groups/                       GroupListCreateView  (list)
    POST   /api/groups/                       GroupListCreateView  (create)
    GET    /api/groups/{id}/                  GroupDetailView      (retrieve)
    PATCH  /api/groups/{id}/                  GroupUpdateView      (rename/update)
    DELETE /api/groups/{id}/                  GroupDeleteView      (soft-delete)
    GET    /api/groups/{id}/members/          GroupMembersView     (list members)
    POST   /api/groups/{id}/invite/           GroupInviteView      (invite by email)
    DELETE /api/groups/{id}/members/{uid}/    RemoveMemberView     (remove member)
"""

from django.urls import path

from apps.groups.views import (
    GroupDeleteView,
    GroupDetailView,
    GroupInviteView,
    GroupListCreateView,
    GroupMembersView,
    GroupUpdateView,
    RemoveMemberView,
)

urlpatterns = [
    path("groups/", GroupListCreateView.as_view(), name="group_list_create"),
    path("groups/<int:pk>/", GroupDetailView.as_view(), name="group_detail"),
    path("groups/<int:pk>/update/", GroupUpdateView.as_view(), name="group_update"),
    path("groups/<int:pk>/delete/", GroupDeleteView.as_view(), name="group_delete"),
    path("groups/<int:pk>/members/", GroupMembersView.as_view(), name="group_members"),
    path("groups/<int:pk>/invite/", GroupInviteView.as_view(), name="group_invite"),
    path("groups/<int:pk>/members/<int:uid>/", RemoveMemberView.as_view(), name="group_remove_member"),
]
