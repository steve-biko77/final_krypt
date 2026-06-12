from django.urls import include, path

urlpatterns = [
    path("api/auth/", include("contexts.identity.adapters.api.urls")),
]
