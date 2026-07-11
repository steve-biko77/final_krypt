"""KRYP-31 — Décision admin sur un transfert en revue AML (Fig. 10 points 4/5).

Un seul use case pour les 3 actions de premier niveau (approve/reject/escalate,
depuis AML_PENDING_REVIEW) ET les 2 actions de second niveau (approve/reject
seulement, depuis ESCALATED) : mêmes règles de traçabilité (audit_log, log
on-chain immédiat sauf escalate, séparation motif interne / notification
utilisateur générique) des deux côtés du diagramme — un point de vérité unique
pour ne jamais diverger entre les deux entrées (le risque exact que le ticket
demande d'éviter). ``expected_status``/``allowed_actions`` paramètrent le niveau.

Hexagonal : pas d'import Django au niveau module — ports injectés
(transaction_repo, aml_repo duck-typés, PaymentServicePort, BlockchainServicePort).
L'écriture de l'audit log (AMLAdminAuditLog) utilise un import local, même
convention que ``PendingAuditHash``/``AMLAdminAuditLog`` ailleurs dans ce projet.
"""
import logging
from dataclasses import dataclass
from typing import FrozenSet, Optional

from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
from contexts.blockchain.ports.blockchain_service import BlockchainServicePort

from ..domain.entities import Transaction, TransactionStatus
from ..domain.exceptions import (
    AdminReasonRequiredError,
    AdminReviewNotAllowedError,
    PaymentServiceError,
)
from ..ports.payment_service import PaymentServicePort

logger = logging.getLogger(__name__)

APPROVE = "approve"
REJECT = "reject"
ESCALATE = "escalate"

_REVIEW_DECISION_BY_ACTION = {
    APPROVE: "MANUALLY_APPROVED",
    REJECT: "MANUALLY_REJECTED",
    ESCALATE: "ESCALATED",
}


@dataclass
class DecideAMLReviewResult:
    transaction: Transaction
    tx_hash: Optional[str] = None
    action: str = ""


class DecideAMLReviewUseCase:
    def __init__(
        self,
        transaction_repo,
        aml_repo,
        payment_service: PaymentServicePort,
        blockchain_service: BlockchainServicePort,
        allowed_actions: FrozenSet[str] = frozenset({APPROVE, REJECT, ESCALATE}),
    ):
        self._repo = transaction_repo
        self._aml_repo = aml_repo
        self._payment_service = payment_service
        self._blockchain = blockchain_service
        self._allowed_actions = allowed_actions

    def execute(
        self,
        transaction_id: str,
        expected_status: TransactionStatus,
        action: str,
        admin_id: str,
        motif: str,
        audit_action_label: str,
    ) -> DecideAMLReviewResult:
        if action not in self._allowed_actions:
            raise AdminReviewNotAllowedError(
                f"Action '{action}' non autorisée à ce niveau de revue."
            )
        if action == REJECT and not (motif or "").strip():
            raise AdminReasonRequiredError()

        transaction = self._repo.find_by_id(transaction_id)
        if transaction is None:
            raise AdminReviewNotAllowedError("Transaction introuvable.")
        if transaction.status != expected_status:
            raise AdminReviewNotAllowedError(
                f"Ce transfert n'est plus en statut {expected_status.value} "
                f"(statut actuel : {transaction.status.value})."
            )

        if action == APPROVE:
            result = self._approve(transaction)
        elif action == REJECT:
            result = self._reject(transaction)
        else:
            result = self._escalate(transaction)

        # AMLResultModel.combined_decision reste figé au moment du scoring —
        # review_decision porte la décision admin, séparément (jamais réécrit
        # via save(), cf. DjangoORMAMLRepository.update_review).
        aml_result = self._aml_repo.find_by_transfer_id(transaction_id)
        if aml_result:
            self._aml_repo.update_review(
                aml_result.id,
                reviewed_by_id=admin_id,
                review_decision=_REVIEW_DECISION_BY_ACTION[action],
            )

        from contexts.compliance.models import AMLAdminAuditLog
        AMLAdminAuditLog.objects.create(
            transaction_id=transaction_id,
            admin_id=admin_id,
            action=audit_action_label,
            motif=motif or "",
            tx_hash=result.tx_hash,
        )

        return result

    # ------------------------------------------------------------- branches
    def _approve(self, transaction: Transaction) -> DecideAMLReviewResult:
        # Stripe : ne crée un Payment Intent que s'il n'existe pas déjà — un
        # transfert AML_PENDING_REVIEW/ESCALATED n'en a jamais reçu à
        # l'initiation (KRYP-21/22 : "PENDING_REVIEW — do NOT call the payment
        # service").
        new_intent_created = False
        if not transaction.stripe_payment_intent_id:
            intent = self._payment_service.create_payment_intent(
                transaction.amount_eur, transaction.id
            )
            transaction.stripe_payment_intent_id = intent.payment_intent_id
            new_intent_created = True

        # Log on-chain IMMÉDIAT (Fig. 10 point 4a) — transferId dérivé via la
        # fonction unique (KRYP-37), jamais un UUID brut.
        onchain_transfer_id = to_onchain_transfer_id(transaction.id)
        tx_hash = None
        try:
            tx_hash = self._blockchain.log_critical_event(
                onchain_transfer_id, "AML_MANUALLY_APPROVED"
            )
        except Exception as exc:  # noqa: BLE001 - best-effort, never crash the decision
            logger.error(
                "log_critical_event a échoué pour %s (AML_MANUALLY_APPROVED): %s",
                transaction.id, exc,
            )

        updated = self._repo.apply_admin_decision(
            transaction.id,
            expected_status=transaction.status,
            new_status=TransactionStatus.PROCESSING,
            tx_hash=tx_hash,
            stripe_payment_intent_id=(
                transaction.stripe_payment_intent_id if new_intent_created else None
            ),
        )
        if updated is None:
            # Race : le transfert a changé entre-temps (ex: annulé). Ne pas
            # laisser un Payment Intent tout juste créé orphelin.
            if new_intent_created:
                try:
                    self._payment_service.cancel_payment_intent(
                        transaction.stripe_payment_intent_id
                    )
                except PaymentServiceError:
                    logger.warning(
                        "decide_aml_review: échec annulation best-effort du PI "
                        "%s après changement concurrent de %s.",
                        transaction.stripe_payment_intent_id, transaction.id,
                    )
            raise AdminReviewNotAllowedError("Le statut a changé entre-temps.")

        return DecideAMLReviewResult(transaction=updated, tx_hash=tx_hash, action=APPROVE)

    def _reject(self, transaction: Transaction) -> DecideAMLReviewResult:
        onchain_transfer_id = to_onchain_transfer_id(transaction.id)
        tx_hash = None
        try:
            tx_hash = self._blockchain.log_critical_event(
                onchain_transfer_id, "AML_MANUALLY_REJECTED"
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "log_critical_event a échoué pour %s (AML_MANUALLY_REJECTED): %s",
                transaction.id, exc,
            )

        updated = self._repo.apply_admin_decision(
            transaction.id,
            expected_status=transaction.status,
            new_status=TransactionStatus.AML_BLOCKED,
            tx_hash=tx_hash,
        )
        if updated is None:
            raise AdminReviewNotAllowedError("Le statut a changé entre-temps.")

        return DecideAMLReviewResult(transaction=updated, tx_hash=tx_hash, action=REJECT)

    def _escalate(self, transaction: Transaction) -> DecideAMLReviewResult:
        # Fig. 10 — PAS de log on-chain à cette étape : seulement à la décision
        # finale, après revue du responsable (voir _approve/_reject, appelés
        # depuis le second niveau avec le même use case). Ne jamais logger deux
        # fois le même transfert.
        updated = self._repo.apply_admin_decision(
            transaction.id,
            expected_status=transaction.status,
            new_status=TransactionStatus.ESCALATED,
            tx_hash=None,
        )
        if updated is None:
            raise AdminReviewNotAllowedError("Le statut a changé entre-temps.")

        return DecideAMLReviewResult(transaction=updated, tx_hash=None, action=ESCALATE)
