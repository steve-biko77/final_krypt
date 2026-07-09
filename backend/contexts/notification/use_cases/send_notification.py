"""KRYP-30 — Orchestre l'envoi d'une notification (Fig. 12/18).

Hexagonal use case : pas d'import Django, uniquement le port. Le SMS ne
concerne que TRANSFER_DELIVERED (KRYP-26 : confirmation de livraison au
bénéficiaire) — les 4 autres événements sont email uniquement.
"""
from dataclasses import dataclass
from typing import Optional

from ..domain.entities import NotificationEvent, NotificationEventType
from ..ports.notification_service import NotificationServicePort

SMS_EVENT_TYPES = {NotificationEventType.TRANSFER_DELIVERED}


@dataclass
class SendNotificationInput:
    event: NotificationEvent
    to_email: str
    to_phone: Optional[str] = None


class SendNotificationUseCase:
    def __init__(
        self,
        email_service: NotificationServicePort,
        sms_service: NotificationServicePort,
    ):
        self._email_service = email_service
        self._sms_service = sms_service

    def execute(self, data: SendNotificationInput) -> None:
        self._email_service.send_email(data.to_email, data.event)

        if data.event.type in SMS_EVENT_TYPES and data.to_phone:
            self._sms_service.send_sms(data.to_phone, data.event)
