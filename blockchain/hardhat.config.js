require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

const { AMOY_RPC_URL, PRIVATE_KEY, ETHERSCAN_API_KEY } = process.env;

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: { enabled: true, runs: 200 },
    },
  },
  networks: {
    // Polygon Amoy testnet. Credentials come exclusively from env vars — never
    // hardcoded. Local test runs have no PRIVATE_KEY, so guard the accounts
    // array so loading this config never breaks `npx hardhat test`.
    amoy: {
      url: AMOY_RPC_URL || "",
      chainId: 80002,
      accounts: PRIVATE_KEY ? [PRIVATE_KEY] : [],
    },
  },
  // Unified Etherscan V2: a single API key covers every supported chain
  // (including Amoy natively) — no per-network object, no customChains.
  etherscan: {
    apiKey: ETHERSCAN_API_KEY || "",
  },
};
