from rest_framework.permissions import BasePermission


class IsStaffUser(BasePermission):
    """Allows access only to users with is_staff=True."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class IsStaffWith2FA(BasePermission):
    """KRYP-31 — Porte d'entrée de la console admin AML (Fig. 10) : is_staff ET
    2FA activée. Message distinct du 403 générique "not staff" pour orienter
    l'admin vers l'activation 2FA plutôt que de le laisser croire qu'il n'a pas
    les droits."""

    message = "Accès réservé au personnel autorisé."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_staff):
            self.message = "Accès réservé au personnel autorisé."
            return False
        if not user.is_2fa_enabled:
            self.message = (
                "L'authentification à deux facteurs doit être activée pour "
                "accéder à la console AML."
            )
            return False
        return True
