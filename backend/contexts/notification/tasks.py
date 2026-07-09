"""KRYP-30 — Notification dispatch, async par nature (jamais bloquant pour le
flux appelant : inscription, revue KYC, initiation/livraison de transfert).

Un seul task générique plutôt qu'un task par événement (le routage vers le bon
template/canal est une responsabilité du use case, pas de Celery) — dispatché
depuis la couche adapter (vue ou autre task), jamais depuis un use case
hexagonal, cohérent avec le reste du projet (cf. KYCSubmitView -> analyze_kyc_task,
escrow_lock_task -> payout_task).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="notification.send")
def notification_task(event_type: str, user_id: str, context: dict) -> dict:
    from contexts.identity.models import UserModel

    from .adapters.services.django_email_service import DjangoEmailService
    from .adapters.services.mock_sms_service import MockSMSService
    from .domain.entities import NotificationEvent, NotificationEventType
    from .use_cases.send_notification import (
        SendNotificationInput,
        SendNotificationUseCase,
    )

    try:
        user = UserModel.objects.get(pk=user_id)
    except (UserModel.DoesNotExist, ValueError):
        logger.error(
            "notification_task: utilisateur %s introuvable pour %s", user_id, event_type
        )
        return {"sent": False, "event_type": event_type}

    event = NotificationEvent(
        type=NotificationEventType(event_type),
        recipient_name=user.first_name,
        context=context,
    )

    use_case = SendNotificationUseCase(
        email_service=DjangoEmailService(),
        sms_service=MockSMSService(),
    )
    # KRYP-26 — le SMS de livraison va au numéro Mobile Money du BÉNÉFICIAIRE
    # (pas au téléphone de l'expéditeur KRYPT) : porté par le contexte, jamais
    # résolu via UserModel (le bénéficiaire n'est pas forcément un utilisateur KRYPT).
    use_case.execute(
        SendNotificationInput(
            event=event,
            to_email=user.email,
            to_phone=context.get("beneficiary_momo_number"),
        )
    )

    return {"sent": True, "event_type": event_type, "user_id": user_id}
