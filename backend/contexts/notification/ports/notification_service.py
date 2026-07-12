from abc import ABC

from ..domain.entities import NotificationEvent


class NotificationServicePort(ABC):
    """KRYP-30 — Port du bounded context Notification (Fig. 12/18).

    DÉCISION DE CONCEPTION (validée) : l'email est envoyé via Django natif
    (``django.core.mail``, backend console en dev — voir ``DjangoEmailService``),
    PAS SendGrid pour l'instant. Ce n'est pas un raccourci silencieux : SendGrid
    nécessite un compte, une vérification d'expéditeur et une clé API — reporté à
    un ticket dédié futur, hors scope ici. Le SMS est entièrement mocké
    (``MockSMSService``, ``logger.info`` uniquement) — aucune intégration Twilio
    réelle prévue dans ce sprint.

    Grâce à ce port, brancher SendGrid (ou Twilio) plus tard ne demande qu'UN
    SEUL nouvel adapter implémentant cette même interface — AUCUNE modification
    des use cases ni des points d'appel (``RegisterUserUseCase``,
    ``analyze_kyc_task``, ``KYCReviewView``, ``InitiateTransferUseCase``,
    ``ProcessPayoutUseCase``), qui ne connaissent que ce port.

    Chaque méthode a une implémentation par défaut qui lève ``NotImplementedError``
    plutôt que d'être ``@abstractmethod`` : un adapter donné ne couvre
    généralement qu'un seul canal (``DjangoEmailService`` → email,
    ``MockSMSService`` → SMS) — ``SendNotificationUseCase`` n'appelle jamais la
    méthode non couverte par l'adapter qu'on lui a injecté pour ce canal. Un futur
    adapter unifié (ex: un client fournisseur qui fait les deux) peut simplement
    surcharger les deux méthodes.
    """

    def send_email(self, to: str, event: NotificationEvent) -> None:
        raise NotImplementedError

    def send_sms(self, to: str, event: NotificationEvent) -> None:
        raise NotImplementedError
