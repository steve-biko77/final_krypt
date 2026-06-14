import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class DocumentType(str, Enum):
    ID_CARD = "ID_CARD"
    PASSPORT = "PASSPORT"
    RESIDENCE_PERMIT = "RESIDENCE_PERMIT"


class KYCStatus(str, Enum):
    SUBMITTED = "SUBMITTED"             # Soumis, avant analyse IA
    ANALYZING = "ANALYZING"             # Analyse IA en cours
    APPROVED = "APPROVED"               # Validé automatiquement (score >= seuil)
    PENDING_REVIEW = "PENDING_REVIEW"   # Validation manuelle requise (score < seuil)
    APPROVED_MANUAL = "APPROVED_MANUAL" # Validé manuellement par un admin
    COMPLEMENT_REQUESTED = "COMPLEMENT_REQUESTED"  # Complément de documents demandé
    REJECTED = "REJECTED"               # Rejeté par un admin


@dataclass
class KYCDocument:
    user_id: str
    document_type: DocumentType
    file_path: str
    status: KYCStatus = KYCStatus.ANALYZING
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    analysis_score: Optional[float] = None
    analysis_details: Optional[dict] = None
    reviewed_by_id: Optional[str] = None
    review_comment: Optional[str] = None
