import json
from pathlib import Path

from django.conf import settings
from web3 import Web3

from ...ports.blockchain_service import BlockchainServicePort


class BlockchainConfigError(RuntimeError):
    """Raised when on-chain config (addresses / ABI / RPC / key) is missing.

    Raised lazily, only when a method is actually called — never at import or
    construction time — so Django can start and unrelated tests can run without
    a deployed contract set or live RPC.
    """


def _default_blockchain_dir() -> Path:
    """Repo-root ``blockchain/`` dir (Hardhat project).

    Django ``settings.BASE_DIR`` is ``backend/``, so its parent is the repo root.
    """
    return Path(settings.BASE_DIR).parent / "blockchain"


class Web3BlockchainService(BlockchainServicePort):
    """web3.py implementation of the on-chain audit/escrow port.

    ABIs are loaded from Hardhat's standard artifact output; deployed addresses
    from ``blockchain/deployed_addresses.json``. All of this is resolved lazily
    on first use so the adapter can be constructed (and Django can boot) even
    when nothing is compiled/deployed yet.

    ``artifacts_dir`` and ``addresses_path`` are injectable so tests can point
    at small fixtures instead of requiring ``npx hardhat compile``/deploy.
    """

    def __init__(
        self,
        artifacts_dir: Path | None = None,
        addresses_path: Path | None = None,
        rpc_url: str | None = None,
        private_key: str | None = None,
        chain_id: int | None = None,
    ):
        blockchain_dir = _default_blockchain_dir()
        self._artifacts_dir = Path(artifacts_dir) if artifacts_dir else blockchain_dir / "artifacts"
        self._addresses_path = (
            Path(addresses_path) if addresses_path else blockchain_dir / "deployed_addresses.json"
        )
        self._rpc_url = rpc_url if rpc_url is not None else settings.BLOCKCHAIN_RPC_URL
        self._private_key = (
            private_key if private_key is not None else settings.BLOCKCHAIN_PRIVATE_KEY
        )
        self._chain_id = chain_id if chain_id is not None else settings.BLOCKCHAIN_CHAIN_ID

        # Lazily-built singletons.
        self._w3: Web3 | None = None
        self._account = None
        self._contracts: dict = {}

    # ------------------------------------------------------------------ setup
    def _load_abi(self, contract_name: str) -> list:
        abi_path = (
            self._artifacts_dir
            / "contracts"
            / f"{contract_name}.sol"
            / f"{contract_name}.json"
        )
        if not abi_path.exists():
            raise BlockchainConfigError(
                f"ABI artifact not found for {contract_name} at {abi_path}. "
                "Run `npx hardhat compile` in the blockchain/ project first."
            )
        with open(abi_path, encoding="utf-8") as fh:
            return json.load(fh)["abi"]

    def _load_addresses(self) -> dict:
        if not self._addresses_path.exists():
            raise BlockchainConfigError(
                f"Deployed addresses file not found at {self._addresses_path}. "
                "Deploy the contracts (scripts/deploy.js) before calling the chain."
            )
        with open(self._addresses_path, encoding="utf-8") as fh:
            return json.load(fh)["contracts"]

    def _web3(self) -> Web3:
        if self._w3 is None:
            if not self._rpc_url:
                raise BlockchainConfigError("BLOCKCHAIN_RPC_URL is not configured.")
            self._w3 = Web3(Web3.HTTPProvider(self._rpc_url))
        return self._w3

    def _signer(self):
        if self._account is None:
            if not self._private_key:
                raise BlockchainConfigError("BLOCKCHAIN_PRIVATE_KEY is not configured.")
            self._account = self._web3().eth.account.from_key(self._private_key)
        return self._account

    def _contract(self, name: str):
        if name not in self._contracts:
            address = self._load_addresses()[name]
            self._contracts[name] = self._web3().eth.contract(
                address=Web3.to_checksum_address(address),
                abi=self._load_abi(name),
            )
        return self._contracts[name]

    # -------------------------------------------------------------- tx helper
    def _send(self, fn) -> str:
        """Build, sign and send a state-changing contract call; return tx hash."""
        w3 = self._web3()
        account = self._signer()
        tx = fn.build_transaction(
            {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
                "chainId": self._chain_id,
            }
        )
        signed = w3.eth.account.sign_transaction(tx, self._private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    # ------------------------------------------------------------------ ports
    def submit_audit_batch(
        self,
        batch_id: int,
        merkle_root: str,
        tx_count: int,
        period_start: int,
        period_end: int,
    ) -> str:
        contract = self._contract("AuditTrail")
        fn = contract.functions.submitBatch(
            batch_id,
            Web3.to_bytes(hexstr=merkle_root),
            tx_count,
            period_start,
            period_end,
        )
        return self._send(fn)

    def verify_inclusion(self, batch_id: int, leaf: str, proof: list[str]) -> bool:
        contract = self._contract("AuditTrail")
        return contract.functions.verifyInclusion(
            batch_id,
            Web3.to_bytes(hexstr=leaf),
            [Web3.to_bytes(hexstr=p) for p in proof],
        ).call()

    def escrow_lock(self, transfer_id: str, amount_cents: int) -> str:
        contract = self._contract("Escrow")
        fn = contract.functions.lock(Web3.to_bytes(hexstr=transfer_id), amount_cents)
        return self._send(fn)

    def escrow_release(self, transfer_id: str) -> str:
        contract = self._contract("Escrow")
        fn = contract.functions.release(Web3.to_bytes(hexstr=transfer_id))
        return self._send(fn)

    def escrow_refund(self, transfer_id: str) -> str:
        contract = self._contract("Escrow")
        fn = contract.functions.refund(Web3.to_bytes(hexstr=transfer_id))
        return self._send(fn)
