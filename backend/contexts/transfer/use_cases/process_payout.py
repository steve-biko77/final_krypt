"""KRYP-26 — Mobile Money payout after escrow (ESCROWED → DELIVERED/PAYOUT_FAILED).

Hexagonal use case: no Django imports. Depends only on the injected
``MobileMoneyServicePort`` (already selected for the transaction's operator by
the factory — the use case never selects it itself, mirroring how
``LockEscrowUseCase`` doesn't know about the Web3 adapter beyond its port),
``BlockchainServicePort`` and a transaction repository.

Same shape as ``LockEscrowUseCase``: a bounded, injectable retry loop that never
raises out of itself and always resolves to a terminal status.

Two distinct outcomes with deliberately asymmetric audit handling:
  - SUCCESS is the NORMAL delivery case → the audit hash joins the periodic
    15-min Merkle batch (a new PendingAuditHash row with a discriminated
    ``{id}:DELIVERED`` leaf), and NO real-time critical event is logged.
  - FAILURE after all retries IS the exceptional path → escrow is refunded and a
    real-time ``log_critical_event(id, "PAYOUT_FAILED_REFUNDED")`` is emitted
    immediately (symmetric with the AML HARD_BLOCK / escrow-lock-failure
    precedents), best-effort so a secondary failure never crashes the use case.
"""
import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from contexts.blockchain.ports.blockchain_service import BlockchainServicePort
from contexts.mobile_money.ports.mobile_money_service import MobileMoneyServicePort
from ..notifications import notify_beneficiary_sms

logger = logging.getLogger(__name__)


@dataclass
class ProcessPayoutResult:
    success: bool
    payout_reference: Optional[str] = None


class ProcessPayoutUseCase:
    def __init__(
        self,
        mobile_money_service: MobileMoneyServicePort,
        blockchain_service: BlockchainServicePort,
        transaction_repo,
        max_retries: int = 3,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self._momo = mobile_money_service
        self._blockchain = blockchain_service
        self._repo = transaction_repo
        self._max_retries = max_retries
        self._sleep = sleep_fn

    def execute(self, transaction_id: str) -> ProcessPayoutResult:
        transaction = self._repo.find_by_id(transaction_id)
        if transaction is None:
            logger.error("ProcessPayoutUseCase: transaction %s introuvable", transaction_id)
            return ProcessPayoutResult(success=False)

        amount_xaf = transaction.amount_xaf  # déjà calculé, ne pas recalculer
        operator = transaction.operator
        momo_number = transaction.momo_number

        for attempt in range(1, self._max_retries + 1):
            try:
                payout = self._momo.send_payout(
                    momo_number, amount_xaf, transaction_id, operator
                )
            except Exception as exc:  # noqa: BLE001 - resilience path, resolved internally
                logger.warning(
                    "send_payout tentative %s/%s échouée pour %s: %s",
                    attempt, self._max_retries, transaction_id, exc,
                )
                if attempt < self._max_retries:
                    self._sleep(2 ** attempt)  # backoff 2, 4, 8, ...
                continue

            return self._on_success(transaction_id, momo_number, payout)

        return self._on_failure(transaction_id)

    # ------------------------------------------------------------------ outcomes
    def _on_success(self, transaction_id, momo_number, payout) -> ProcessPayoutResult:
        # Libère l'escrow on-chain, marque DELIVERED avec la référence payout.
        self._blockchain.escrow_release(transaction_id)
        self._repo.mark_delivered(transaction_id, payout.payout_id)

        # Une livraison réussie est le cas NORMAL : on rejoint le batch Merkle
        # périodique (pas de log_critical_event). Leaf discriminée pour ne pas
        # entrer en collision avec la feuille ESCROWED (KRYP-25).
        self._queue_delivered_audit_hash(transaction_id)

        notify_beneficiary_sms(
            momo_number,
            f"Votre transfert KRYPT {transaction_id} a été livré. Réf: {payout.payout_id}",
        )
        logger.info(
            "Transaction %s livrée (payout=%s)", transaction_id, payout.payout_id
        )
        return ProcessPayoutResult(success=True, payout_reference=payout.payout_id)

    def _on_failure(self, transaction_id) -> ProcessPayoutResult:
        # Chemin exceptionnel : remboursement escrow + événement critique temps réel.
        self._blockchain.escrow_refund(transaction_id)
        self._repo.mark_payout_failed(transaction_id)
        logger.error(
            "send_payout a échoué après %s tentatives pour %s → PAYOUT_FAILED (refund)",
            self._max_retries, transaction_id,
        )
        try:
            self._blockchain.log_critical_event(transaction_id, "PAYOUT_FAILED_REFUNDED")
        except Exception as exc:  # noqa: BLE001 - best-effort, ne jamais crasher
            logger.error("log_critical_event a échoué pour %s: %s", transaction_id, exc)
        return ProcessPayoutResult(success=False)

    def _queue_delivered_audit_hash(self, transaction_id) -> None:
        # Import local : garde le use case sans dépendance Django au niveau module.
        from web3 import Web3
        from contexts.blockchain.models import PendingAuditHash

        leaf_hash = Web3.keccak(text=f"{transaction_id}:DELIVERED").hex()
        if not leaf_hash.startswith("0x"):
            leaf_hash = "0x" + leaf_hash
        PendingAuditHash.objects.create(
            transaction_id=transaction_id,
            leaf_hash=leaf_hash,
        )
