from django.urls import path

from .views import (
    InitiateTransferView,
    SimulateTransferView,
    StripeWebhookView,
    TransferStatusView,
)

urlpatterns = [
    path("simulate", SimulateTransferView.as_view(), name="transfer-simulate"),
    path("initiate", InitiateTransferView.as_view(), name="transfer-initiate"),
    path("stripe/webhook", StripeWebhookView.as_view(), name="transfer-stripe-webhook"),
    path("<str:id>/status", TransferStatusView.as_view(), name="transfer-status"),
]
