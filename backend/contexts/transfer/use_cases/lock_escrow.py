"""KRYP-25 — Real-time escrow lock after Stripe confirmation.

Hexagonal use case: no Django imports. Depends only on the injected
``BlockchainServicePort`` and a transaction repository (duck-typed on
``DjangoORMTransactionRepository``: ``find_by_id`` / ``mark_escrowed`` /
``update_status``).

Escrow locking is the critical fund-state path (mémoire ch.2, bounded context
Transfert). Unlike AuditTrail — which is Merkle-batched every 15 min to preserve
the 0.9-1% fee-competitiveness target (mémoire ch.1, Phase 2, comparable à
TapTap Send) — the escrow lock reflects on-chain state immediately and is never
batched. It therefore carries its own bounded retry loop around the blockchain
call; the outer Celery task retry is a separate, task-level safety net.
"""
import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from contexts.blockchain.ports.blockchain_service import BlockchainServicePort
from ..domain.entities import TransactionStatus

logger = logging.getLogger(__name__)


@dataclass
class LockEscrowResult:
    success: bool
    tx_hash: Optional[str] = None


class LockEscrowUseCase:
    def __init__(
        self,
        blockchain_service: BlockchainServicePort,
        transaction_repo,
        max_retries: int = 3,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        self._blockchain = blockchain_service
        self._repo = transaction_repo
        self._max_retries = max_retries
        self._sleep = sleep_fn

    def execute(self, transaction_id: str) -> LockEscrowResult:
        transaction = self._repo.find_by_id(transaction_id)
        if transaction is None:
            logger.error("LockEscrowUseCase: transaction %s introuvable", transaction_id)
            return LockEscrowResult(success=False)

        amount_cents = int(transaction.amount_eur * 100)

        for attempt in range(1, self._max_retries + 1):
            try:
                tx_hash = self._blockchain.escrow_lock(transaction_id, amount_cents)
            except Exception as exc:  # noqa: BLE001 - resilience path, always resolved internally
                logger.warning(
                    "escrow_lock tentative %s/%s échouée pour %s: %s",
                    attempt, self._max_retries, transaction_id, exc,
                )
                if attempt < self._max_retries:
                    # Backoff croissant monotone (2, 4, 8, ... secondes).
                    self._sleep(2 ** attempt)
                continue

            self._repo.mark_escrowed(transaction_id, tx_hash)
            logger.info("Transaction %s verrouillée on-chain (tx=%s)", transaction_id, tx_hash)
            return LockEscrowResult(success=True, tx_hash=tx_hash)

        # Toutes les tentatives ont échoué : statut ESCROW_FAILED (Fig. 7).
        self._repo.update_status(transaction_id, TransactionStatus.ESCROW_FAILED)
        logger.error(
            "escrow_lock a échoué après %s tentatives pour la transaction %s "
            "→ ESCROW_FAILED (notification: KRYP-30 s'en chargera)",
            self._max_retries, transaction_id,
        )
        # Signal critique temps réel (best-effort) : ne jamais faire échouer le
        # use case si cet appel secondaire échoue lui aussi.
        try:
            self._blockchain.log_critical_event(transaction_id, "ESCROW_LOCK_FAILED")
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "log_critical_event a échoué pour %s: %s", transaction_id, exc
            )

        return LockEscrowResult(success=False)
