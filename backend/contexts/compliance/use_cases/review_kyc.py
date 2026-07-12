from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..domain.entities import KYCDocument, KYCStatus
from ..domain.exceptions import KYCDocumentNotFoundError, KYCInvalidStatusTransitionError
from ..ports.kyc_repository import KYCDocumentRepository

_REVIEWABLE_STATUSES = {KYCStatus.PENDING_REVIEW, KYCStatus.ANALYZING}
_ALLOWED_DECISIONS = {KYCStatus.APPROVED_MANUAL, KYCStatus.COMPLEMENT_REQUESTED, KYCStatus.REJECTED}


@dataclass
class ReviewKYCInput:
    document_id: str
    new_status: KYCStatus
    reviewed_by_id: Optional[str] = None
    comment: Optional[str] = None


class ReviewKYCUseCase:
    def __init__(self, kyc_repo: KYCDocumentRepository):
        self._kyc_repo = kyc_repo

    def execute(self, data: ReviewKYCInput) -> KYCDocument:
        doc = self._kyc_repo.find_by_id(data.document_id)
        if not doc:
            raise KYCDocumentNotFoundError(f"Document {data.document_id} not found")

        if doc.status not in _REVIEWABLE_STATUSES:
            raise KYCInvalidStatusTransitionError(
                f"Cannot review document with status {doc.status.value}"
            )

        if data.new_status not in _ALLOWED_DECISIONS:
            raise KYCInvalidStatusTransitionError(
                "Decision must be APPROVED, COMPLEMENT_REQUESTED or REJECTED"
            )

        if data.new_status == KYCStatus.REJECTED and not (data.comment or "").strip():
            raise KYCInvalidStatusTransitionError(
                "A comment is required when rejecting a document"
            )

        doc.status = data.new_status
        doc.reviewed_at = datetime.now(timezone.utc)
        doc.reviewed_by_id = data.reviewed_by_id
        doc.review_comment = data.comment

        return self._kyc_repo.save(doc)
