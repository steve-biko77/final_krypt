from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from ...domain.entities import NotificationEvent, NotificationEventType
from ...ports.notification_service import NotificationServicePort

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
        message.send()
