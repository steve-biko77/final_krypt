from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from contexts.compliance.domain.entities import AMLDecision
from contexts.compliance.use_cases.score_aml import ScoreAMLInput, ScoreAMLUseCase

from ..domain.entities import Transaction, TransactionStatus
from ..domain.exceptions import TransferBlockedError
from ..ports.exchange_rate_service import ExchangeRateServicePort
from ..ports.payment_service import PaymentServicePort
from .simulate_transfer import SimulateTransferInput, SimulateTransferUseCase

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
            self._transaction_repo.save(transaction)
            raise TransferBlockedError()

        if decision not in _APPROVED_DECISIONS:
            # PENDING_REVIEW — do NOT call the payment service.
            transaction.status = TransactionStatus.AML_PENDING_REVIEW
            transaction = self._transaction_repo.save(transaction)
            return InitiateTransferResult(transaction=transaction, client_secret=None)

        # Approved → create the Stripe payment intent.
        transaction.status = TransactionStatus.PROCESSING
        intent = self._payment_service.create_payment_intent(
            simulation.amount_eur, transaction.id
        )
        transaction.stripe_payment_intent_id = intent.payment_intent_id
        transaction = self._transaction_repo.save(transaction)
        return InitiateTransferResult(
            transaction=transaction, client_secret=intent.client_secret
        )
