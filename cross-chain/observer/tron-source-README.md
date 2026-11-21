# TRON source escrow observer (prototype)

Read-only verifier for TRC-20 deposits into `SobyaTronUsdtEscrow`.

## Verification path

The observer uses SolidityNode endpoints only:

- `walletsolidity/gettransactioninfobyid` to obtain a solidified execution receipt and require `receipt.result == SUCCESS`.
- `walletsolidity/gettransactionbyid` to require the transaction body in the solidified chain.
- `walletsolidity/getblockbynum` to compare the solidified transaction block and verify the configured genesis block hash.
- `walletsolidity/triggerconstantcontract` to read the escrow's configured token, order status, and full stored order from the latest solidified state.

It verifies the transaction sender and escrow target, rejects native TRX value, requires exactly one matching `OrderFunded(bytes32,address,address,uint256)` event from the escrow, and compares all stored order fields (user, token, source amount, solver, destination chain/recipient/amount, quote expiry, and refund deadline) with the expected signed order.

TRON's 21-byte `41`-prefixed address format is normalized to the corresponding 20-byte ABI address for comparisons. The RPC client is HTTPS-only.

## Limitations

- This is a read-only library and mocked-RPC test suite, not an autonomous relayer, signer, durable order service, or independent RPC quorum.
- A single SolidityNode endpoint remains a trust dependency; production requires independently operated or diverse RPC sources and quorum policy.
- The TRON escrow wrapper still requires a TRON-solc build and Shasta TVM deployment/integration tests. Local Foundry EVM tests do not establish TVM compatibility.
- No TRON escrow address, USDT contract address, production RPC, or signing key is configured.
- No TRON testnet or mainnet deployment has occurred.
