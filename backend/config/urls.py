"""
Root URL configuration.

All API routes are prefixed with /api/.
The health check endpoint at /health/ requires no authentication and is used
by Render for uptime monitoring and by UptimeRobot to prevent cold starts.
"""

from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.http import require_GET


@require_GET
def health_check(request):
    """
    GET /health/

    Public endpoint — no authentication required.
    Returns HTTP 200 with a JSON body confirming the service is running.

    Used by:
      - Render.com health check (deployment readiness)
      - UptimeRobot ping (prevents free-tier cold starts)
    """
    return JsonResponse(
        {
            "status": "ok",
            "service": "splitwise-clone-api",
            "version": "1.0.0",
        }
    )


urlpatterns = [
    # ── Public ────────────────────────────────────────────────────────────────
    path("health/", health_check, name="health_check"),

    # ── Admin ─────────────────────────────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ── Authentication ────────────────────────────────────────────────────────
    # POST /api/auth/register/
    # POST /api/auth/login/
    # POST /api/auth/logout/
    # POST /api/auth/token/refresh/
    # GET  /api/auth/me/
    path("api/auth/", include("apps.authentication.urls")),

    # ── Groups ────────────────────────────────────────────────────────────────
    # GET/POST  /api/groups/
    # GET/PATCH/DELETE /api/groups/{id}/
    # GET  /api/groups/{id}/members/
    # POST /api/groups/{id}/invite/
    # DELETE /api/groups/{id}/members/{uid}/
    path("api/", include("apps.groups.urls")),

    # ── Expenses ──────────────────────────────────────────────────────────────
    # GET/POST /api/groups/{gid}/expenses/
    # GET/PATCH/DELETE /api/groups/{gid}/expenses/{id}/
    path("api/", include("apps.expenses.urls")),

    # ── Balances ──────────────────────────────────────────────────────────────
    # GET /api/groups/{gid}/balances/
    # GET /api/balances/
    path("api/", include("apps.balances.urls")),

    # ── Settlements ───────────────────────────────────────────────────────────
    # GET/POST /api/groups/{gid}/settlements/
    # GET/PATCH/DELETE /api/groups/{gid}/settlements/{id}/
    path("api/", include("apps.settlements.urls")),

    # ── Chat (REST history + delete) ──────────────────────────────────────────
    # GET    /api/expenses/{eid}/messages/
    # DELETE /api/expenses/{eid}/messages/{id}/
    path("api/", include("apps.chat.urls")),

    # ── CSV Imports ────────────────────────────────────────────────────────────
    # POST /api/imports/upload/
    # GET  /api/imports/
    # GET  /api/imports/{id}/
    # GET  /api/imports/{id}/report/
    path("api/", include("apps.imports.urls")),
]
