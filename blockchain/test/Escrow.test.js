const { expect } = require("chai");
const { ethers } = require("hardhat");
const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");

const Status = { NONE: 0, LOCKED: 1, RELEASED: 2, REFUNDED: 3 };

describe("Escrow", function () {
  let escrow;
  let owner;
  let other;
  let transferId;

  beforeEach(async function () {
    [owner, other] = await ethers.getSigners();
    const Escrow = await ethers.getContractFactory("Escrow");
    escrow = await Escrow.deploy();
    await escrow.waitForDeployment();
    transferId = ethers.encodeBytes32String("transfer-1");
  });

  it("lock -> release cycle updates status and emits events", async function () {
    await expect(escrow.lock(transferId, 12345n))
      .to.emit(escrow, "Locked")
      .withArgs(transferId, 12345n, anyValue);

    expect(await escrow.transferStatus(transferId)).to.equal(Status.LOCKED);
    expect(await escrow.transferAmountCents(transferId)).to.equal(12345n);

    await expect(escrow.release(transferId))
      .to.emit(escrow, "Released")
      .withArgs(transferId, anyValue);

    expect(await escrow.transferStatus(transferId)).to.equal(Status.RELEASED);
  });

  it("lock -> refund cycle updates status and emits events", async function () {
    await escrow.lock(transferId, 500n);

    await expect(escrow.refund(transferId))
      .to.emit(escrow, "Refunded")
      .withArgs(transferId, anyValue);

    expect(await escrow.transferStatus(transferId)).to.equal(Status.REFUNDED);
  });

  it("reverts on double-lock of the same transferId", async function () {
    await escrow.lock(transferId, 100n);
    await expect(
      escrow.lock(transferId, 100n)
    ).to.be.revertedWithCustomError(escrow, "TransferAlreadyExists");
  });

  it("reverts on release without a prior lock", async function () {
    await expect(
      escrow.release(transferId)
    ).to.be.revertedWithCustomError(escrow, "TransferNotLocked");
  });

  it("reverts on refund without a prior lock", async function () {
    await expect(
      escrow.refund(transferId)
    ).to.be.revertedWithCustomError(escrow, "TransferNotLocked");
  });

  it("cannot release a transfer that is already released", async function () {
    await escrow.lock(transferId, 100n);
    await escrow.release(transferId);
    await expect(
      escrow.release(transferId)
    ).to.be.revertedWithCustomError(escrow, "TransferNotLocked");
  });

  describe("access control", function () {
    it("reverts when a non-owner calls lock", async function () {
      await expect(
        escrow.connect(other).lock(transferId, 100n)
      ).to.be.revertedWithCustomError(escrow, "OwnableUnauthorizedAccount");
    });

    it("reverts when a non-owner calls release", async function () {
      await escrow.lock(transferId, 100n);
      await expect(
        escrow.connect(other).release(transferId)
      ).to.be.revertedWithCustomError(escrow, "OwnableUnauthorizedAccount");
    });

    it("reverts when a non-owner calls refund", async function () {
      await escrow.lock(transferId, 100n);
      await expect(
        escrow.connect(other).refund(transferId)
      ).to.be.revertedWithCustomError(escrow, "OwnableUnauthorizedAccount");
    });
  });
});
