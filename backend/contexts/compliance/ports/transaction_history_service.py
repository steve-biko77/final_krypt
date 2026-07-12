from abc import ABC, abstractmethod
from datetime import datetime


class TransactionHistoryServicePort(ABC):
    """
    Port permettant au contexte `compliance` d'interroger l'historique
    transactionnel (détenu par le contexte `transfer`) sans dépendance directe.

    Utilisé pour calculer les features comportementales de la Couche 1 / Couche 4 :
      - `is_new_beneficiary` (via `has_prior_transaction`, inversé)
      - `sender_tx_count_30d` (via `count_since`)

    L'implémentation concrète (`DjangoTransactionHistoryService`) est le seul
    module autorisé à importer `contexts.transfer.models` — les use cases ne
    dépendent que de ce port, pour éviter tout cycle d'import entre bounded contexts.
    """

    @abstractmethod
    def count_since(
        self, sender_id: str, since: datetime, exclude_transfer_id: str = ""
    ) -> int:
        """Nombre de transactions envoyées par `sender_id` depuis `since`."""

    @abstractmethod
    def has_prior_transaction(
        self,
        sender_id: str,
        beneficiary_name: str,
        momo_number: str,
        exclude_transfer_id: str = "",
    ) -> bool:
        """
        True si `sender_id` a déjà transféré vers ce bénéficiaire auparavant.
        `exclude_transfer_id` permet d'exclure la transaction en cours (déjà
        persistée avant le scoring AML dans le flux `transfer`).
        """
