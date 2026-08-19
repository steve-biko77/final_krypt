from django.urls import path

from .views import (
    BeneficiariesView,
    BeneficiaryDetailView,
    CancelTransferView,
    InitiateTransferView,
    MyTransfersView,
    SimulateTransferView,
    StripeWebhookView,
    TransferStatusView,
)

urlpatterns = [
    path("simulate", SimulateTransferView.as_view(), name="transfer-simulate"),
    path("initiate", InitiateTransferView.as_view(), name="transfer-initiate"),
    path("stripe/webhook", StripeWebhookView.as_view(), name="transfer-stripe-webhook"),
    path("mine", MyTransfersView.as_view(), name="transfer-mine"),
    path("beneficiaries", BeneficiariesView.as_view(), name="transfer-beneficiaries"),
    path(
        "beneficiaries/<str:id>",
        BeneficiaryDetailView.as_view(),
        name="transfer-beneficiary-detail",
    ),
    path("<str:id>/status", TransferStatusView.as_view(), name="transfer-status"),
    path("<str:id>/cancel", CancelTransferView.as_view(), name="transfer-cancel"),
]
