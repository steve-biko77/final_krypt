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


@shared_task(name="notification.send_admin_alert")
def admin_alert_task(event_type: str, to_email: str, context: dict) -> dict:
    """KRYP-31 — Alerte admin (console AML, Fig. 10) : contrairement à
    ``notification_task``, ne résout PAS de ``UserModel`` — le destinataire est
    une adresse email de configuration (``settings.COMPLIANCE_MANAGER_EMAIL``,
    en attendant un vrai système de rôles/hiérarchie admin), pas forcément un
    utilisateur enregistré. Réutilise le même port/adapter/use case (une seule
    fois : le port ``NotificationServicePort`` est agnostique du mécanisme de
    résolution du destinataire, seule cette tâche diffère)."""
    from .adapters.services.django_email_service import DjangoEmailService
    from .adapters.services.mock_sms_service import MockSMSService
    from .domain.entities import NotificationEvent, NotificationEventType
    from .use_cases.send_notification import (
        SendNotificationInput,
        SendNotificationUseCase,
    )

    event = NotificationEvent(
        type=NotificationEventType(event_type),
        recipient_name="Équipe conformité KRYPT",
        context=context,
    )
    SendNotificationUseCase(
        email_service=DjangoEmailService(),
        sms_service=MockSMSService(),
    ).execute(SendNotificationInput(event=event, to_email=to_email))

    return {"sent": True, "event_type": event_type, "to_email": to_email}
