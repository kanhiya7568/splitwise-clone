"""
Expense URL patterns.

Mounted at /api/ in config/urls.py.

Full URL table:
    GET    /api/groups/{gid}/expenses/           list + filter
    POST   /api/groups/{gid}/expenses/           create
    GET    /api/groups/{gid}/expenses/{eid}/     retrieve
    PATCH  /api/groups/{gid}/expenses/{eid}/edit/    update (creator/admin)
    DELETE /api/groups/{gid}/expenses/{eid}/delete/  soft-delete (creator/admin)
"""

from django.urls import path

from apps.expenses.views import (
    ExpenseDeleteView,
    ExpenseDetailView,
    ExpenseListCreateView,
    ExpenseUpdateView,
)

urlpatterns = [
    path(
        "groups/<int:gid>/expenses/",
        ExpenseListCreateView.as_view(),
        name="expense_list_create",
    ),
    path(
        "groups/<int:gid>/expenses/<int:eid>/",
        ExpenseDetailView.as_view(),
        name="expense_detail",
    ),
    path(
        "groups/<int:gid>/expenses/<int:eid>/edit/",
        ExpenseUpdateView.as_view(),
        name="expense_update",
    ),
    path(
        "groups/<int:gid>/expenses/<int:eid>/delete/",
        ExpenseDeleteView.as_view(),
        name="expense_delete",
    ),
]
