# TRON source escrow observer (prototype)

This read-only observer verifies a TRON source deposit for the SOBYA intent-settlement flow.

## Finality and checks

It queries only TRON SolidityNode endpoints:

- `walletsolidity/gettransactionbyid` to require the transaction body in the solidified view.
- `walletsolidity/gettransactioninfobyid` to require a solidified execution receipt with `receipt.result == SUCCESS`.

It then checks the TriggerSmartContract target and sender, decodes the escrow `fund(Order,bytes)` calldata, matches every signed order field, validates the 65-byte solver quote signature encoding, and requires exactly one matching `OrderFunded` event emitted by the configured escrow with the expected amount.

The observer normalizes TRON's 21-byte `41`-prefixed addresses to EVM-style 20-byte hex for comparisons. Event log contract addresses are checked in their 20-byte representation.

## Limitations

- This is a read-only verifier, not a relayer, signer, RPC quorum, or durable order service.
- The SolidityNode API must be independently operated or selected with a production RPC trust/quorum policy. A single endpoint can lie.
- The TRON escrow wrapper still requires TRON-solc compilation and Shasta TVM deployment/integration tests. Solidity/EVM unit tests do not prove TVM compatibility.
- The observer does not itself call the contract's storage getters. It validates the exact submitted order calldata plus the solidified escrow event/receipt. Production rollout should add independent solidified state reads and RPC quorum.
- No TRON addresses, USDT contract, or production keys are configured.
