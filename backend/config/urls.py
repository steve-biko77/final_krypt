from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from contexts.compliance.adapters.api.admin_stats_views import AdminStatsView

urlpatterns = [
    path("api/auth/", include("contexts.identity.adapters.api.urls")),
    path("api/kyc/", include("contexts.compliance.adapters.api.urls")),
    path("api/aml/", include("contexts.compliance.adapters.api.aml_urls")),
    path("api/admin/aml/", include("contexts.compliance.adapters.api.admin_aml_urls")),
    path("api/admin/stats", AdminStatsView.as_view()),
    path("api/transfer/", include("contexts.transfer.adapters.api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
]
