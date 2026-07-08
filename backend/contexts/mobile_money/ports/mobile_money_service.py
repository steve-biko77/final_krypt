"""KRYP-26 — Mobile Money payout port (bounded context Mobile Money).

Shared port implemented by both a real MTN MoMo Remittance adapter and a
permanently-mocked Orange Money adapter (Orange has no reachable sandbox — see
``OrangeMoneyMockService``). The payout is the final leg of a transfer: after the
EUR funds are locked in escrow (KRYP-25), the equivalent XAF is disbursed to the
beneficiary's mobile-money wallet.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PayoutResult:
    """Outcome of a payout request to a mobile-money operator.

    ``payout_id`` is the operator-side reference (MTN's ``X-Reference-Id`` /
    Orange's mock id) used later for status polling and traceability. ``status``
    is the operator's raw status string (e.g. ``"SUCCESSFUL"``/``"PENDING"``).
    """

    payout_id: str
    status: str


class MobileMoneyServicePort(ABC):
    """Port for disbursing an XAF payout to a mobile-money wallet.

    ``operator`` is redundant on a per-operator adapter instance (each concrete
    adapter only ever serves its own operator) but is kept in every signature
    because the port is shared by both adapters; each adapter asserts it matches
    its own operator internally.
    """

    @abstractmethod
    def validate_account(self, momo_number: str, operator: str) -> bool:
        """Return True if ``momo_number`` is an active wallet for ``operator``."""

    @abstractmethod
    def send_payout(
        self,
        momo_number: str,
        amount_xaf: Decimal,
        transfer_id: str,
        operator: str,
    ) -> PayoutResult:
        """Disburse ``amount_xaf`` to ``momo_number``. Returns a PayoutResult."""

    @abstractmethod
    def get_payout_status(self, payout_id: str, operator: str) -> str:
        """Return the operator's current status string for ``payout_id``."""
