import uuid

from django.db import models


class PendingAuditHash(models.Model):
    """KRYP-25 — A single off-chain transfer audit hash awaiting Merkle batching.

    Escrow-locked transfers enqueue one row here (leaf = keccak256 of the transfer
    id). ``submit_audit_batch_task`` groups all unbatched rows into a Merkle tree
    every 15 minutes and commits the root to AuditTrail on-chain, then marks the
    rows ``batched`` with the assigned ``batch_id``.
    """

    # KRYP-27 — un même transfert produit deux lignes au cours de son cycle de
    # vie, partageant le même ``transaction_id`` : la feuille ESCROWED (verrou
    # escrow) et la feuille DELIVERED (payout). ``event_type`` lève l'ambiguïté
    # pour retrouver le batch de l'événement de livraison spécifiquement.
    EVENT_ESCROWED = "ESCROWED"
    EVENT_DELIVERED = "DELIVERED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = models.CharField(max_length=100, db_index=True)
    event_type = models.CharField(max_length=20, default="", blank=True)
    leaf_hash = models.CharField(max_length=66)
    batched = models.BooleanField(default=False, db_index=True)
    batch_id = models.IntegerField(null=True, blank=True)
    # KRYP-27 — hash de la transaction Polygon du batch (preuve d'inclusion),
    # et preuve de Merkle par ligne (persistée uniquement, non exposée par l'API).
    batch_tx_hash = models.CharField(max_length=100, null=True, blank=True)
    merkle_proof = models.JSONField(null=True, blank=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "blockchain"
        db_table = "blockchain_pending_audit_hashes"
        ordering = ["created_at"]

    def __str__(self):
        return f"PendingAuditHash({self.transaction_id}, batched={self.batched})"
