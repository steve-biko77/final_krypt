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
    # KRYP-31 — console admin AML (Fig. 10). Les deux ADMIN_ALERT_* ne
    # correspondent à aucun UserModel réel (destinataire configuré via
    # settings.COMPLIANCE_MANAGER_EMAIL) — voir admin_alert_task, qui contourne
    # délibérément la résolution UserModel de notification_task.
    ADMIN_ALERT_PENDING_REVIEW = "ADMIN_ALERT_PENDING_REVIEW"
    ADMIN_ALERT_ESCALATED = "ADMIN_ALERT_ESCALATED"
    DOCS_REQUESTED = "DOCS_REQUESTED"


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
