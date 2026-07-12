import uuid
from typing import Optional

from ...domain.entities import AMLDecision, AMLResult
from ...models import AMLResultModel


class DjangoORMAMLRepository:
    def save(self, result: AMLResult) -> AMLResult:
        obj = AMLResultModel(
            id=uuid.UUID(result.id),
            transfer_id=result.transfer_id,
            user_id=uuid.UUID(result.user_id),
            xgboost_score=result.xgboost_score,
            ofac_match=result.ofac_match,
            ofac_details=result.ofac_details or {},
            combined_decision=result.combined_decision.value,
            reviewed_by_id=uuid.UUID(result.reviewed_by_id) if result.reviewed_by_id else None,
            review_decision=result.review_decision,
            audit_hash=result.audit_hash,
            is_new_beneficiary=result.is_new_beneficiary,
            sender_tx_count_30d=result.sender_tx_count_30d,
            tag_ml_score=result.tag_ml_score,
            triggered_rules=result.triggered_rules or [],
        )
        obj.save()
        return self._to_entity(obj)

    def find_by_transfer_id(self, transfer_id: str) -> Optional[AMLResult]:
        try:
            obj = AMLResultModel.objects.get(transfer_id=transfer_id)
            return self._to_entity(obj)
        except AMLResultModel.DoesNotExist:
            return None

    def find_by_id(self, id: str) -> Optional[AMLResult]:
        try:
            obj = AMLResultModel.objects.get(pk=uuid.UUID(id))
            return self._to_entity(obj)
        except (AMLResultModel.DoesNotExist, ValueError):
            return None

    def update_review(self, id: str, reviewed_by_id: str, review_decision: str) -> None:
        """KRYP-31 — Persist the admin's decision on an EXISTING result row via a
        real UPDATE. Never call ``save()`` for this: it always constructs a brand
        new ``AMLResultModel`` from the dataclass, which would insert a second row
        for the same ``transfer_id`` rather than update the scored one."""
        AMLResultModel.objects.filter(pk=uuid.UUID(id)).update(
            reviewed_by_id=uuid.UUID(reviewed_by_id),
            review_decision=review_decision,
        )

    def _to_entity(self, obj: AMLResultModel) -> AMLResult:
        return AMLResult(
            id=str(obj.pk),
            transfer_id=obj.transfer_id,
            user_id=str(obj.user_id),
            xgboost_score=obj.xgboost_score,
            ofac_match=obj.ofac_match,
            ofac_details=obj.ofac_details or {},
            combined_decision=AMLDecision(obj.combined_decision),
            reviewed_by_id=str(obj.reviewed_by_id) if obj.reviewed_by_id else None,
            review_decision=obj.review_decision,
            audit_hash=obj.audit_hash,
            created_at=obj.created_at,
            is_new_beneficiary=obj.is_new_beneficiary,
            sender_tx_count_30d=obj.sender_tx_count_30d,
            tag_ml_score=obj.tag_ml_score,
            triggered_rules=obj.triggered_rules or [],
        )
