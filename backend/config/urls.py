from django.urls import include, path

urlpatterns = [
    path("api/auth/", include("contexts.identity.adapters.api.urls")),
    path("api/kyc/", include("contexts.compliance.adapters.api.urls")),
    path("api/aml/", include("contexts.compliance.adapters.api.aml_urls")),
    path("api/admin/aml/", include("contexts.compliance.adapters.api.admin_aml_urls")),
    path("api/transfer/", include("contexts.transfer.adapters.api.urls")),
]
