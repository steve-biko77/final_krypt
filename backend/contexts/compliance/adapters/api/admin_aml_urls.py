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

# NB : les chemins littéraux (escalated, escalated/<id>, escalated/<id>/decide,
# history) doivent être déclarés AVANT les motifs génériques <str:id>/... —
# sinon ces derniers les capturent en premier (Django essaie les patterns dans
# l'ordre et <str:id> matche n'importe quel segment, y compris "escalated").
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
    path("history", AMLAdminHistoryView.as_view(), name="admin-aml-history"),
    path("<str:id>", AMLAdminDetailView.as_view(), name="admin-aml-detail"),
    path(
        "<str:id>/request-docs",
        AMLAdminRequestDocsView.as_view(),
        name="admin-aml-request-docs",
    ),
    path("<str:id>/decide", AMLAdminDecideView.as_view(), name="admin-aml-decide"),
]
