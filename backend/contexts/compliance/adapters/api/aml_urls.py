from django.urls import path

from .aml_views import AMLResubmitDocsView, AMLResultView, AMLScoreView

urlpatterns = [
    path("score", AMLScoreView.as_view(), name="aml-score"),
    path("result/<str:transfer_id>", AMLResultView.as_view(), name="aml-result"),
    path(
        "<str:transfer_id>/resubmit-docs",
        AMLResubmitDocsView.as_view(),
        name="aml-resubmit-docs",
    ),
]
