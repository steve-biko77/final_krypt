"""KRYP-25 — Periodic Merkle-batch submission of audit hashes to AuditTrail.

Runs every 15 minutes (CELERY_BEAT_SCHEDULE). Groups all unbatched
``PendingAuditHash`` rows into a sorted-pair keccak256 Merkle tree and commits
the single root on-chain — never one event per transfer (mémoire ch.1 Phase 2:
0.9-1% fee-competitiveness target, comparable TapTap Send).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="blockchain.submit_audit_batch")
def submit_audit_batch_task() -> dict:
    from .adapters.services.web3_blockchain_service import Web3BlockchainService
    from .domain.merkle import MerkleTree
    from .models import PendingAuditHash

    pending = list(PendingAuditHash.objects.filter(batched=False).order_by("created_at"))
    if not pending:
        # Rien à soumettre : aucun appel on-chain (économie de gas/frais).
        logger.info("submit_audit_batch: aucun hash en attente, rien à soumettre.")
        return {"submitted": False, "count": 0}

    leaves = [row.leaf_hash for row in pending]
    tree = MerkleTree(leaves)
    root_hex = tree.root_hex()

    period_start = int(min(row.created_at for row in pending).timestamp())
    period_end = int(max(row.created_at for row in pending).timestamp())

    # KRYP-37 — periodStart (déjà un paramètre de submitBatch) sert directement
    # de batchId, plutôt qu'un compteur local ("max+1") : ce compteur repart de
    # zéro à chaque DB de test recréée alors que le compteur on-chain persiste
    # entre les runs, provoquant un BatchAlreadyExists sur des runs e2e_real
    # répétés. periodStart ne dépend d'aucun état local à synchroniser avec la
    # chaîne — deux batches ne peuvent pas partager le même periodStart à la
    # seconde près en usage réaliste (fenêtres de 15 min), donc les collisions
    # deviennent pratiquement impossibles. AuditTrail.batchId est un uint256 sans
    # contrainte de séquence, seulement d'unicité (cf. AuditTrail.sol).
    batch_id = period_start

    tx_hash = Web3BlockchainService().submit_audit_batch(
        batch_id, root_hex, len(pending), period_start, period_end
    )

    # KRYP-27 — persister par ligne : le batch (batched/batch_id/batch_tx_hash sont
    # identiques pour tout le lot) ET la preuve de Merkle individuelle (différente
    # par ligne, donc pas de bulk .update()). tree.proof() renvoie une liste de
    # bytes ; on la convertit en chaînes hex ("0x…") conformément à la convention
    # du port BlockchainServicePort.
    for row in pending:
        row.batched = True
        row.batch_id = batch_id
        row.batch_tx_hash = tx_hash
        row.merkle_proof = ["0x" + node.hex() for node in tree.proof(row.leaf_hash)]
    PendingAuditHash.objects.bulk_update(
        pending, ["batched", "batch_id", "batch_tx_hash", "merkle_proof"]
    )

    logger.info(
        "submit_audit_batch: batch %s soumis (%s hashes, tx=%s)",
        batch_id, len(pending), tx_hash,
    )
    return {
        "submitted": True,
        "batch_id": batch_id,
        "count": len(pending),
        "merkle_root": root_hex,
        "tx_hash": tx_hash,
    }
