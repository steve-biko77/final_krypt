from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PaymentIntentResult:
    payment_intent_id: str
    client_secret: str


class PaymentServicePort(ABC):
    @abstractmethod
    def create_payment_intent(
        self, amount_eur: Decimal, transaction_id: str
    ) -> PaymentIntentResult:
        """Create a payment intent for the given EUR amount and return its id + client secret."""

    @abstractmethod
    def confirm_payment(self, payment_intent_id: str) -> bool:
        """Return True if the payment intent has succeeded."""
