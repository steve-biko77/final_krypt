from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from ..domain.entities import TransferSimulation
from ..domain.exceptions import InvalidAmountError
from ..ports.exchange_rate_service import ExchangeRateServicePort

_MIN_AMOUNT = Decimal("5")
_MAX_AMOUNT = Decimal("5000")
_FEE_RATE = Decimal("0.015")   # 1.5% flat (Fig. 5)
_TWO_PLACES = Decimal("0.01")


@dataclass
class SimulateTransferInput:
    amount_eur: Decimal


class SimulateTransferUseCase:
    def __init__(self, exchange_rate_service: ExchangeRateServicePort):
        self._exchange_rate_service = exchange_rate_service

    def execute(self, data: SimulateTransferInput) -> TransferSimulation:
        amount = data.amount_eur

        if amount < _MIN_AMOUNT:
            raise InvalidAmountError(f"Le montant minimum est {_MIN_AMOUNT} EUR.")
        if amount > _MAX_AMOUNT:
            raise InvalidAmountError(f"Le montant maximum est {_MAX_AMOUNT} EUR.")

        fees_eur = (amount * _FEE_RATE).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        net_eur = (amount - fees_eur).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        exchange_rate = self._exchange_rate_service.get_rate("EUR", "XAF")
        amount_xaf = (net_eur * exchange_rate).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

        return TransferSimulation(
            amount_eur=amount,
            fees_eur=fees_eur,
            fees_percentage=_FEE_RATE * 100,
            net_eur=net_eur,
            exchange_rate=exchange_rate,
            amount_xaf=amount_xaf,
        )
