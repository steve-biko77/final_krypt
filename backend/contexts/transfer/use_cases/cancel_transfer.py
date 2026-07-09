"""KRYP-28 — Annulation d'un transfert avant confirmation Stripe.

Fig. 7 — CANCELLED n'est accessible que depuis DRAFT ou PENDING_AML. Un Payment
Intent n'est normalement créé qu'au passage à PROCESSING (jamais pendant
DRAFT/PENDING_AML) : l'annulation défensive côté Stripe ci-dessous couvre une
race rare (le PI aurait été créé mais la transition vers PROCESSING n'aurait pas
encore été persistée), pas le chemin principal.
"""
import logging
from dataclasses import dataclass

from ..domain.entities import Transaction, TransactionStatus
from ..domain.exceptions import PaymentServiceError, TransferNotCancellableError
from ..ports.payment_service import PaymentServicePort

logger = logging.getLogger(__name__)

_CANCELLABLE_STATUSES = {TransactionStatus.DRAFT, TransactionStatus.PENDING_AML}


@dataclass
class CancelTransferResult:
    transaction: Transaction


class CancelTransferUseCase:
    def __init__(self, payment_service: PaymentServicePort, transaction_repo):
        self._payment_service = payment_service
        self._transaction_repo = transaction_repo

    def execute(self, transaction_id: str) -> CancelTransferResult:
        transaction = self._transaction_repo.find_by_id(transaction_id)
        if transaction is None:
            raise TransferNotCancellableError("Transaction introuvable.")

        if transaction.status not in _CANCELLABLE_STATUSES:
            raise TransferNotCancellableError(
                f"Ce transfert ne peut plus être annulé (statut actuel : "
                f"{transaction.status.value})."
            )

        if transaction.stripe_payment_intent_id:
            # Cas défensif (cf. docstring du module) — ne devrait normalement
            # jamais survenir tant que le statut est DRAFT/PENDING_AML.
            try:
                self._payment_service.cancel_payment_intent(
                    transaction.stripe_payment_intent_id
                )
            except PaymentServiceError as exc:
                # Stripe peut refuser (PI déjà confirmé/annulé côté Stripe) : ça ne
                # doit pas empêcher l'annulation côté KRYPT si le statut local est
                # toujours légitimement annulable.
                logger.warning(
                    "cancel_transfer: Stripe a refusé l'annulation du PI %s pour "
                    "%s (%s) — annulation locale poursuivie.",
                    transaction.stripe_payment_intent_id, transaction_id, exc,
                )

        cancelled = self._transaction_repo.cancel_if_cancellable(transaction_id)
        if cancelled is None:
            # Race entre le find_by_id ci-dessus et l'update conditionnel (ex: le
            # scoring AML vient de conclure au même instant).
            raise TransferNotCancellableError(
                "Ce transfert ne peut plus être annulé : son statut a changé "
                "entre-temps."
            )

        return CancelTransferResult(transaction=cancelled)
