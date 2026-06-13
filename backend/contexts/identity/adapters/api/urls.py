from django.urls import path

from .views import (
    LoginView,
    MeView,
    RegisterView,
    TwoFactorDisableView,
    TwoFactorLoginView,
    TwoFactorSetupView,
    TwoFactorVerifyView,
)

urlpatterns = [
    path("register", RegisterView.as_view(), name="auth-register"),
    path("login", LoginView.as_view(), name="auth-login"),
    path("me", MeView.as_view(), name="auth-me"),
    path("2fa/setup", TwoFactorSetupView.as_view(), name="2fa-setup"),
    path("2fa/verify", TwoFactorVerifyView.as_view(), name="2fa-verify"),
    path("2fa/disable", TwoFactorDisableView.as_view(), name="2fa-disable"),
    path("2fa/login", TwoFactorLoginView.as_view(), name="2fa-login"),
]
