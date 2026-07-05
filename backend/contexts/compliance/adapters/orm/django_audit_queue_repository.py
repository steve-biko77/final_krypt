import uuid

from ...models import AuditQueueModel
from ...ports.audit_queue_service import AuditQueueServicePort


class DjangoAuditQueueRepository(AuditQueueServicePort):
    """Adapter Django du port AuditQueueServicePort (Couche 4 — audit a posteriori)."""

    def enqueue(
        self,
        sender_id: str,
        transfer_id: str,
        aml_result_id: str,
        tag_ml_score: float,
    ) -> None:
        AuditQueueModel.objects.create(
            sender_id=uuid.UUID(sender_id),
            transfer_id=str(transfer_id),
            aml_result_id=str(aml_result_id),
            tag_ml_score=tag_ml_score,
        )
