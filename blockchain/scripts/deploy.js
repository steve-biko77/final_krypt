// Deploys AuditTrail + Escrow to whatever network Hardhat is pointed at.
// Credentials/RPC for a real network come from env vars (AMOY_RPC_URL /
// PRIVATE_KEY) via hardhat.config.js — never hardcoded here.
//
//   Local smoke test : npx hardhat run scripts/deploy.js
//   Polygon Amoy     : npx hardhat run scripts/deploy.js --network amoy
//
// The deployed addresses are written to blockchain/deployed_addresses.json so
// the Django backend adapter (Web3BlockchainService) can load them.
const fs = require("fs");
const path = require("path");
const hre = require("hardhat");

async function main() {
  const { ethers, network } = hre;

  const [deployer] = await ethers.getSigners();
  console.log(`Network      : ${network.name} (chainId ${network.config.chainId})`);
  console.log(`Deployer     : ${deployer.address}`);

  const AuditTrail = await ethers.getContractFactory("AuditTrail");
  const auditTrail = await AuditTrail.deploy();
  await auditTrail.waitForDeployment();
  const auditTrailAddress = await auditTrail.getAddress();
  console.log(`AuditTrail   : ${auditTrailAddress}`);

  const Escrow = await ethers.getContractFactory("Escrow");
  const escrow = await Escrow.deploy();
  await escrow.waitForDeployment();
  const escrowAddress = await escrow.getAddress();
  console.log(`Escrow       : ${escrowAddress}`);

  const output = {
    network: network.name,
    chainId: network.config.chainId,
    deployedAt: new Date().toISOString(),
    contracts: {
      AuditTrail: auditTrailAddress,
      Escrow: escrowAddress,
    },
  };

  const outPath = path.join(__dirname, "..", "deployed_addresses.json");
  fs.writeFileSync(outPath, JSON.stringify(output, null, 2) + "\n");
  console.log(`Addresses written to ${outPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
