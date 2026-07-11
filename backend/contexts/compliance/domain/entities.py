import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class AMLDecision(str, Enum):
    HARD_BLOCK = "HARD_BLOCK"           # Match OFAC/EU confirmé → blocage immédiat
    AUTO_APPROVED = "AUTO_APPROVED"     # Score < 0.3 ET pas d'OFAC → approuvé
    AUTO_BLOCKED = "AUTO_BLOCKED"       # Score > 0.7 → bloqué
    PENDING_REVIEW = "PENDING_REVIEW"   # Score 0.3-0.7 → révision admin
    MANUALLY_APPROVED = "MANUALLY_APPROVED"
    MANUALLY_REJECTED = "MANUALLY_REJECTED"
    ESCALATED = "ESCALATED"  # KRYP-31 — envoyé en revue de second niveau (Fig. 10)


@dataclass
class AMLResult:
    transfer_id: str
    user_id: str
    xgboost_score: float
    ofac_match: bool
    ofac_details: dict
    combined_decision: AMLDecision
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reviewed_by_id: Optional[str] = None
    review_decision: Optional[str] = None
    audit_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    # Architecture de décision 4 couches (KRYP-22 v2, seuils_production.md) :
    # features comportementales (loggées, réentraînement futur) + tag ML shadow
    # + règles métier déclenchées (traçabilité audit Couche 1).
    is_new_beneficiary: bool = False
    sender_tx_count_30d: int = 0
    tag_ml_score: float = 0.0
    triggered_rules: list = field(default_factory=list)


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
