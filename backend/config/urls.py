from django.urls import include, path

urlpatterns = [
    path("api/auth/", include("contexts.identity.adapters.api.urls")),
    path("api/kyc/", include("contexts.compliance.adapters.api.urls")),
]
