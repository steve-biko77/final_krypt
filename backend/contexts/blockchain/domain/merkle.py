"""KRYP-25 — Sorted-pair keccak256 Merkle tree (OpenZeppelin-compatible).

Self-contained implementation used to batch off-chain transfer audit hashes into
a single on-chain Merkle root submitted to ``AuditTrail.submitBatch`` every 15
minutes (mémoire ch.1/ch.2 — batching preserves the 0.9-1% fee-competitiveness
target vs. one on-chain event per transfer).

Conventions (must match the deployed contract's ``verifyInclusion``, which uses
OZ ``MerkleProof.verify`` — sorted-pair keccak256):
  - Leaves are the already-computed keccak256 hashes stored on ``PendingAuditHash``
    rows (32-byte values, no double-hashing).
  - An internal node combines two children as ``keccak256(sorted(a, b))`` where
    the lexicographically smaller 32-byte value is concatenated first — exactly
    OZ ``_hashPair``.
  - Odd node counts: the leftover node is promoted unchanged to the next level.
    Python builds both the root and the proofs from this same structure, so
    internal self-consistency (proof verifies against root) is what matters; we
    do not need to bit-for-bit match merkletreejs (only used in the independent
    Hardhat contract tests).
"""
from typing import List

from web3 import Web3


def _to_bytes(value) -> bytes:
    if isinstance(value, bytes):
        return value
    return Web3.to_bytes(hexstr=value)


def _hash_pair(a: bytes, b: bytes) -> bytes:
    """OZ _hashPair: keccak256 of the two nodes sorted ascending."""
    lo, hi = (a, b) if a <= b else (b, a)
    return Web3.keccak(lo + hi)


class MerkleTree:
    """A sorted-pair keccak256 Merkle tree over pre-hashed leaves."""

    def __init__(self, leaves: List):
        if not leaves:
            raise ValueError("MerkleTree requires at least one leaf")
        self._leaves: List[bytes] = [_to_bytes(leaf) for leaf in leaves]
        self._levels: List[List[bytes]] = self._build_levels(self._leaves)

    @staticmethod
    def _build_levels(leaves: List[bytes]) -> List[List[bytes]]:
        levels = [list(leaves)]
        current = levels[0]
        while len(current) > 1:
            nxt: List[bytes] = []
            for i in range(0, len(current), 2):
                if i + 1 < len(current):
                    nxt.append(_hash_pair(current[i], current[i + 1]))
                else:
                    # Odd node out: promote unchanged to the next level.
                    nxt.append(current[i])
            levels.append(nxt)
            current = nxt
        return levels

    @property
    def root(self) -> bytes:
        return self._levels[-1][0]

    def root_hex(self) -> str:
        return "0x" + self.root.hex()

    def proof(self, leaf) -> List[bytes]:
        """Return the sibling path proving ``leaf`` is under the root."""
        target = _to_bytes(leaf)
        try:
            index = self._levels[0].index(target)
        except ValueError:
            raise ValueError("leaf not present in tree")

        proof: List[bytes] = []
        for level in self._levels[:-1]:
            if index % 2 == 0:
                sibling = index + 1
                if sibling < len(level):
                    proof.append(level[sibling])
                # else: promoted node, no sibling at this level.
            else:
                proof.append(level[index - 1])
            index //= 2
        return proof


def verify_proof(leaf, proof: List, root) -> bool:
    """Pure-Python re-implementation of OZ MerkleProof.verify (sorted-pair).

    Walks from ``leaf`` to a computed root using the sibling ``proof`` and
    compares to ``root``. Confidence that a (leaf, proof, root) triple built by
    :class:`MerkleTree` would also validate against the real contract.
    """
    computed = _to_bytes(leaf)
    for sibling in proof:
        computed = _hash_pair(computed, _to_bytes(sibling))
    return computed == _to_bytes(root)
