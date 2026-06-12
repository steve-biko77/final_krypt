import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    email: str
    first_name: str
    last_name: str
    phone: str
    password_hash: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    is_kyc_verified: bool = False
    created_at: Optional[datetime] = None
