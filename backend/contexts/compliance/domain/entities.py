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
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class KYCDocument:
    user_id: str
    document_type: DocumentType
    file_path: str
    status: KYCStatus = KYCStatus.PENDING
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
