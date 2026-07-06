"""KRYP-24 — Tests for the blockchain audit/escrow adapter.

These tests NEVER make a real network call: `web3.Web3` is mocked at the module
boundary of the adapter, and ABIs/addresses are read from tiny fixture files
written to a temp dir (so `npx hardhat compile`/deploy need not have run).
"""
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from contexts.blockchain.adapters.services.web3_blockchain_service import (
    BlockchainConfigError,
    Web3BlockchainService,
)

WEB3_PATH = "contexts.blockchain.adapters.services.web3_blockchain_service.Web3"

ROOT = "0x" + "11" * 32
LEAF = "0x" + "22" * 32
PROOF = ["0x" + "33" * 32, "0x" + "44" * 32]
TRANSFER_ID = "0x" + "55" * 32


def _write_fixtures(base: Path) -> tuple[Path, Path]:
    """Create a fixture artifacts dir + deployed_addresses.json under `base`."""
    artifacts = base / "artifacts"
    for name in ("AuditTrail", "Escrow"):
        d = artifacts / "contracts" / f"{name}.sol"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.json").write_text(json.dumps({"abi": []}), encoding="utf-8")

    addresses = base / "deployed_addresses.json"
    addresses.write_text(
        json.dumps(
            {
                "network": "amoy",
                "chainId": 80002,
                "contracts": {
                    "AuditTrail": "0x0000000000000000000000000000000000000A11",
                    "Escrow": "0x0000000000000000000000000000000000000E5c",
                },
            }
        ),
        encoding="utf-8",
    )
    return artifacts, addresses


def _make_web3_mock():
    """A MagicMock standing in for the `Web3` class, wired for a full tx round-trip."""
    web3_cls = mock.MagicMock(name="Web3")
    w3 = web3_cls.return_value
    w3.eth.account.from_key.return_value.address = "0xSender"
    w3.eth.get_transaction_count.return_value = 7
    signed = mock.MagicMock()
    signed.raw_transaction = b"\xde\xad"
    w3.eth.account.sign_transaction.return_value = signed
    tx_hash = mock.MagicMock()
    tx_hash.hex.return_value = "0xabc123"
    w3.eth.send_raw_transaction.return_value = tx_hash
    return web3_cls, w3


class Web3BlockchainServiceTests(SimpleTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.artifacts, self.addresses = _write_fixtures(base)

    def _service(self):
        return Web3BlockchainService(
            artifacts_dir=self.artifacts,
            addresses_path=self.addresses,
            rpc_url="http://localhost:8545",
            private_key="0x" + "01" * 32,
            chain_id=80002,
        )

    # --------------------------------------------------------- happy paths
    def test_submit_audit_batch_calls_contract_and_returns_hash(self):
        web3_cls, w3 = _make_web3_mock()
        contract = w3.eth.contract.return_value
        with mock.patch(WEB3_PATH, web3_cls):
            svc = self._service()
            tx = svc.submit_audit_batch(1, ROOT, 4, 1000, 2000)

        self.assertEqual(tx, "0xabc123")
        contract.functions.submitBatch.assert_called_once_with(
            1, web3_cls.to_bytes.return_value, 4, 1000, 2000
        )
        # AuditTrail address (not Escrow) was used for the contract binding.
        _, kwargs = w3.eth.contract.call_args
        self.assertEqual(kwargs["abi"], [])
        web3_cls.to_bytes.assert_any_call(hexstr=ROOT)

    def test_verify_inclusion_uses_call_and_returns_bool(self):
        web3_cls, w3 = _make_web3_mock()
        contract = w3.eth.contract.return_value
        contract.functions.verifyInclusion.return_value.call.return_value = True
        with mock.patch(WEB3_PATH, web3_cls):
            svc = self._service()
            result = svc.verify_inclusion(1, LEAF, PROOF)

        self.assertIs(result, True)
        contract.functions.verifyInclusion.assert_called_once()
        args, _ = contract.functions.verifyInclusion.call_args
        self.assertEqual(args[0], 1)
        self.assertEqual(len(args[2]), len(PROOF))  # proof converted element-wise

    def test_escrow_lock_release_refund_call_right_functions(self):
        web3_cls, w3 = _make_web3_mock()
        contract = w3.eth.contract.return_value
        with mock.patch(WEB3_PATH, web3_cls):
            svc = self._service()
            self.assertEqual(svc.escrow_lock(TRANSFER_ID, 12345), "0xabc123")
            self.assertEqual(svc.escrow_release(TRANSFER_ID), "0xabc123")
            self.assertEqual(svc.escrow_refund(TRANSFER_ID), "0xabc123")

        contract.functions.lock.assert_called_once_with(
            web3_cls.to_bytes.return_value, 12345
        )
        contract.functions.release.assert_called_once()
        contract.functions.refund.assert_called_once()
        # Three state-changing calls => three signed raw transactions sent.
        self.assertEqual(w3.eth.send_raw_transaction.call_count, 3)

    def test_send_signs_with_chain_id_and_nonce(self):
        web3_cls, w3 = _make_web3_mock()
        with mock.patch(WEB3_PATH, web3_cls):
            svc = self._service()
            svc.escrow_lock(TRANSFER_ID, 100)

        fn = w3.eth.contract.return_value.functions.lock.return_value
        _, tx_kwargs = fn.build_transaction.call_args
        built = fn.build_transaction.call_args[0][0]
        self.assertEqual(built["chainId"], 80002)
        self.assertEqual(built["nonce"], 7)
        self.assertEqual(built["from"], "0xSender")

    # --------------------------------------------------------- error paths
    def test_missing_addresses_file_raises_on_call_not_construction(self):
        # Construction must not raise even with a bogus addresses path.
        svc = Web3BlockchainService(
            artifacts_dir=self.artifacts,
            addresses_path=Path(self._tmp.name) / "does_not_exist.json",
            rpc_url="http://localhost:8545",
            private_key="0x" + "01" * 32,
            chain_id=80002,
        )
        with self.assertRaises(BlockchainConfigError):
            svc.escrow_release(TRANSFER_ID)

    def test_missing_abi_artifact_raises(self):
        svc = Web3BlockchainService(
            artifacts_dir=Path(self._tmp.name) / "no_artifacts",
            addresses_path=self.addresses,
            rpc_url="http://localhost:8545",
            private_key="0x" + "01" * 32,
            chain_id=80002,
        )
        with self.assertRaises(BlockchainConfigError):
            svc.submit_audit_batch(1, ROOT, 1, 0, 0)

    def test_missing_rpc_url_raises_on_call(self):
        web3_cls, _ = _make_web3_mock()
        svc = Web3BlockchainService(
            artifacts_dir=self.artifacts,
            addresses_path=self.addresses,
            rpc_url="",
            private_key="0x" + "01" * 32,
            chain_id=80002,
        )
        with mock.patch(WEB3_PATH, web3_cls):
            with self.assertRaises(BlockchainConfigError):
                svc.escrow_lock(TRANSFER_ID, 1)
