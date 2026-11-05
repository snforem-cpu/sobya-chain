# SOBYA blockchain (development)

SOBYA is an in-development Cosmos SDK application using CometBFT, with a partially integrated Cosmos EVM execution environment. It is not a launched public network.

## Native token

- Display: `SOBY`
- Base denomination: `asobya`
- Precision: 18 decimals (`1 SOBY = 10^18 asobya`)
- Intended maximum native supply: `1,000,000,000 SOBY`
- Automatic mint inflation is disabled by current genesis normalization.

The genesis guard checks the initial native allocation against the cap. Runtime issuance invariants and the validator reserve release mechanism still require complete end-to-end verification before launch. See [TOKENOMICS.md](TOKENOMICS.md).

## EVM and fee routing

The development branch includes Cosmos EVM modules and EVM-aware transaction handling. CI workflows exercise EVM JSON-RPC, signed EVM transactions, contract deployment/calls, and actual Cosmos/EVM transaction-fee routing. The current EVM chain ID `777777` is for development and CI only.

The fee router currently sends the combined treasury/community portion (70%) to the configured shared management wallet and leaves 30% for the Cosmos distribution module. Because treasury and community use the same wallet, their internal accounting remains separate off-chain.

## Development

Run locally with Ignite only for disposable development environments:

```sh
ignite chain serve
```

The values in `config.yml` are development-only test allocations. They are not the agreed public launch distribution or a final genesis file.

## Safety and status

- CI/localnet success is not proof of independent public validators or production readiness.
- The public testnet chain ID, EVM chain ID, genesis ceremony, validator reserve rules, and public infrastructure are not finalized.
- Do not use real funds on this development chain.
- Never commit private validator keys, node keys, mnemonics, or wallet secrets.
