"""
Settlement URL patterns.

Mounted under /api/ in config/urls.py.

Full URL table:
    GET    /api/groups/{gid}/settlements/          list
    POST   /api/groups/{gid}/settlements/          create
    GET    /api/groups/{gid}/settlements/{sid}/    retrieve
    PATCH  /api/groups/{gid}/settlements/{sid}/edit/    edit (participant only)
    DELETE /api/groups/{gid}/settlements/{sid}/delete/  soft-delete (participant only)
"""

from django.urls import path

from apps.settlements.views import (
    SettlementDeleteView,
    SettlementDetailView,
    SettlementListCreateView,
    SettlementUpdateView,
)

urlpatterns = [
    path(
        "groups/<int:gid>/settlements/",
        SettlementListCreateView.as_view(),
        name="settlement_list_create",
    ),
    path(
        "groups/<int:gid>/settlements/<int:sid>/",
        SettlementDetailView.as_view(),
        name="settlement_detail",
    ),
    path(
        "groups/<int:gid>/settlements/<int:sid>/edit/",
        SettlementUpdateView.as_view(),
        name="settlement_update",
    ),
    path(
        "groups/<int:gid>/settlements/<int:sid>/delete/",
        SettlementDeleteView.as_view(),
        name="settlement_delete",
    ),
]
