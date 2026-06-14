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
        )
        obj.save()
        return self._to_entity(obj)

    def find_by_transfer_id(self, transfer_id: str) -> Optional[AMLResult]:
        try:
            obj = AMLResultModel.objects.get(transfer_id=transfer_id)
            return self._to_entity(obj)
        except AMLResultModel.DoesNotExist:
            return None

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
        )
