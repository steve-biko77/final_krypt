from abc import ABC, abstractmethod


class BlockchainServicePort(ABC):
    """Port for the on-chain transparency/audit layer (KRYP-24).

    Phase 1/2: the blockchain holds NO real value — real custody stays off-chain
    (Stripe / Mobile Money). These calls only record audit state on-chain.

    Byte-typed identifiers convention:
      - ``transfer_id`` / ``leaf`` / ``merkle_root`` are hex strings
        (``"0x"``-prefixed, 32 bytes / 66 chars) — the natural form for
        Solidity ``bytes32`` and Web3.py. ``proof`` is a list of such hex
        strings. Amounts are integer EUR cents (never floats).
      - Every state-changing method returns the transaction hash as a hex
        ``str``.
    """

    @abstractmethod
    def submit_audit_batch(
        self,
        batch_id: int,
        merkle_root: str,
        tx_count: int,
        period_start: int,
        period_end: int,
    ) -> str:
        """Commit a batch Merkle root to AuditTrail. Returns the tx hash."""

    @abstractmethod
    def verify_inclusion(self, batch_id: int, leaf: str, proof: list[str]) -> bool:
        """Return True if ``leaf`` is proven included in batch ``batch_id``."""

    @abstractmethod
    def escrow_lock(self, transfer_id: str, amount_cents: int) -> str:
        """Record a transfer as LOCKED on Escrow. Returns the tx hash."""

    @abstractmethod
    def escrow_release(self, transfer_id: str) -> str:
        """Record a locked transfer as RELEASED on Escrow. Returns the tx hash."""

    @abstractmethod
    def escrow_refund(self, transfer_id: str) -> str:
        """Record a locked transfer as REFUNDED on Escrow. Returns the tx hash."""
