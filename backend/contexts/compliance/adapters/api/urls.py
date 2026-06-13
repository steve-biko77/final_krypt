from django.urls import path

from .views import KYCReviewView, KYCStatusView, KYCSubmitView

urlpatterns = [
    path("submit", KYCSubmitView.as_view(), name="kyc-submit"),
    path("status", KYCStatusView.as_view(), name="kyc-status"),
    path("review/<str:doc_id>", KYCReviewView.as_view(), name="kyc-review"),
]
