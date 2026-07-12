"""
KRYP-23 — Test d'intégration Stripe sandbox (API réelle).

Marqué `@pytest.mark.integration` : EXCLU du run standard. Il n'est exécuté que
via `pytest -m integration` et nécessite une vraie clé test Stripe.

  - Standard (rapide, aucun appel réseau)  : pytest -m "not integration"
  - Sandbox Stripe (appel réel)            : pytest -m integration

Sans `STRIPE_SECRET_KEY` valide (préfixe `sk_test_`), le test SKIP proprement —
il ne doit jamais échouer faute de secret (CI/local sans creds).
"""
import os
import uuid
from decimal import Decimal

import pytest
from django.conf import settings


@pytest.mark.integration
@pytest.mark.django_db
def test_stripe_sandbox_create_payment_intent_real():
    key = getattr(settings, "STRIPE_SECRET_KEY", "") or os.environ.get("STRIPE_SECRET_KEY", "")
    if not key or not key.startswith("sk_test_"):
        pytest.skip(
            "STRIPE_SECRET_KEY absente ou non test (préfixe sk_test_ requis) — "
            "test sandbox ignoré."
        )

    from contexts.transfer.adapters.services.stripe_payment_service import (
        StripePaymentService,
    )

    result = StripePaymentService().create_payment_intent(
        Decimal("10.00"), f"test-integration-{uuid.uuid4()}"
    )

    assert result.payment_intent_id.startswith("pi_")
    assert isinstance(result.client_secret, str) and result.client_secret
    assert result.client_secret.startswith("pi_")
