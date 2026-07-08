"""KRYP-26 — Operator → adapter selection for mobile-money payouts."""
from ...ports.mobile_money_service import MobileMoneyServicePort
from .mtn_momo_service import MTNMoMoService
from .orange_money_mock_service import OrangeMoneyMockService


def get_mobile_money_service(operator: str) -> MobileMoneyServicePort:
    """Return the payout adapter for ``operator``.

    ``MTN_MOMO`` → real MTN MoMo Remittance adapter.
    ``ORANGE_MONEY`` → permanent mock (no reachable Orange sandbox).
    """
    if operator == "MTN_MOMO":
        return MTNMoMoService()
    if operator == "ORANGE_MONEY":
        return OrangeMoneyMockService()
    raise ValueError(f"Opérateur mobile money inconnu : {operator!r}")
