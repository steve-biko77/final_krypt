import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


@dataclass
class TransferSimulation:
    amount_eur: Decimal
    fees_eur: Decimal
    fees_percentage: Decimal
    net_eur: Decimal
    exchange_rate: Decimal
    amount_xaf: Decimal


class TransactionStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_AML = "PENDING_AML"
    AML_BLOCKED = "AML_BLOCKED"
    AML_PENDING_REVIEW = "AML_PENDING_REVIEW"
    PROCESSING = "PROCESSING"
    ESCROWED = "ESCROWED"
    DELIVERED = "DELIVERED"
    PAYMENT_FAILED = "PAYMENT_FAILED"


@dataclass
class Transaction:
    sender_id: str
    beneficiary_name: str
    beneficiary_country: str
    momo_number: str
    operator: str  # Literal["MTN_MOMO", "ORANGE_MONEY"]
    amount_eur: Decimal
    fees_eur: Decimal
    amount_xaf: Decimal
    status: TransactionStatus = TransactionStatus.DRAFT
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    aml_result_id: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
