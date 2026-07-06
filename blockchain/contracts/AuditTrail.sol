// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {MerkleProof} from "@openzeppelin/contracts/utils/cryptography/MerkleProof.sol";

/// @title AuditTrail
/// @notice On-chain transparency/audit layer for KRYPT (Phase 1/2).
///         Stores Merkle roots of periodically-batched off-chain transfer events
///         (KRYP-25 wires the periodic submission) plus real-time critical events.
///         This contract holds NO value — it is a traceability ledger only.
contract AuditTrail is Ownable {
    /// @notice batchId => Merkle root of the batch's leaves.
    mapping(uint256 => bytes32) public batchRoots;

    /// @notice batchId => number of transactions committed in the batch.
    mapping(uint256 => uint256) public batchTxCount;

    /// @notice Emitted when a batch of off-chain events is committed on-chain.
    event BatchCommitted(
        uint256 indexed batchId,
        bytes32 merkleRoot,
        uint256 txCount,
        uint256 periodStart,
        uint256 periodEnd,
        uint256 committedAt
    );

    /// @notice Emitted for an unbatched, real-time critical event
    ///         (e.g. an AML HARD_BLOCK) that must be traceable immediately.
    event CriticalEventLogged(bytes32 transferId, string eventType, uint256 timestamp);

    /// @dev Reverts when trying to submit a batchId that already exists.
    error BatchAlreadyExists(uint256 batchId);

    /// @dev OZ v5 Ownable requires an explicit initial owner.
    constructor() Ownable(msg.sender) {}

    /// @notice Commit a batch's Merkle root on-chain.
    /// @dev Re-submission of an existing batchId reverts: a committed root is
    ///      immutable audit evidence and must never be silently overwritten.
    function submitBatch(
        uint256 batchId,
        bytes32 merkleRoot,
        uint256 txCount,
        uint256 periodStart,
        uint256 periodEnd
    ) external onlyOwner {
        if (batchRoots[batchId] != bytes32(0)) {
            revert BatchAlreadyExists(batchId);
        }
        batchRoots[batchId] = merkleRoot;
        batchTxCount[batchId] = txCount;
        emit BatchCommitted(batchId, merkleRoot, txCount, periodStart, periodEnd, block.timestamp);
    }

    /// @notice Verify that `leaf` is included in the committed batch `batchId`.
    /// @return True if `proof` proves `leaf` is under `batchRoots[batchId]`.
    function verifyInclusion(
        uint256 batchId,
        bytes32 leaf,
        bytes32[] calldata proof
    ) external view returns (bool) {
        return MerkleProof.verify(proof, batchRoots[batchId], leaf);
    }

    /// @notice Emit a real-time critical audit event (unbatched).
    function logCriticalEvent(bytes32 transferId, string calldata eventType) external onlyOwner {
        emit CriticalEventLogged(transferId, eventType, block.timestamp);
    }
}
