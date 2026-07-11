"""KRYP-31 (partie 2/3) — Geler le compte de l'émetteur d'un transfert HARD_BLOCK
(image 2, section 4). PAS une décision sur le transfert lui-même — son statut
ne change pas ; seul le compte utilisateur est affecté (is_frozen=True),
bloquant toute FUTURE initiation de transfert (voir InitiateTransferView).

Log on-chain IMMÉDIAT, comme les décisions de la partie 1/3, mais avec un
identifiant dérivé du COMPTE plutôt que du transfert (to_onchain_account_id) —
c'est un événement lié à l'utilisateur, pas à cette transaction précise.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from contexts.blockchain.domain.transfer_id import to_onchain_account_id
from contexts.blockchain.ports.blockchain_service import BlockchainServicePort
from contexts.transfer.domain.exceptions import AdminReviewNotAllowedError

from ..domain.entities import AMLDecision

logger = logging.getLogger(__name__)


@dataclass
class FreezeAccountInput:
    transaction_id: str
    admin_id: str


@dataclass
class FreezeAccountResult:
    user_id: str
    tx_hash: Optional[str] = None


class FreezeAccountUseCase:
    def __init__(self, transaction_repo, aml_repo, blockchain_service: BlockchainServicePort):
        self._transaction_repo = transaction_repo
        self._aml_repo = aml_repo
        self._blockchain = blockchain_service

    def execute(self, data: FreezeAccountInput) -> FreezeAccountResult:
        transaction = self._transaction_repo.find_by_id(data.transaction_id)
        if transaction is None:
            raise AdminReviewNotAllowedError("Transaction introuvable.")

        aml_result = self._aml_repo.find_by_transfer_id(data.transaction_id)
        if aml_result is None or aml_result.combined_decision != AMLDecision.HARD_BLOCK:
            raise AdminReviewNotAllowedError(
                "Ce transfert n'est pas un cas HARD_BLOCK."
            )

        user_id = transaction.sender_id

        onchain_account_id = to_onchain_account_id(user_id)
        tx_hash = None
        try:
            tx_hash = self._blockchain.log_critical_event(
                onchain_account_id, "ACCOUNT_FROZEN"
            )
        except Exception as exc:  # noqa: BLE001 - best-effort, never crash the freeze
            logger.error(
                "log_critical_event a échoué pour le gel du compte %s: %s",
                user_id, exc,
            )

        from contexts.identity.models import UserModel
        UserModel.objects.filter(pk=user_id).update(is_frozen=True)

        from contexts.compliance.models import AMLAdminAuditLog
        AMLAdminAuditLog.objects.create(
            transaction_id=data.transaction_id,
            admin_id=data.admin_id,
            action=AMLAdminAuditLog.Action.FREEZE_ACCOUNT,
            tx_hash=tx_hash,
        )

        return FreezeAccountResult(user_id=user_id, tx_hash=tx_hash)
