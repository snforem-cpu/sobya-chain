# Ethereum source deposit observer

Read-only source-chain adapter for the Ethereum escrow prototype. It validates
an ERC-20 deposit by checking the configured escrow's OrderFunded event and
reading the escrow's on-chain order/status/token state at Ethereum's finalized
block tag.

The observer checks chain ID, transaction/receipt identity, escrow destination,
user transaction sender, zero native value, canonical receipt block, finalized
block height, configured USDT token, FUNDED status, every field returned by the
public orders(orderId) getter, and exactly one matching OrderFunded event.

This is an observer prototype, not a signer or a deployed service. It does not
verify SOBYA destination payouts, hold keys, submit claims/refunds, or replace
independent RPC providers. The Ethereum finalized tag is fail-closed: an RPC
provider that does not support it cannot be used by this adapter.

Run from this directory after installing requirements:

    python -m unittest -v
