from django.urls import path

from .admin_aml_views import (
    AMLAdminDecideView,
    AMLAdminDetailView,
    AMLAdminEscalatedDecideView,
    AMLAdminEscalatedDetailView,
    AMLAdminEscalatedListView,
    AMLAdminHistoryView,
    AMLAdminPendingListView,
    AMLAdminRequestDocsView,
)
from .admin_daily_report_views import (
    AMLAdminDailyReportArchiveView,
    AMLAdminDailyReportExportCSVView,
    AMLAdminDailyReportView,
)
from .admin_hard_block_views import (
    AMLAdminHardBlockedDocumentView,
    AMLAdminHardBlockedFreezeAccountView,
    AMLAdminHardBlockedGenerateTracfinReportView,
    AMLAdminHardBlockedListView,
    AMLAdminHardBlockedTracfinReportDownloadView,
)

# NB : les chemins littéraux (escalated, escalated/<id>, escalated/<id>/decide,
# hard-blocked, hard-blocked/<id>/..., daily-report, history) doivent être
# déclarés AVANT les motifs génériques <str:id>/... — sinon ces derniers les
# capturent en premier (Django essaie les patterns dans l'ordre et <str:id>
# matche n'importe quel segment, y compris "escalated"/"hard-blocked").
urlpatterns = [
    path("pending", AMLAdminPendingListView.as_view(), name="admin-aml-pending"),
    path(
        "escalated", AMLAdminEscalatedListView.as_view(), name="admin-aml-escalated-list"
    ),
    path(
        "escalated/<str:id>",
        AMLAdminEscalatedDetailView.as_view(),
        name="admin-aml-escalated-detail",
    ),
    path(
        "escalated/<str:id>/decide",
        AMLAdminEscalatedDecideView.as_view(),
        name="admin-aml-escalated-decide",
    ),
    path(
        "hard-blocked",
        AMLAdminHardBlockedListView.as_view(),
        name="admin-aml-hard-blocked-list",
    ),
    path(
        "hard-blocked/<str:id>/document",
        AMLAdminHardBlockedDocumentView.as_view(),
        name="admin-aml-hard-blocked-document",
    ),
    path(
        "hard-blocked/<str:id>/freeze-account",
        AMLAdminHardBlockedFreezeAccountView.as_view(),
        name="admin-aml-hard-blocked-freeze-account",
    ),
    path(
        "hard-blocked/<str:id>/generate-tracfin-report",
        AMLAdminHardBlockedGenerateTracfinReportView.as_view(),
        name="admin-aml-hard-blocked-generate-tracfin-report",
    ),
    path(
        "hard-blocked/<str:id>/tracfin-report",
        AMLAdminHardBlockedTracfinReportDownloadView.as_view(),
        name="admin-aml-hard-blocked-tracfin-report-download",
    ),
    path(
        "daily-report",
        AMLAdminDailyReportView.as_view(),
        name="admin-aml-daily-report",
    ),
    path(
        "daily-report/export-csv",
        AMLAdminDailyReportExportCSVView.as_view(),
        name="admin-aml-daily-report-export-csv",
    ),
    path(
        "daily-report/archive",
        AMLAdminDailyReportArchiveView.as_view(),
        name="admin-aml-daily-report-archive",
    ),
    path("history", AMLAdminHistoryView.as_view(), name="admin-aml-history"),
    path("<str:id>", AMLAdminDetailView.as_view(), name="admin-aml-detail"),
    path(
        "<str:id>/request-docs",
        AMLAdminRequestDocsView.as_view(),
        name="admin-aml-request-docs",
    ),
    path("<str:id>/decide", AMLAdminDecideView.as_view(), name="admin-aml-decide"),
]
