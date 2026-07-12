"""
KRYP-25 — Test d'intégration Escrow sur le testnet Polygon Amoy (RPC réel).

Marqué `@pytest.mark.integration` : EXCLU du run standard. Il n'est exécuté que
via `pytest -m integration` et nécessite de vraies credentials Amoy
(AMOY_RPC_URL / PRIVATE_KEY, exposées via settings.BLOCKCHAIN_*).

  - Standard (rapide, aucun appel réseau) : pytest -m "not integration"
  - Amoy (appel on-chain réel)            : pytest -m integration

Sans credentials valides, le test SKIP proprement — il ne doit jamais échouer
faute de secret (même motif que tests_stripe_integration.py).
"""
import secrets

import pytest
from django.conf import settings


@pytest.mark.integration
def test_escrow_lock_real_testnet():
    rpc_url = getattr(settings, "BLOCKCHAIN_RPC_URL", "") or ""
    private_key = getattr(settings, "BLOCKCHAIN_PRIVATE_KEY", "") or ""
    if not rpc_url or not private_key:
        pytest.skip(
            "AMOY_RPC_URL / PRIVATE_KEY absents — test d'intégration Amoy ignoré."
        )
    if not private_key.startswith("0x") or len(private_key) != 66:
        pytest.skip("PRIVATE_KEY ne ressemble pas à une clé 32 octets — ignoré.")

    from contexts.blockchain.adapters.services.web3_blockchain_service import (
        Web3BlockchainService,
    )

    # transferId aléatoire (32 octets) : Escrow.lock() reverte si le statut du
    # transferId n'est pas NONE (TransferNotLocked/AlreadyExists). Un id frais à
    # chaque run évite un revert « already locked » d'une exécution précédente.
    transfer_id = "0x" + secrets.token_hex(32)

    tx_hash = Web3BlockchainService().escrow_lock(transfer_id, 100)

    assert isinstance(tx_hash, str)
    assert tx_hash.startswith("0x")
