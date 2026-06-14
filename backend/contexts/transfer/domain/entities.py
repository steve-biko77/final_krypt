from dataclasses import dataclass
from decimal import Decimal


@dataclass
class TransferSimulation:
    amount_eur: Decimal
    fees_eur: Decimal
    fees_percentage: Decimal
    net_eur: Decimal
    exchange_rate: Decimal
    amount_xaf: Decimal
