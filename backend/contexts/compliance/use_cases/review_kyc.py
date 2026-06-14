from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from ..domain.entities import KYCDocument, KYCStatus
from ..domain.exceptions import KYCDocumentNotFoundError, KYCInvalidStatusTransitionError
from ..ports.kyc_repository import KYCDocumentRepository

_REVIEWABLE_STATUSES = {KYCStatus.PENDING, KYCStatus.PENDING_REVIEW, KYCStatus.ANALYZING}


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

        if data.new_status not in (KYCStatus.APPROVED, KYCStatus.REJECTED):
            raise KYCInvalidStatusTransitionError("Status must be APPROVED or REJECTED")

        doc.status = data.new_status
        doc.reviewed_at = datetime.now(timezone.utc)
        doc.reviewed_by_id = data.reviewed_by_id
        doc.review_comment = data.comment

        return self._kyc_repo.save(doc)
