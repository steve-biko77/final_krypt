const { expect } = require("chai");
const { ethers } = require("hardhat");
const { MerkleTree } = require("merkletreejs");
const keccak256 = require("keccak256");

describe("AuditTrail", function () {
  let auditTrail;
  let owner;
  let other;

  beforeEach(async function () {
    [owner, other] = await ethers.getSigners();
    const AuditTrail = await ethers.getContractFactory("AuditTrail");
    auditTrail = await AuditTrail.deploy();
    await auditTrail.waitForDeployment();
  });

  // Build a real small Merkle tree from transfer-event leaves.
  function buildTree(values) {
    const leaves = values.map((v) => keccak256(v));
    const tree = new MerkleTree(leaves, keccak256, { sortPairs: true });
    return { tree, leaves };
  }

  describe("submitBatch", function () {
    it("stores the root + tx count and emits BatchCommitted", async function () {
      const { tree } = buildTree(["tx-a", "tx-b", "tx-c", "tx-d"]);
      const root = tree.getHexRoot();
      const batchId = 1n;
      const txCount = 4n;
      const periodStart = 1_700_000_000n;
      const periodEnd = 1_700_003_600n;

      await expect(
        auditTrail.submitBatch(batchId, root, txCount, periodStart, periodEnd)
      )
        .to.emit(auditTrail, "BatchCommitted")
        .withArgs(batchId, root, txCount, periodStart, periodEnd, anyUint());

      expect(await auditTrail.batchRoots(batchId)).to.equal(root);
      expect(await auditTrail.batchTxCount(batchId)).to.equal(txCount);
    });

    it("reverts when submitting an already-existing batchId", async function () {
      const { tree } = buildTree(["tx-a", "tx-b"]);
      const root = tree.getHexRoot();
      await auditTrail.submitBatch(1n, root, 2n, 0n, 0n);

      await expect(
        auditTrail.submitBatch(1n, root, 2n, 0n, 0n)
      ).to.be.revertedWithCustomError(auditTrail, "BatchAlreadyExists");
    });

    it("reverts when a non-owner submits a batch", async function () {
      const { tree } = buildTree(["tx-a", "tx-b"]);
      await expect(
        auditTrail.connect(other).submitBatch(1n, tree.getHexRoot(), 2n, 0n, 0n)
      ).to.be.revertedWithCustomError(auditTrail, "OwnableUnauthorizedAccount");
    });
  });

  describe("verifyInclusion", function () {
    it("returns true for a valid leaf + proof", async function () {
      const values = ["tx-a", "tx-b", "tx-c", "tx-d"];
      const { tree, leaves } = buildTree(values);
      await auditTrail.submitBatch(1n, tree.getHexRoot(), 4n, 0n, 0n);

      const leaf = leaves[2];
      const proof = tree.getHexProof(leaf);
      const leafHex = "0x" + leaf.toString("hex");

      expect(await auditTrail.verifyInclusion(1n, leafHex, proof)).to.equal(true);
    });

    it("returns false for a leaf that is not in the tree", async function () {
      const { tree, leaves } = buildTree(["tx-a", "tx-b", "tx-c", "tx-d"]);
      await auditTrail.submitBatch(1n, tree.getHexRoot(), 4n, 0n, 0n);

      const goodLeaf = leaves[0];
      const proof = tree.getHexProof(goodLeaf);
      const wrongLeaf = "0x" + keccak256("tx-not-in-tree").toString("hex");

      // A valid proof but for the wrong leaf must not verify.
      expect(await auditTrail.verifyInclusion(1n, wrongLeaf, proof)).to.equal(false);
    });
  });

  describe("logCriticalEvent", function () {
    it("emits CriticalEventLogged", async function () {
      const transferId = ethers.encodeBytes32String("transfer-42");
      await expect(auditTrail.logCriticalEvent(transferId, "AML_HARD_BLOCK"))
        .to.emit(auditTrail, "CriticalEventLogged")
        .withArgs(transferId, "AML_HARD_BLOCK", anyUint());
    });

    it("reverts when a non-owner logs a critical event", async function () {
      const transferId = ethers.encodeBytes32String("transfer-42");
      await expect(
        auditTrail.connect(other).logCriticalEvent(transferId, "AML_HARD_BLOCK")
      ).to.be.revertedWithCustomError(auditTrail, "OwnableUnauthorizedAccount");
    });
  });
});

// Matcher helper: accept any uint for the block.timestamp argument.
function anyUint() {
  const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");
  return anyValue;
}
