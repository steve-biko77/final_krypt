import uuid
from typing import Optional

from django.utils import timezone

from ...domain.entities import Transaction, TransactionStatus
from ...models import TransactionModel


class DjangoORMTransactionRepository:
    def save(self, transaction: Transaction) -> Transaction:
        obj, _ = TransactionModel.objects.update_or_create(
            id=uuid.UUID(transaction.id),
            defaults=dict(
                sender_id=uuid.UUID(transaction.sender_id),
                beneficiary_name=transaction.beneficiary_name,
                beneficiary_country=transaction.beneficiary_country,
                momo_number=transaction.momo_number,
                operator=transaction.operator,
                amount_eur=transaction.amount_eur,
                fees_eur=transaction.fees_eur,
                amount_xaf=transaction.amount_xaf,
                status=transaction.status.value,
                aml_result_id=transaction.aml_result_id,
                stripe_payment_intent_id=transaction.stripe_payment_intent_id,
                escrow_tx_hash=transaction.escrow_tx_hash,
            ),
        )
        return self._to_entity(obj)

    def find_by_id(self, id: str) -> Optional[Transaction]:
        try:
            obj = TransactionModel.objects.get(pk=uuid.UUID(id))
            return self._to_entity(obj)
        except (TransactionModel.DoesNotExist, ValueError):
            return None

    def find_by_sender(self, sender_id: str, limit: int = 5) -> list[Transaction]:
        """Refonte frontend (partie 3/4) — transferts récents d'un émetteur
        (tableau de bord), triés par ``-created_at`` (déjà l'ordre par défaut du
        modèle, explicité ici pour ne pas dépendre du Meta.ordering)."""
        qs = TransactionModel.objects.filter(
            sender_id=uuid.UUID(sender_id)
        ).order_by("-created_at")[:limit]
        return [self._to_entity(obj) for obj in qs]

    def find_by_payment_intent_id(
        self, payment_intent_id: str
    ) -> Optional[Transaction]:
        try:
            obj = TransactionModel.objects.get(
                stripe_payment_intent_id=payment_intent_id
            )
            return self._to_entity(obj)
        except TransactionModel.DoesNotExist:
            return None

    def update_status(self, id: str, status: TransactionStatus) -> None:
        TransactionModel.objects.filter(pk=uuid.UUID(id)).update(status=status.value)

    def save_if_status(
        self, transaction: Transaction, expected_status: TransactionStatus
    ) -> Optional[Transaction]:
        """KRYP-28 — Same field set as ``save()``, but the write only takes effect
        if the row's current status still matches ``expected_status``. Guards the
        post-AML-scoring writes in InitiateTransferUseCase against a concurrent
        cancellation silently clobbering CANCELLED. Returns None (no write) if the
        status had already moved on."""
        updated = TransactionModel.objects.filter(
            pk=uuid.UUID(transaction.id), status=expected_status.value
        ).update(
            beneficiary_name=transaction.beneficiary_name,
            beneficiary_country=transaction.beneficiary_country,
            momo_number=transaction.momo_number,
            operator=transaction.operator,
            amount_eur=transaction.amount_eur,
            fees_eur=transaction.fees_eur,
            amount_xaf=transaction.amount_xaf,
            status=transaction.status.value,
            aml_result_id=transaction.aml_result_id,
            stripe_payment_intent_id=transaction.stripe_payment_intent_id,
            escrow_tx_hash=transaction.escrow_tx_hash,
        )
        if updated == 0:
            return None
        return self.find_by_id(transaction.id)

    def cancel_if_cancellable(self, id: str) -> Optional[Transaction]:
        """KRYP-28 — Atomically transition to CANCELLED only if the row is still
        DRAFT or PENDING_AML (Fig. 7). Returns the updated Transaction, or None if
        it had already moved past that point."""
        updated = TransactionModel.objects.filter(
            pk=uuid.UUID(id),
            status__in=[
                TransactionStatus.DRAFT.value,
                TransactionStatus.PENDING_AML.value,
            ],
        ).update(status=TransactionStatus.CANCELLED.value)
        if updated == 0:
            return None
        return self.find_by_id(id)

    def apply_admin_decision(
        self,
        id: str,
        expected_status: TransactionStatus,
        new_status: TransactionStatus,
        tx_hash: Optional[str] = None,
        stripe_payment_intent_id: Optional[str] = None,
    ) -> Optional[Transaction]:
        """KRYP-31 — Guarded transition for an admin AML console decision
        (request-docs / approve / reject / escalate / escalated decide): only
        writes if the row is still ``expected_status`` (guards a double-click or
        a race with a concurrent state change, same idiom as ``save_if_status``),
        and persists the on-chain tx hash of the DECISION itself (``None`` for
        ESCALATE — Fig. 10 never logs on-chain at that step) plus, on approve, a
        newly-created Stripe payment intent id if the transfer skipped Stripe at
        initiate time."""
        updates = {"status": new_status.value, "admin_review_tx_hash": tx_hash}
        if stripe_payment_intent_id is not None:
            updates["stripe_payment_intent_id"] = stripe_payment_intent_id
        updated = TransactionModel.objects.filter(
            pk=uuid.UUID(id), status=expected_status.value
        ).update(**updates)
        if updated == 0:
            return None
        return self.find_by_id(id)

    def mark_escrowed(self, id: str, tx_hash: str) -> None:
        """Persist the ESCROWED status, the on-chain tx hash and the precise
        ``escrowed_at`` timestamp in one update (the latter is the unambiguous
        anchor the 24h-timeout job checks)."""
        TransactionModel.objects.filter(pk=uuid.UUID(id)).update(
            status=TransactionStatus.ESCROWED.value,
            escrow_tx_hash=tx_hash,
            escrowed_at=timezone.now(),
        )

    def mark_delivered(self, id: str, payout_reference: str) -> None:
        """Persist the DELIVERED status and the mobile-money payout reference."""
        TransactionModel.objects.filter(pk=uuid.UUID(id)).update(
            status=TransactionStatus.DELIVERED.value,
            payout_reference=payout_reference,
        )

    def mark_payout_failed(self, id: str) -> None:
        """Mark a transaction PAYOUT_FAILED (after failed payout / 24h timeout)."""
        TransactionModel.objects.filter(pk=uuid.UUID(id)).update(
            status=TransactionStatus.PAYOUT_FAILED.value,
        )

    def _to_entity(self, obj: TransactionModel) -> Transaction:
        return Transaction(
            id=str(obj.pk),
            sender_id=str(obj.sender_id),
            beneficiary_name=obj.beneficiary_name,
            beneficiary_country=obj.beneficiary_country,
            momo_number=obj.momo_number,
            operator=obj.operator,
            amount_eur=obj.amount_eur,
            fees_eur=obj.fees_eur,
            amount_xaf=obj.amount_xaf,
            status=TransactionStatus(obj.status),
            aml_result_id=obj.aml_result_id,
            stripe_payment_intent_id=obj.stripe_payment_intent_id,
            escrow_tx_hash=obj.escrow_tx_hash,
            escrowed_at=obj.escrowed_at,
            payout_reference=obj.payout_reference,
            admin_review_tx_hash=obj.admin_review_tx_hash,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
