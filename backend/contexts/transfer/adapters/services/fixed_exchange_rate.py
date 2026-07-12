from decimal import Decimal

from ...ports.exchange_rate_service import ExchangeRateServicePort

# XAF is pegged to EUR at the fixed CFA franc rate (Banque de France)
# Production will replace this with a live interbank API call.
_RATES: dict[tuple[str, str], Decimal] = {
    ("EUR", "XAF"): Decimal("655.957"),
}


class FixedExchangeRateService(ExchangeRateServicePort):
    def get_rate(self, from_currency: str, to_currency: str) -> Decimal:
        key = (from_currency.upper(), to_currency.upper())
        rate = _RATES.get(key)
        if rate is None:
            raise ValueError(f"Taux de change non disponible : {from_currency}/{to_currency}")
        return rate
