import uuid
from datetime import datetime

from contexts.transfer.models import TransactionModel

from ...ports.transaction_history_service import TransactionHistoryServicePort


def _exclude_current(qs, exclude_transfer_id: str):
    """Exclut la transaction en cours (déjà persistée avant le scoring AML)."""
    if not exclude_transfer_id:
        return qs
    try:
        return qs.exclude(id=uuid.UUID(exclude_transfer_id))
    except (ValueError, TypeError):
        # transfer_id non-UUID (ex. endpoint standalone) — rien à exclure.
        return qs


class DjangoTransactionHistoryService(TransactionHistoryServicePort):
    """
    Adapter concret du port TransactionHistoryServicePort.

    Seul module de `compliance` autorisé à importer `contexts.transfer.models`.
    C'est un module feuille (jamais importé par `transfer`), donc pas de cycle :
    l'injection se fait au niveau des views.
    """

    def count_since(
        self, sender_id: str, since: datetime, exclude_transfer_id: str = ""
    ) -> int:
        qs = TransactionModel.objects.filter(
            sender_id=uuid.UUID(sender_id), created_at__gte=since
        )
        qs = _exclude_current(qs, exclude_transfer_id)
        return qs.count()

    def has_prior_transaction(
        self,
        sender_id: str,
        beneficiary_name: str,
        momo_number: str,
        exclude_transfer_id: str = "",
    ) -> bool:
        qs = TransactionModel.objects.filter(
            sender_id=uuid.UUID(sender_id), beneficiary_name=beneficiary_name
        )
        if momo_number:
            qs = qs.filter(momo_number=momo_number)
        qs = _exclude_current(qs, exclude_transfer_id)
        return qs.exists()
