from django.urls import path
from .views import CSVUploadView, ImportSessionDetailView, ImportSessionListView, ImportReportView

urlpatterns = [
    path("imports/", ImportSessionListView.as_view(), name="import-list"),
    path("imports/upload/", CSVUploadView.as_view(), name="import-upload"),
    path("imports/<int:pk>/", ImportSessionDetailView.as_view(), name="import-detail"),
    path("imports/<int:pk>/report/", ImportReportView.as_view(), name="import-report"),
]
