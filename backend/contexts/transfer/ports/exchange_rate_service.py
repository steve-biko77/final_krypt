from abc import ABC, abstractmethod
from decimal import Decimal


class ExchangeRateServicePort(ABC):
    @abstractmethod
    def get_rate(self, from_currency: str, to_currency: str) -> Decimal:
        """Return the exchange rate from_currency → to_currency."""
