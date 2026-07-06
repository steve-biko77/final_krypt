// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title Escrow
/// @notice State-tracking contract for KRYPT transfers (Phase 1/2).
/// @dev IMPORTANT: this is NOT a value vault. No function is `payable` and no
///      ETH/token ever moves. It mirrors the real off-chain custody state
///      (Stripe / Mobile Money) on-chain purely for real-time traceability.
///      Amounts are stored in EUR cents (uint256) to avoid floating point.
contract Escrow is Ownable {
    enum Status {
        NONE,
        LOCKED,
        RELEASED,
        REFUNDED
    }

    /// @notice transferId => current lifecycle status.
    mapping(bytes32 => Status) public transferStatus;

    /// @notice transferId => locked amount in EUR cents.
    mapping(bytes32 => uint256) public transferAmountCents;

    event Locked(bytes32 transferId, uint256 amountCents, uint256 timestamp);
    event Released(bytes32 transferId, uint256 timestamp);
    event Refunded(bytes32 transferId, uint256 timestamp);

    error TransferAlreadyExists(bytes32 transferId);
    error TransferNotLocked(bytes32 transferId);

    /// @dev OZ v5 Ownable requires an explicit initial owner.
    constructor() Ownable(msg.sender) {}

    /// @notice Record that a transfer has been locked (funds held off-chain).
    function lock(bytes32 transferId, uint256 amountCents) external onlyOwner {
        if (transferStatus[transferId] != Status.NONE) {
            revert TransferAlreadyExists(transferId);
        }
        transferStatus[transferId] = Status.LOCKED;
        transferAmountCents[transferId] = amountCents;
        emit Locked(transferId, amountCents, block.timestamp);
    }

    /// @notice Record that a locked transfer has been released to the beneficiary.
    function release(bytes32 transferId) external onlyOwner {
        if (transferStatus[transferId] != Status.LOCKED) {
            revert TransferNotLocked(transferId);
        }
        transferStatus[transferId] = Status.RELEASED;
        emit Released(transferId, block.timestamp);
    }

    /// @notice Record that a locked transfer has been refunded to the sender.
    function refund(bytes32 transferId) external onlyOwner {
        if (transferStatus[transferId] != Status.LOCKED) {
            revert TransferNotLocked(transferId);
        }
        transferStatus[transferId] = Status.REFUNDED;
        emit Refunded(transferId, block.timestamp);
    }
}
