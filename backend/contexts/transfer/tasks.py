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
            # KRYP-26 — funds secured on-chain: trigger the mobile-money payout.
            from .tasks import payout_task
            payout_task.delay(transaction_id)

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


@shared_task(bind=True, name="transfer.payout", max_retries=3)
def payout_task(self, transaction_id: str) -> dict:
    """KRYP-26 — Mobile-money payout after a successful escrow lock.

    Same outer-safety-net pattern as ``escrow_lock_task``: the Celery-native
    ``max_retries=3`` guards task-level infra failures only; the business retry
    loop lives inside ``ProcessPayoutUseCase`` (which never raises on a payout
    failure — it resolves to DELIVERED or PAYOUT_FAILED internally).
    """
    from contexts.blockchain.adapters.services.web3_blockchain_service import (
        Web3BlockchainService,
    )
    from contexts.mobile_money.adapters.services.mobile_money_factory import (
        get_mobile_money_service,
    )
    from .adapters.orm.django_transaction_repository import (
        DjangoORMTransactionRepository,
    )
    from .use_cases.process_payout import ProcessPayoutUseCase

    try:
        repo = DjangoORMTransactionRepository()
        transaction = repo.find_by_id(transaction_id)
        if transaction is None:
            logger.error("payout_task: transaction %s introuvable", transaction_id)
            return {"transaction_id": transaction_id, "success": False}

        use_case = ProcessPayoutUseCase(
            mobile_money_service=get_mobile_money_service(transaction.operator),
            blockchain_service=Web3BlockchainService(),
            transaction_repo=repo,
        )
        result = use_case.execute(transaction_id)
        return {
            "transaction_id": transaction_id,
            "success": result.success,
            "payout_reference": result.payout_reference,
        }
    except Exception as exc:  # noqa: BLE001 - task-level infra safety net
        logger.exception("payout_task infrastructure failure for %s", transaction_id)
        raise self.retry(exc=exc)


@shared_task(name="transfer.check_escrow_timeouts")
def check_escrow_timeouts_task() -> dict:
    """KRYP-26 — Hourly sweep: force-refund transfers stuck in ESCROWED > 24h.

    A transfer that has been ESCROWED for more than 24h without reaching
    DELIVERED is an anomaly (payout never completed). We refund the escrow
    on-chain, mark it PAYOUT_FAILED and emit an immediate critical audit event
    (same real-time reasoning as a payout failure — not a normal flow, so it
    does NOT wait for the 15-min Merkle batch).
    """
    from datetime import timedelta

    from django.utils import timezone

    from contexts.blockchain.adapters.services.web3_blockchain_service import (
        Web3BlockchainService,
    )
    from .adapters.orm.django_transaction_repository import (
        DjangoORMTransactionRepository,
    )
    from .models import TransactionModel, TransactionStatus

    cutoff = timezone.now() - timedelta(hours=24)
    stuck = TransactionModel.objects.filter(
        status=TransactionStatus.ESCROWED.value,
        escrowed_at__lt=cutoff,
    )

    blockchain = Web3BlockchainService()
    repo = DjangoORMTransactionRepository()
    processed = 0
    for txn in stuck:
        transaction_id = str(txn.id)
        try:
            blockchain.escrow_refund(transaction_id)
        except Exception as exc:  # noqa: BLE001 - best-effort per transaction
            logger.error(
                "check_escrow_timeouts: escrow_refund a échoué pour %s: %s",
                transaction_id, exc,
            )
        repo.mark_payout_failed(transaction_id)
        try:
            blockchain.log_critical_event(transaction_id, "ESCROW_TIMEOUT_REFUNDED")
        except Exception as exc:  # noqa: BLE001 - best-effort
            logger.error(
                "check_escrow_timeouts: log_critical_event a échoué pour %s: %s",
                transaction_id, exc,
            )
        processed += 1

    if processed:
        logger.warning("check_escrow_timeouts: %s transfert(s) remboursé(s) (>24h).", processed)
    return {"refunded": processed}
