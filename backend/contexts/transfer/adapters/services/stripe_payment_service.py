from decimal import Decimal

import stripe
from django.conf import settings

from ...domain.exceptions import PaymentServiceError
from ...ports.payment_service import PaymentIntentResult, PaymentServicePort


class StripePaymentService(PaymentServicePort):
    """Stripe implementation of the payment port.

    Stripe amounts are expressed in the currency's smallest unit (cents for EUR).
    api_key is set at call time (not import time) so tests can override settings.

    Provider-specific `stripe.error.StripeError`s are wrapped in the port-level
    `PaymentServiceError` so no Stripe type leaks past this boundary.
    """

    def create_payment_intent(
        self, amount_eur: Decimal, transaction_id: str
    ) -> PaymentIntentResult:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount_eur * 100),
                currency="eur",
                metadata={"transaction_id": transaction_id},
            )
        except stripe.error.StripeError as exc:
            raise PaymentServiceError(str(exc)) from exc
        return PaymentIntentResult(
            payment_intent_id=intent.id,
            client_secret=intent.client_secret,
        )

    def confirm_payment(self, payment_intent_id: str) -> bool:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        except stripe.error.StripeError as exc:
            raise PaymentServiceError(str(exc)) from exc
        return intent.status == "succeeded"

    def cancel_payment_intent(self, payment_intent_id: str) -> None:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            stripe.PaymentIntent.cancel(payment_intent_id)
        except stripe.error.StripeError as exc:
            raise PaymentServiceError(str(exc)) from exc
