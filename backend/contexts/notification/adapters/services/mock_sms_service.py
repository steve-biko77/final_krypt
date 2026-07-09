import logging

from ...domain.entities import NotificationEvent
from ...ports.notification_service import NotificationServicePort

logger = logging.getLogger(__name__)


class MockSMSService(NotificationServicePort):
    """SMS entièrement mocké — ``logger.info`` uniquement, jamais d'appel réseau.

    Contrairement au mock MTN/Orange (contrainte externe non résolvable : accès
    sandbox indisponible), ce mock est un choix de scope délibéré et assumé pour
    ce sprint : le ticket KRYP-30 exclut explicitement toute intégration Twilio
    réelle. Brancher un vrai fournisseur SMS plus tard (Twilio ou autre) se fait
    en ajoutant un nouvel adapter à ce même port, sans toucher aux use cases.

    N'implémente que ``send_sms`` — l'email est couvert par ``DjangoEmailService``."""

    def send_sms(self, to: str, event: NotificationEvent) -> None:
        message = event.context.get("sms_message", f"KRYPT — {event.type.value}")
        logger.info("SMS to %s: %s", to, message)
