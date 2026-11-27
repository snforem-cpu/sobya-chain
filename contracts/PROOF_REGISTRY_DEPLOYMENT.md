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

## Deploy with the official mobile MetaMask deployer

After GitHub Pages has completed its build, open:

`https://snforem-cpu.github.io/sobya-chain/proof-suite/deploy/`

1. Press **Connect MetaMask** and approve the wallet connection.
2. Confirm the page reports SOBYA Mainnet, chain ID `357812033857`, and a valid artifact checksum.
3. Review the service wallet shown on the page: `0xd316993423Fc6268038F4EE3EA7C0C5038513C18`.
4. Press **Deploy Proof Registry**. MetaMask will show the contract-creation transaction and its gas fee.
5. Verify the network and approve only if the transaction is a contract deployment from your own wallet.
6. Wait for confirmation. The page verifies deployed bytecode and reads back the immutable fee recipient.
7. Send the resulting contract address and transaction hash for the website integration step.

The page uses MetaMask Connect and a reproducible Foundry artifact; it never asks for a private key or recovery phrase. If GitHub Pages has not yet published the artifact, wait for the Pages workflow to finish before opening the deployer.

## Important release gate

Deploying this contract does not by itself complete the website migration. The browser app and verifier must be updated to call `recordProof(bytes32)` and validate the `ProofRecorded` event from this exact contract address. Do not direct users to pay through the old EOA data-transaction flow. Configure the website only after the contract address has been independently checked on SOBYA Mainnet.
