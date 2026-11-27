# SOBYA Proof Registry deployment

This is a separate fifth contract. It does not modify WSOBY, the V2 Factory, Oracle, or Router.

## Contract behavior

- EVM chain ID: `357812033857`.
- Fixed service fee: exactly `1 SOBY` (`1 ether`, 18 decimals).
- Constructor argument: the existing Proof service wallet, `0xd316993423Fc6268038F4EE3EA7C0C5038513C18`.
- `recordProof(bytes32)` accepts a 32-byte SHA-256 digest and the exact fee in one transaction.
- The contract forwards the fee to the configured service wallet and emits `ProofRecorded`.
- A digest can be registered once. Zero digests and incorrect fees are rejected.
- If forwarding the fee fails, the entire transaction (including the registry write) reverts.
- Documents and filenames are never sent to the contract.

## Tests

From the repository root, with Foundry installed:

```sh
cd contracts
forge fmt --check
forge build
forge test --match-contract SobyaProofRegistryTest -vv
```

The GitHub Actions contract workflow also compiles and runs the full Solidity regression suite.

## Deploy with MetaMask (no private key shared)

1. Open the official Remix IDE at https://remix.ethereum.org/ and create `SobyaProofRegistry.sol`.
2. Copy the exact source from `contracts/src/SobyaProofRegistry.sol` in this repository.
3. Compile with Solidity `0.8.24` (optimizer enabled, 200 runs).
4. In Deploy & Run Transactions, choose **Injected Provider - MetaMask**.
5. Confirm MetaMask is connected to **SOBYA Mainnet**, EVM chain ID `357812033857`.
6. Select `SobyaProofRegistry` and enter this constructor argument:
   `0xd316993423Fc6268038F4EE3EA7C0C5038513C18`.
7. Click Deploy and review the network gas fee in MetaMask. Confirm only if the network and constructor argument are correct.
8. Copy the deployed contract address and transaction hash. Verify the deployed bytecode and constructor configuration before configuring the website.

Never enter a seed phrase or private key into Remix or share it with anyone. MetaMask should display and sign the deployment transaction itself.

## Important release gate

Deploying this contract does not by itself complete the website migration. The browser app and verifier must be updated to call `recordProof(bytes32)` and validate the `ProofRecorded` event from this exact contract address. Do not direct users to pay through the old EOA data-transaction flow. Configure the website only after the contract address has been independently checked on SOBYA Mainnet.
