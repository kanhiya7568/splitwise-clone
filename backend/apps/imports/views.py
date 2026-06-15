"""
Import API views.

POST /api/imports/upload/              — Upload CSV, get session + report
GET  /api/imports/                     — List all import sessions for current user
GET  /api/imports/{id}/               — Session detail with all issues
GET  /api/imports/{id}/report/        — JSON import report
"""

from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.groups.models import Group
from .models import ImportSession
from .serializers import ImportSessionListSerializer, ImportSessionSerializer
from .services import generate_import_report, process_csv_import


class CSVUploadView(APIView):
    """
    POST /api/imports/upload/

    Body (multipart/form-data):
      file     — the CSV file
      group_id — target group ID

    Returns the full ImportSession including all detected issues.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request) -> Response:
        csv_file = request.FILES.get("file")
        group_id = request.data.get("group_id")

        if not csv_file:
            return Response({"error": "No file provided. Send 'file' as multipart/form-data."}, status=400)
        if not group_id:
            return Response({"error": "group_id is required."}, status=400)
        if not csv_file.name.endswith(".csv"):
            return Response({"error": "Only .csv files are accepted."}, status=400)

        try:
            group = Group.objects.get(pk=group_id)
        except Group.DoesNotExist:
            return Response({"error": f"Group {group_id} not found."}, status=404)

        # Check requesting user is a member
        if not group.memberships.filter(user=request.user, is_active=True).exists():
            return Response({"error": "You are not an active member of this group."}, status=403)

        try:
            csv_content = csv_file.read().decode("utf-8-sig")  # strip BOM if present
        except UnicodeDecodeError:
            return Response({"error": "File must be UTF-8 encoded."}, status=400)

        try:
            session = process_csv_import(
                csv_content=csv_content,
                uploaded_by=request.user,
                group=group,
                file_name=csv_file.name,
            )
        except Exception as exc:
            return Response({"error": f"Import failed: {exc}"}, status=500)

        serializer = ImportSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ImportSessionListView(ListAPIView):
    """GET /api/imports/ — List sessions for the current user."""
    permission_classes = [IsAuthenticated]
    serializer_class = ImportSessionListSerializer

    def get_queryset(self):
        return ImportSession.objects.filter(uploaded_by=self.request.user).order_by("-started_at")


class ImportSessionDetailView(RetrieveAPIView):
    """GET /api/imports/{id}/ — Session detail with all issues."""
    permission_classes = [IsAuthenticated]
    serializer_class = ImportSessionSerializer

    def get_queryset(self):
        return ImportSession.objects.filter(uploaded_by=self.request.user)


class ImportReportView(APIView):
    """GET /api/imports/{id}/report/ — Structured JSON import report."""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, pk: int) -> Response:
        try:
            session = ImportSession.objects.get(pk=pk, uploaded_by=request.user)
        except ImportSession.DoesNotExist:
            return Response({"error": "Import session not found."}, status=404)

        report = generate_import_report(session)
        return Response(report)
