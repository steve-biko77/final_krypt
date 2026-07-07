"""KRYP-25 — Transfer Celery tasks.

``escrow_lock_task`` is dispatched from the Stripe webhook on
``payment_intent.succeeded``. It performs the real-time on-chain escrow lock
(Fig. 7: ``PROCESSING → ESCROWED``, now realized asynchronously) and, on
success, enqueues the transfer's audit hash for the periodic Merkle batch.

Two distinct retry mechanisms — do not conflate them:
  - ``LockEscrowUseCase`` retries the blockchain call itself (fund-state path);
    it never raises on a blockchain failure, always resolving to ESCROWED or
    ESCROW_FAILED internally.
  - This task's Celery-native ``max_retries=3`` is an outer safety net for
    task-level infrastructure failures (e.g. DB hiccups) only.
"""
import logging

from celery import shared_task
from web3 import Web3

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="transfer.escrow_lock", max_retries=3)
def escrow_lock_task(self, transaction_id: str) -> dict:
    from contexts.blockchain.adapters.services.web3_blockchain_service import (
        Web3BlockchainService,
    )
    from contexts.blockchain.models import PendingAuditHash
    from .adapters.orm.django_transaction_repository import (
        DjangoORMTransactionRepository,
    )
    from .use_cases.lock_escrow import LockEscrowUseCase

    try:
        use_case = LockEscrowUseCase(
            blockchain_service=Web3BlockchainService(),
            transaction_repo=DjangoORMTransactionRepository(),
        )
        result = use_case.execute(transaction_id)

        if result.success:
            # Enqueue the audit leaf for the next 15-min Merkle batch. Leaf is a
            # deterministic keccak256 of the transfer id (traceable off-chain).
            leaf_hash = Web3.keccak(text=transaction_id).hex()
            if not leaf_hash.startswith("0x"):
                leaf_hash = "0x" + leaf_hash
            PendingAuditHash.objects.create(
                transaction_id=transaction_id,
                leaf_hash=leaf_hash,
            )

        return {
            "transaction_id": transaction_id,
            "success": result.success,
            "escrow_tx_hash": result.tx_hash,
        }
    except Exception as exc:  # noqa: BLE001 - task-level infra safety net
        logger.exception(
            "escrow_lock_task infrastructure failure for %s", transaction_id
        )
        raise self.retry(exc=exc)
