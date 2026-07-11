"""KRYP-24 — Tests for the blockchain audit/escrow adapter.

These tests NEVER make a real network call: `web3.Web3` is mocked at the module
boundary of the adapter, and ABIs/addresses are read from tiny fixture files
written to a temp dir (so `npx hardhat compile`/deploy need not have run).
"""
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase
from web3 import Web3

from contexts.blockchain.adapters.services.web3_blockchain_service import (
    BlockchainConfigError,
    Web3BlockchainService,
)
from contexts.blockchain.domain.merkle import MerkleTree, verify_proof

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

    def test_log_critical_event_calls_audittrail_and_returns_hash(self):
        web3_cls, w3 = _make_web3_mock()
        contract = w3.eth.contract.return_value
        with mock.patch(WEB3_PATH, web3_cls):
            svc = self._service()
            tx = svc.log_critical_event(TRANSFER_ID, "ESCROW_LOCK_FAILED")

        self.assertEqual(tx, "0xabc123")
        contract.functions.logCriticalEvent.assert_called_once_with(
            web3_cls.to_bytes.return_value, "ESCROW_LOCK_FAILED"
        )
        web3_cls.to_bytes.assert_any_call(hexstr=TRANSFER_ID)

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
        # KRYP-37 — "pending", jamais le défaut "latest" (une transaction tout
        # juste envoyée n'est pas encore minée, donc "latest" réutiliserait le
        # même nonce -> "nonce too low" sur des envois rapprochés).
        w3.eth.get_transaction_count.assert_called_once_with("0xSender", "pending")

    def test_send_holds_nonce_lock_during_critical_section(self):
        """KRYP-37 — le verrou applicatif est bien tenu pendant lecture-nonce +
        envoi, et relâché ensuite (pas de deadlock, pas de faux positif)."""
        from contexts.blockchain.adapters.services import web3_blockchain_service as mod

        web3_cls, w3 = _make_web3_mock()

        def _get_transaction_count(*args, **kwargs):
            self.assertTrue(mod._nonce_lock.locked())
            return 7
        w3.eth.get_transaction_count.side_effect = _get_transaction_count

        with mock.patch(WEB3_PATH, web3_cls):
            svc = self._service()
            svc.escrow_lock(TRANSFER_ID, 100)

        self.assertFalse(mod._nonce_lock.locked())

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


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-25 — Arbre de Merkle (sorted-pair keccak256, compatible OZ MerkleProof)
# ─────────────────────────────────────────────────────────────────────────────

def _leaf(value: str) -> str:
    """A pre-hashed leaf, exactly as the task stores it on PendingAuditHash."""
    return Web3.keccak(text=value).hex()


class MerkleTreeTests(SimpleTestCase):
    """Pure-Python tests — no DB, no network. Confirms a (leaf, proof, root)
    triple validates via an independent OZ-equivalent verification walk, so the
    same triple would validate against the deployed AuditTrail.verifyInclusion."""

    def test_valid_proof_verifies_against_root(self):
        values = ["tx-a", "tx-b", "tx-c", "tx-d", "tx-e"]  # odd-node level exercised
        leaves = [_leaf(v) for v in values]
        tree = MerkleTree(leaves)
        root = tree.root

        for leaf in leaves:
            proof = tree.proof(leaf)
            self.assertTrue(
                verify_proof(leaf, proof, root),
                msg=f"leaf {leaf} should verify against root",
            )

    def test_wrong_leaf_fails_to_verify(self):
        leaves = [_leaf(v) for v in ("tx-a", "tx-b", "tx-c", "tx-d")]
        tree = MerkleTree(leaves)
        proof = tree.proof(leaves[0])
        # Proof for leaf[0] must not validate a different leaf.
        self.assertFalse(verify_proof(leaves[1], proof, tree.root))
        # Nor a bogus leaf never in the tree.
        self.assertFalse(verify_proof(_leaf("not-in-tree"), proof, tree.root))

    def test_single_leaf_tree_root_is_the_leaf(self):
        leaf = _leaf("solo")
        tree = MerkleTree([leaf])
        self.assertEqual(tree.root, Web3.to_bytes(hexstr=leaf))
        self.assertTrue(verify_proof(leaf, [], tree.root))

    def test_root_hex_is_stable_and_prefixed(self):
        leaves = [_leaf(v) for v in ("a", "b", "c")]
        self.assertEqual(MerkleTree(leaves).root_hex(), MerkleTree(leaves).root_hex())
        self.assertTrue(MerkleTree(leaves).root_hex().startswith("0x"))


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-37 — Dérivation déterministe du transferId on-chain (fix bug UUID brut)
# ─────────────────────────────────────────────────────────────────────────────

class TransferIdDerivationTests(SimpleTestCase):
    """Pure-Python — no DB, no network."""

    def test_deterministic_same_transaction_id_same_hash(self):
        from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
        transaction_id = "550e8400-e29b-41d4-a716-446655440000"

        first = to_onchain_transfer_id(transaction_id)
        second = to_onchain_transfer_id(transaction_id)
        third = to_onchain_transfer_id(transaction_id)

        self.assertEqual(first, second)
        self.assertEqual(second, third)

    def test_valid_bytes32_hex_format(self):
        from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
        result = to_onchain_transfer_id("550e8400-e29b-41d4-a716-446655440000")

        self.assertTrue(result.startswith("0x"))
        self.assertEqual(len(result), 66)  # "0x" + 64 hex chars = 32 bytes
        # bytes32 valide pour Web3.to_bytes(hexstr=...) — c'est exactement ce que
        # le contrat Escrow/AuditTrail attend (cf. docstring du port).
        Web3.to_bytes(hexstr=result)  # ne doit pas lever

    def test_different_transaction_ids_produce_different_hashes(self):
        from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
        a = to_onchain_transfer_id("550e8400-e29b-41d4-a716-446655440000")
        b = to_onchain_transfer_id("11111111-1111-1111-1111-111111111111")

        self.assertNotEqual(a, b)

    def test_raw_uuid_would_have_failed_hex_conversion(self):
        """Confirme le bug d'origine (KRYP-37) : un UUID brut n'est PAS un hexstr
        valide — c'est précisément pourquoi cette fonction existe."""
        raw_uuid = "550e8400-e29b-41d4-a716-446655440000"
        with self.assertRaises(ValueError):
            Web3.to_bytes(hexstr=raw_uuid)


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-25 — Tâche de soumission du batch d'audit (Merkle → AuditTrail)
# ─────────────────────────────────────────────────────────────────────────────

class SubmitAuditBatchTaskTests(TestCase):

    def _pending(self, transaction_id: str, event_type: str = "", leaf: str = None):
        from contexts.blockchain.models import PendingAuditHash
        return PendingAuditHash.objects.create(
            transaction_id=transaction_id,
            event_type=event_type,
            leaf_hash=leaf or _leaf(transaction_id),
        )

    @mock.patch("contexts.blockchain.adapters.services.web3_blockchain_service.Web3BlockchainService")
    def test_merkle_batch_submission_groups_pending_hashes(self, mock_service_cls):
        from contexts.blockchain.models import PendingAuditHash
        from contexts.blockchain.tasks import submit_audit_batch_task

        ids = ["tx-1", "tx-2", "tx-3", "tx-4"]
        for i in ids:
            self._pending(i)
        mock_service_cls.return_value.submit_audit_batch.return_value = "0xbatch"

        result = submit_audit_batch_task()

        # submit_audit_batch appelé exactement une fois.
        mock_service_cls.return_value.submit_audit_batch.assert_called_once()
        args = mock_service_cls.return_value.submit_audit_batch.call_args[0]
        batch_id, submitted_root, tx_count = args[0], args[1], args[2]
        self.assertEqual(tx_count, 4)

        # La racine soumise correspond à celle recalculée indépendamment.
        expected_root = MerkleTree([_leaf(i) for i in ids]).root_hex()
        self.assertEqual(submitted_root, expected_root)
        self.assertEqual(result["merkle_root"], expected_root)

        # Toutes les lignes sont maintenant batched avec le même batch_id.
        rows = PendingAuditHash.objects.filter(transaction_id__in=ids)
        self.assertTrue(all(r.batched for r in rows))
        self.assertEqual({r.batch_id for r in rows}, {batch_id})

    @mock.patch("contexts.blockchain.adapters.services.web3_blockchain_service.Web3BlockchainService")
    def test_batch_tx_hash_and_merkle_proof_persisted(self, mock_service_cls):
        """KRYP-27 — après soumission, chaque ligne porte le batch_tx_hash du lot
        et sa propre preuve de Merkle (liste de chaînes hex, différente par ligne)."""
        from contexts.blockchain.domain.merkle import verify_proof
        from contexts.blockchain.models import PendingAuditHash
        from contexts.blockchain.tasks import submit_audit_batch_task

        ids = ["tx-1", "tx-2", "tx-3"]
        for i in ids:
            self._pending(i)
        mock_service_cls.return_value.submit_audit_batch.return_value = "0xbatchtx"

        result = submit_audit_batch_task()

        expected_root = MerkleTree([_leaf(i) for i in ids]).root_hex()
        rows = list(PendingAuditHash.objects.filter(transaction_id__in=ids))
        for row in rows:
            self.assertEqual(row.batch_tx_hash, "0xbatchtx")
            # Preuve : liste de chaînes hex "0x…" qui vérifie contre la racine.
            self.assertIsInstance(row.merkle_proof, list)
            for node in row.merkle_proof:
                self.assertTrue(node.startswith("0x"))
            self.assertTrue(
                verify_proof(row.leaf_hash, row.merkle_proof, expected_root),
                msg=f"la preuve de {row.transaction_id} doit vérifier contre la racine",
            )
        self.assertEqual(result["tx_hash"], "0xbatchtx")

    @mock.patch("contexts.blockchain.adapters.services.web3_blockchain_service.Web3BlockchainService")
    def test_event_type_disambiguates_escrow_vs_delivered_rows(self, mock_service_cls):
        """KRYP-27 — un transfert a DEUX lignes (ESCROWED + DELIVERED) partageant
        le même transaction_id ; le filtre event_type='DELIVERED' isole la bonne.

        Les deux lignes peuvent atterrir dans des lots distincts : on soumet un
        premier lot (ESCROWED seul), puis un second (DELIVERED seul), et on
        vérifie que le batch récupéré par event_type est bien celui de livraison.
        """
        from datetime import timedelta

        from django.utils import timezone

        from contexts.blockchain.models import PendingAuditHash
        from contexts.blockchain.tasks import submit_audit_batch_task

        txid = "tx-shared"
        # 1er lot : uniquement la feuille ESCROWED.
        self._pending(txid, event_type=PendingAuditHash.EVENT_ESCROWED, leaf=_leaf(f"{txid}:E"))
        mock_service_cls.return_value.submit_audit_batch.return_value = "0xescrowbatch"
        r1 = submit_audit_batch_task()

        # 2e lot : uniquement la feuille DELIVERED (créée après le 1er lot).
        # KRYP-37 — batch_id dérive désormais de periodStart (created_at) :
        # created_at avancé d'un cycle Beat réaliste (15 min) pour obtenir un
        # periodStart distinct, comme deux lots réellement soumis à 15 min
        # d'écart (un appel immédiat dans le même test tomberait sinon dans la
        # même seconde que le 1er lot).
        delivered_row = self._pending(
            txid, event_type=PendingAuditHash.EVENT_DELIVERED, leaf=_leaf(f"{txid}:D")
        )
        PendingAuditHash.objects.filter(pk=delivered_row.pk).update(
            created_at=timezone.now() + timedelta(minutes=15)
        )
        mock_service_cls.return_value.submit_audit_batch.return_value = "0xdeliveredbatch"
        r2 = submit_audit_batch_task()

        self.assertNotEqual(r1["batch_id"], r2["batch_id"])

        delivered = PendingAuditHash.objects.filter(
            transaction_id=txid,
            event_type=PendingAuditHash.EVENT_DELIVERED,
            batched=True,
        ).first()
        escrowed = PendingAuditHash.objects.filter(
            transaction_id=txid,
            event_type=PendingAuditHash.EVENT_ESCROWED,
            batched=True,
        ).first()

        # Chaque ligne pointe vers SON lot — pas de confusion.
        self.assertEqual(delivered.batch_tx_hash, "0xdeliveredbatch")
        self.assertEqual(delivered.batch_id, r2["batch_id"])
        self.assertEqual(escrowed.batch_tx_hash, "0xescrowbatch")
        self.assertEqual(escrowed.batch_id, r1["batch_id"])

    @mock.patch("contexts.blockchain.adapters.services.web3_blockchain_service.Web3BlockchainService")
    def test_merkle_batch_skipped_when_empty(self, mock_service_cls):
        from contexts.blockchain.tasks import submit_audit_batch_task

        result = submit_audit_batch_task()

        self.assertFalse(result["submitted"])
        mock_service_cls.return_value.submit_audit_batch.assert_not_called()

    @mock.patch("contexts.blockchain.adapters.services.web3_blockchain_service.Web3BlockchainService")
    def test_already_batched_rows_are_ignored(self, mock_service_cls):
        from contexts.blockchain.tasks import submit_audit_batch_task

        already = self._pending("tx-old")
        already.batched = True
        already.batch_id = 1
        already.save()
        self._pending("tx-new")
        mock_service_cls.return_value.submit_audit_batch.return_value = "0xb2"

        result = submit_audit_batch_task()

        self.assertTrue(result["submitted"])
        self.assertEqual(result["count"], 1)  # seule la ligne non batchée
        # KRYP-37 — batch_id = periodStart (timestamp Unix), plus un compteur
        # local : indépendant du batch_id=1 déjà pris par la ligne batchée.
        self.assertNotEqual(result["batch_id"], 1)
        self.assertGreater(result["batch_id"], 1_000_000_000)  # ordre de grandeur Unix
