"""KRYP-30 — Notification bounded context (Fig. 12/18).

Pure domain: no Django imports, no persistence. A notification is never stored —
it is emitted once and forgotten (no read model, no "notification history" table
in this ticket's scope).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class NotificationEventType(str, Enum):
    USER_REGISTERED = "USER_REGISTERED"
    KYC_APPROVED = "KYC_APPROVED"
    TRANSFER_INITIATED = "TRANSFER_INITIATED"
    TRANSFER_DELIVERED = "TRANSFER_DELIVERED"
    TRANSFER_FAILED = "TRANSFER_FAILED"


@dataclass
class NotificationEvent:
    """A single notification to emit.

    ``context`` carries the template data (beneficiary name, amount, tracking
    link, ...) — deliberately a free-form dict rather than fixed fields, since
    each event type needs a different shape (Fig. 12/18: one port, many event
    shapes). ``recipient_name`` is kept separate because every template uses it
    for the greeting line, regardless of event type.
    """
    type: NotificationEventType
    recipient_name: str
    context: Dict[str, Any] = field(default_factory=dict)
