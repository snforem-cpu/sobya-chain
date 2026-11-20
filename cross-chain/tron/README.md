# TRON USDT escrow adapter

## Implementation status

This is a TRON-named deployment wrapper around the shared escrow state machine in
`contracts/src/SobyaEthereumUsdtEscrow.sol`. It accepts a TRC-20 USDT contract
address at construction and inherits the same signed quote, exact-balance-delta,
threshold payout-attestation, replay protection, and user refund rules.

The wrapper avoids maintaining a second copy of security-critical escrow logic.
The EIP-712 domain includes `block.chainid` and `address(this)`, so signatures
are scoped to the deployed TRON escrow instance.

## Important verification boundary

The Foundry tests for this wrapper run in a local EVM test environment. They
verify inherited state-machine behavior; **they do not execute the contract in
the TRON Virtual Machine**. Before any TRON testnet deployment:

1. Pin and use a TRON-distributed Solidity compiler, not upstream `solc`.
2. Compile the exact source with the compiler version supported by the target
   TRON network. Record compiler build, optimizer settings, and bytecode hash.
3. Deploy to Shasta using TronWeb/TronBox with a test TRC-20 mock and independent
   attestor keys.
4. Verify exact TRC-20 transfer behavior, signature recovery, chain ID domain
   separation, Energy limits, and refund/claim race behavior on TVM.
5. Publish the verified source and bytecode hash; then conduct independent
   security review before considering mainnet.

The repository's current Foundry compiler is upstream Solidity 0.8.24. This is
not a substitute for a TRON-solc build. No TRON USDT address or escrow address
is configured here, and no TRON deployment has occurred.

## Trust and operational assumptions

The fixed attestor threshold is a trusted authorization set, not a light client
and not trustless proof of SOBYA finality. Attestors must independently inspect
the SOBYA payout. The attestor set is immutable; key loss or compromise requires
a new deployment and an explicit migration plan. Source USDT is released to the
solver only after the threshold attestation, while the user can refund after
the signed order's deadline if it remains funded.

TRON contract calls consume Bandwidth/Energy. Testnet and production operations
therefore still require suitable TRX/resources and monitoring.
