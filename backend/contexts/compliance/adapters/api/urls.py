from django.urls import path

from .views import KYCAdminListView, KYCReviewView, KYCStatusView, KYCSubmitView

urlpatterns = [
    path("submit", KYCSubmitView.as_view(), name="kyc-submit"),
    path("status", KYCStatusView.as_view(), name="kyc-status"),
    path("review/<str:doc_id>", KYCReviewView.as_view(), name="kyc-review"),
    path("admin/list", KYCAdminListView.as_view(), name="kyc-admin-list"),
]
