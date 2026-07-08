"""
KRYP-26 — Test d'intégration MTN MoMo Remittance sandbox (API réelle).

Marqué `@pytest.mark.integration` : EXCLU du run standard. Il n'est exécuté que
via `pytest -m integration` et nécessite de vraies credentials sandbox MTN
(MTN_SUBSCRIPTION_KEY / MTN_API_USER / MTN_API_KEY, exposées via settings).

  - Standard (rapide, aucun appel réseau) : pytest -m "not integration"
  - Sandbox MTN (appel réel)              : pytest -m integration

Sans credentials valides, le test SKIP proprement — il ne doit jamais échouer
faute de secret (même motif que tests_stripe_integration.py /
tests_escrow_integration.py).

Choix : on exerce `validate_account` (GET account-status) plutôt que
`send_payout`. C'est l'appel réel le moins risqué / le plus cheap pour prouver la
connectivité + l'auth OAuth2 sans dépendre d'un MSISDN destinataire pleinement
valide côté sandbox. La validation d'un vrai payout est déférée au run crédenté
de l'utilisateur (source de vérité ultime, cf. docstring de l'adaptateur : la
console Remittance est session-gated).
"""
import pytest
from django.conf import settings


@pytest.mark.integration
def test_mtn_payout_real_sandbox():
    subscription_key = getattr(settings, "MTN_SUBSCRIPTION_KEY", "") or ""
    api_user = getattr(settings, "MTN_API_USER", "") or ""
    api_key = getattr(settings, "MTN_API_KEY", "") or ""
    if not subscription_key or not api_user or not api_key:
        pytest.skip(
            "MTN_SUBSCRIPTION_KEY / MTN_API_USER / MTN_API_KEY absents — "
            "test d'intégration MTN sandbox ignoré."
        )

    from contexts.mobile_money.adapters.services.mtn_momo_service import (
        MTNMoMoService,
    )

    service = MTNMoMoService()
    # MSISDN de test sandbox : la validation renvoie un booléen ; on vérifie
    # surtout que l'auth + la connectivité fonctionnent (pas d'exception réseau).
    result = service.validate_account("46733123453", "MTN_MOMO")
    assert isinstance(result, bool)
