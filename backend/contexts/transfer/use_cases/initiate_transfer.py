import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from contexts.compliance.domain.entities import AMLDecision
from contexts.compliance.use_cases.score_aml import ScoreAMLInput, ScoreAMLUseCase

from ..domain.entities import Transaction, TransactionStatus
from ..domain.exceptions import PaymentServiceError, TransferBlockedError
from ..ports.exchange_rate_service import ExchangeRateServicePort
from ..ports.payment_service import PaymentServicePort
from .simulate_transfer import SimulateTransferInput, SimulateTransferUseCase

logger = logging.getLogger(__name__)

_APPROVED_DECISIONS = {AMLDecision.AUTO_APPROVED, AMLDecision.MANUALLY_APPROVED}
_BLOCKED_DECISIONS = {
    AMLDecision.HARD_BLOCK,
    AMLDecision.AUTO_BLOCKED,
    AMLDecision.MANUALLY_REJECTED,
}


@dataclass
class InitiateTransferInput:
    sender_id: str
    beneficiary_name: str
    beneficiary_country: str
    momo_number: str
    operator: str
    amount_eur: Decimal


@dataclass
class InitiateTransferResult:
    transaction: Transaction
    client_secret: Optional[str] = None


class InitiateTransferUseCase:
    def __init__(
        self,
        exchange_rate_service: ExchangeRateServicePort,
        payment_service: PaymentServicePort,
        aml_use_case: ScoreAMLUseCase,
        transaction_repo,
    ):
        self._exchange_rate_service = exchange_rate_service
        self._payment_service = payment_service
        self._aml_use_case = aml_use_case
        self._transaction_repo = transaction_repo

    def execute(self, data: InitiateTransferInput) -> InitiateTransferResult:
        # Reuse the simulation use case for fee/amount computation + min/max validation.
        # Raises InvalidAmountError on out-of-range amounts (same as /simulate).
        simulation = SimulateTransferUseCase(self._exchange_rate_service).execute(
            SimulateTransferInput(amount_eur=data.amount_eur)
        )

        # Persist the transaction before scoring — status PENDING_AML until AML resolves.
        transaction = Transaction(
            sender_id=data.sender_id,
            beneficiary_name=data.beneficiary_name,
            beneficiary_country=data.beneficiary_country,
            momo_number=data.momo_number,
            operator=data.operator,
            amount_eur=simulation.amount_eur,
            fees_eur=simulation.fees_eur,
            amount_xaf=simulation.amount_xaf,
            status=TransactionStatus.PENDING_AML,
        )
        transaction = self._transaction_repo.save(transaction)

        # Run AML scoring BEFORE ever touching Stripe.
        aml_result = self._aml_use_case.execute(
            ScoreAMLInput(
                user_id=data.sender_id,
                amount=float(data.amount_eur),
                beneficiary_name=data.beneficiary_name,
                beneficiary_country=data.beneficiary_country,
                transfer_id=transaction.id,
                momo_number=data.momo_number,
                operator=data.operator,
            )
        )
        transaction.aml_result_id = aml_result.id
        decision = aml_result.combined_decision

        if decision in _BLOCKED_DECISIONS:
            transaction.status = TransactionStatus.AML_BLOCKED
            saved = self._guarded_transition(transaction)
            if saved is None:
                # KRYP-28 point d'attention 2 : le transfert a été annulé pendant
                # le scoring AML — ne pas écraser CANCELLED avec AML_BLOCKED.
                current = self._transaction_repo.find_by_id(transaction.id)
                return InitiateTransferResult(transaction=current, client_secret=None)
            raise TransferBlockedError()

        if decision not in _APPROVED_DECISIONS:
            # PENDING_REVIEW — do NOT call the payment service.
            transaction.status = TransactionStatus.AML_PENDING_REVIEW
            saved = self._guarded_transition(transaction)
            if saved is None:
                current = self._transaction_repo.find_by_id(transaction.id)
                return InitiateTransferResult(transaction=current, client_secret=None)
            return InitiateTransferResult(transaction=saved, client_secret=None)

        # Approved → create the Stripe payment intent.
        transaction.status = TransactionStatus.PROCESSING
        intent = self._payment_service.create_payment_intent(
            simulation.amount_eur, transaction.id
        )
        transaction.stripe_payment_intent_id = intent.payment_intent_id
        saved = self._guarded_transition(transaction)
        if saved is None:
            # Annulé pendant l'appel Stripe : ne pas laisser le Payment Intent
            # orphelin engagé — tentative best-effort d'annulation côté Stripe.
            try:
                self._payment_service.cancel_payment_intent(intent.payment_intent_id)
            except PaymentServiceError:
                logger.warning(
                    "initiate_transfer: échec de l'annulation best-effort du PI "
                    "%s après annulation concurrente de %s.",
                    intent.payment_intent_id, transaction.id,
                )
            current = self._transaction_repo.find_by_id(transaction.id)
            return InitiateTransferResult(transaction=current, client_secret=None)
        return InitiateTransferResult(
            transaction=saved, client_secret=intent.client_secret
        )

    def _guarded_transition(self, transaction: Transaction) -> Optional[Transaction]:
        """KRYP-28 point d'attention 2 — écrit le nouveau statut uniquement si la
        ligne est toujours PENDING_AML en base. Si le transfert a été annulé
        entre-temps (race avec CancelTransferUseCase), la transition est refusée
        plutôt que d'écraser silencieusement CANCELLED."""
        saved = self._transaction_repo.save_if_status(
            transaction, TransactionStatus.PENDING_AML
        )
        if saved is None:
            logger.warning(
                "initiate_transfer: transition vers %s abandonnée pour %s — "
                "statut modifié entre-temps (probablement annulé).",
                transaction.status.value, transaction.id,
            )
        return saved
