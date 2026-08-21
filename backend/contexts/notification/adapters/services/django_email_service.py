import functools
from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from ...domain.entities import NotificationEvent, NotificationEventType
from ...ports.notification_service import NotificationServicePort

# Logo KRYPT — converti UNE FOIS en PNG statique depuis frontend/public/icons/
# logo.svg (sharp/librsvg, 120x120, voir contexts/notification/assets/) plutôt
# que chargé depuis une URL externe (http://localhost:3000/... n'est jamais
# atteignable par le serveur de messagerie d'un vrai destinataire). Attaché en
# pièce jointe "inline" et référencé par Content-ID (cid:logo_krypt) dans
# _base_email.html — fonctionne sans connexion réseau du client mail.
_LOGO_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "logo_krypt.png"
_LOGO_CID = "logo_krypt"


@functools.lru_cache(maxsize=1)
def _logo_bytes() -> bytes:
    return _LOGO_PATH.read_bytes()


def _logo_mime_image() -> MIMEImage:
    image = MIMEImage(_logo_bytes())
    image.add_header("Content-ID", f"<{_LOGO_CID}>")
    image.add_header("Content-Disposition", "inline", filename="logo_krypt.png")
    return image


_TEMPLATE_BY_EVENT = {
    NotificationEventType.USER_REGISTERED: (
        "notification/user_registered.html",
        "Bienvenue chez KRYPT",
    ),
    NotificationEventType.KYC_APPROVED: (
        "notification/kyc_approved.html",
        "Votre identité KRYPT est vérifiée",
    ),
    NotificationEventType.TRANSFER_INITIATED: (
        "notification/transfer_initiated.html",
        "Votre transfert KRYPT est en cours",
    ),
    NotificationEventType.TRANSFER_DELIVERED: (
        "notification/transfer_delivered.html",
        "Votre transfert KRYPT a été livré",
    ),
    NotificationEventType.TRANSFER_FAILED: (
        "notification/transfer_failed.html",
        "Votre transfert KRYPT n'a pas abouti",
    ),
    NotificationEventType.DOCS_REQUESTED: (
        "notification/docs_requested.html",
        "Documents complémentaires requis pour votre transfert KRYPT",
    ),
    NotificationEventType.ADMIN_ALERT_PENDING_REVIEW: (
        "notification/admin_alert_pending_review.html",
        "[KRYPT Admin] Nouveau transfert en revue AML",
    ),
    NotificationEventType.ADMIN_ALERT_ESCALATED: (
        "notification/admin_alert_escalated.html",
        "[KRYPT Admin] Transfert escaladé — revue niveau 2 requise",
    ),
}


class DjangoEmailService(NotificationServicePort):
    """Email via Django natif (``django.core.mail``) — voir ``EMAIL_BACKEND``
    dans settings.py (backend console en dev, jamais d'appel réseau hors prod).

    N'implémente que ``send_email`` — le SMS est un canal distinct couvert par
    ``MockSMSService`` (cf. docstring du port pour le raisonnement)."""

    def send_email(self, to: str, event: NotificationEvent) -> None:
        template_name, subject = _TEMPLATE_BY_EVENT[event.type]
        html_body = render_to_string(
            template_name, {"recipient_name": event.recipient_name, **event.context}
        )
        message = EmailMultiAlternatives(
            subject=subject,
            body=strip_tags(html_body),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        )
        message.attach_alternative(html_body, "text/html")
        # multipart/related (au lieu du multipart/mixed par défaut) — requis
        # pour que les clients mail résolvent cid:logo_krypt comme une image
        # intégrée plutôt que comme une pièce jointe ordinaire.
        message.mixed_subtype = "related"
        message.attach(_logo_mime_image())
        message.send()
