from django.urls import path

from .views import SimulateTransferView

urlpatterns = [
    path("simulate", SimulateTransferView.as_view(), name="transfer-simulate"),
]
