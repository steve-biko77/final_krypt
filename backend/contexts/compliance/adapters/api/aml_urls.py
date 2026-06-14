from django.urls import path

from .aml_views import AMLResultView, AMLScoreView

urlpatterns = [
    path("score", AMLScoreView.as_view(), name="aml-score"),
    path("result/<str:transfer_id>", AMLResultView.as_view(), name="aml-result"),
]
