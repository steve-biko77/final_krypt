import uuid
from typing import Optional

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
            ),
        )
        return self._to_entity(obj)

    def find_by_id(self, id: str) -> Optional[Transaction]:
        try:
            obj = TransactionModel.objects.get(pk=uuid.UUID(id))
            return self._to_entity(obj)
        except (TransactionModel.DoesNotExist, ValueError):
            return None

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
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
