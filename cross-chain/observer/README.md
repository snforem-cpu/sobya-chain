# SOBYA destination payout observer (prototype)

This is a read-only Python observer for the PayoutExecuted event emitted by
SobyaCrossChainSettlement. It is the first off-chain verification component
for the intent-based swap flow.

## What it verifies

For each order, the caller must provide expected values from the signed
solver quote/source escrow record. The observer independently checks:

- JSON-RPC chain ID equals the configured SOBYA EVM chain ID.
- Transaction and receipt exist, succeeded, target the configured settlement
  contract, and agree on the requested transaction hash. The actual transaction
  sender and native SOBY value must match the destination solver and quote.
- The receipt block hash matches the canonical block at that height, and the
  receipt has at least the configured number of destination confirmations.
- Exactly one matching PayoutExecuted event exists from the configured
  settlement contract.
- Order ID, canonical source-chain key, source escrow, source USDT contract or
  mint, exact source amount, SOBYA recipient, exact SOBY amount, destination-chain solver address (which may differ from the source-chain solver account), and
  destination chain ID match the expected order record.
- SQLite prevents recording the same order or transaction log twice.

Canonical source-chain keys are keccak256(UTF-8 network label), for example
keccak256("ETHEREUM_MAINNET"). EVM/TVM addresses are left-padded to 32 bytes;
Solana public keys are used as their native 32-byte values.

## TRON source deposit observer (prototype)

`tron_source_observer.py` reads transaction details and block data through
TRON's Solidity Node endpoints, then checks the solidified transaction result,
target contract, sender, zero native-TRX value, canonical solidified block ID,
configured TRC-20 token, FUNDED order storage, all ten stored order fields,
and exactly one matching `OrderFunded` event. It accepts TRON's 41-prefixed
hex addresses and normalizes them to the 20-byte EVM representation used by
the escrow ABI.

This remains an RPC-based observer, not a cryptographic TRON light client.
Before production use it needs independent Solidity Node quorum, a verified
TRON-Solidity compiler/TVM deployment, and Shasta integration tests against
the actual deployed bytecode. Mocked tests do not establish TVM compatibility
or production finality guarantees.

## What it does not do

- It does not verify source-chain deposits or their finality.
- It does not sign or submit payout attestations.
- It does not operate a solver, hold private keys, or submit transactions.
- It does not replace independent RPC providers, chain-specific finality policy,
  durable order storage, monitoring, or external security review.
- A confirmation count is an operational threshold, not proof of Ethereum
  consensus finality. Production Ethereum verification must use a finalized
  block tag or a stronger independently reviewed finality policy.
- It is not deployed as a service and has no public API.

## Run tests

    python -m pip install -r cross-chain/observer/requirements.txt
    cd cross-chain/observer
    python -m unittest -v

Do not place RPC credentials or signer private keys here or commit them to Git.
The observer is deliberately read-only.
