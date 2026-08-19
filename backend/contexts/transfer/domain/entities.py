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
    ESCROW_FAILED = "ESCROW_FAILED"
    DELIVERED = "DELIVERED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYOUT_FAILED = "PAYOUT_FAILED"
    CANCELLED = "CANCELLED"
    AWAITING_DOCS = "AWAITING_DOCS"
    ESCALATED = "ESCALATED"


@dataclass
class SavedBeneficiary:
    """Carnet de contacts — bénéficiaire enregistré par un utilisateur pour
    resélection rapide dans le tunnel de transfert (jamais créé sans action
    explicite : voir SaveBeneficiaryUseCase, appelé uniquement si l'utilisateur
    a coché "Enregistrer ce bénéficiaire")."""

    user_id: str
    beneficiary_name: str
    beneficiary_country: str
    momo_number: str
    operator: str  # Literal["MTN_MOMO", "ORANGE_MONEY"]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


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
    escrow_tx_hash: Optional[str] = None
    escrowed_at: Optional[datetime] = None
    payout_reference: Optional[str] = None
    admin_review_tx_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
