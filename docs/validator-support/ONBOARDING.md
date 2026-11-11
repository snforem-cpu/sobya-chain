# SOBYA Validator Onboarding

This guide separates expressions of interest from permission to execute live-chain transactions. SOBYA mainnet is live on CometBFT chain ID `sobya-1`. External preflight checks were run from GitHub-hosted runners on 2026-11-11.

## 1. Apply (manual intake)

Submit the public [SOBYA Validator Application](https://github.com/snforem-cpu/sobya-chain/issues/new?template=validator-application.yml).

The issue is public. Provide only public operator details, public addresses, public consensus keys, and public P2P/RPC endpoints. Never submit a seed phrase, private key, validator signing key, server password, SSH key, access token, or private contact information.

There is no application fee. Applying does not guarantee admission or a support grant. The issue form is a manual GitHub workflow; it is not connected to the experimental Go support API.

## 2. Published public endpoints

NodeSafe supplied these public endpoints:

- CometBFT RPC: https://sobya-rpc.nodesafe-app.xyz
- Cosmos REST API: https://sobya-api.nodesafe-app.xyz
- EVM JSON-RPC: https://sobya-evm-rpc.nodesafe-app.xyz
- Explorer: https://explorer.nodesafe-app.xyz/sobya

External read-only preflight results on 2026-11-11:

- CometBFT RPC returned chain ID `sobya-1`, Node ID `1dad50ff897c247cba0ff646d0ee1ad59c3abc88`, and advancing block heights (12902 to 12906 over 20 seconds).
- Cosmos REST returned chain ID `sobya-1`; the staking query returned one validator record.
- EVM JSON-RPC returned production EVM chain ID `357812033857` (`0x534f425941`), a non-zero block height, and valid `eth_getBalance` responses for both owner wallet addresses. The balances matched 400,000,000 SOBY and 450,000,000 SOBY.
- External TCP to `188.68.36.11:26656` succeeded. The previously reported port `36656` timed out.
- CometBFT `/net_info` reported `listening: true` and zero connected peers at the time checked.
- Live staking parameters returned: bond denom `asobya`, `max_validators=100`, `unbonding_time=1814400s` (21 days), and `min_commission_rate=0`.
- NodeSafe's live validator record returned `BONDED`, not jailed, `tokens=1000000000000000000` (1 SOBY), `min_self_delegation=1` (one asobya base unit), and commission rate 10% (max 50%, max change 10%). This records NodeSafe's current settings; it does not establish a universal recommended bond for every future validator.
- Fee-market REST queries returned HTTP 501. EVM RPC returned `eth_gasPrice=0`, `eth_maxPriorityFeePerGas=0`, and zero base-fee/reward samples in `eth_feeHistory`. No live transaction was sent. Do not infer that all transactions are free or quote a live transaction fee from these values.
- A read-only preflight run on workflow run 6 completed successfully: RPC chain/height, REST staking queries, EVM read-only calls, and TCP port checks all passed. This does not establish a second-node CometBFT handshake or sync.

The reachable P2P peer string is:

```text
1dad50ff897c247cba0ff646d0ee1ad59c3abc88@188.68.36.11:26656
```

TCP reachability is confirmed on `188.68.36.11:26656`; the launch package's old `:36656` endpoint timed out from the external runner. However, a second independent SOBYA node has not yet completed a CometBFT handshake and block sync. A zero peer count on the single existing node does not by itself mean that the public P2P port is closed. Treat `:26656` as the current candidate bootstrap endpoint pending a successful peer handshake; do not publish `:36656` as reachable.

## 3. Mandatory live validator preflight — PARTIALLY CLEARED

Before telling an applicant to create a validator, the team must verify and publish all of the following:

1. **P2P/bootstrap:** use the reachable NodeSafe peer above; confirm an independent node actually connects, catches up, and follows advancing blocks.
2. **Genesis:** use the exact immutable Genesis file from the project launch bundle that NodeSafe confirmed it used at launch. Do not ask for a replacement, modify it, regenerate it, or use the BonyNode rehearsal Genesis.
3. **Binary:** GitHub publishes `v0.1.0-rc.2` with Linux amd64/arm64 assets. NodeSafe must confirm the running `sobyad version` and source commit match the approved release before new operators are instructed to install it.
4. **Staking:** read current on-chain staking parameters, minimum self-delegation, denomination, transaction fees, and validator eligibility rules.
5. **Support:** publish the operator support contact and incident procedure.

The Genesis identity is already settled by the launch confirmation. The remaining transaction gate is to capture the current live staking parameters, existing validator record, running binary version/commit, and fee-market behavior. Until those live values are captured and reconciled with the exact release, send host-preparation and sync instructions only; do not guess a self-bond amount, gas price, or validator-creation command.

## 4. Review applications

The team reviews each application manually:

- Confirm operator identity and uniqueness.
- Check the exact binary, public consensus key, P2P reachability, infrastructure, monitoring, and backup plan.
- Verify the applicant can securely hold its own validator keys and operate independently.
- Do not fetch applicant-supplied URLs automatically; verify endpoints through controlled tooling.

## 5. Joining after chain launch

A validator joining after chain launch is not a genesis validator:

- Use only the immutable launch Genesis already confirmed by NodeSafe and the verified peer/bootstrap information.
- Synchronize to the live chain and verify chain ID and advancing height before attempting validator creation.
- Do not generate or submit a genesis gentx for a network that is already running.
- The operator creates its own validator with a signed live-chain staking transaction from its own wallet only after the exact binary, current staking parameters, self-bond requirement, and gas policy have been confirmed.
- The operator signs its own transactions. The SOBYA team must never request a seed phrase or private validator key.

The live chain confirms `asobya` as the staking denomination and NodeSafe's current self-bond is 1 SOBY; its on-chain `min_self_delegation` is 1 asobya. The chain does not expose a global minimum self-bond in the queried staking parameters. The launch package sets local Cosmos `minimum-gas-prices = "1000000000asobya"`, but live EVM fee quotes are zero and FeeMarket REST queries are not implemented (HTTP 501). The exact transaction gas/fee must therefore be reconciled with NodeSafe before any operator signs or broadcasts `create-validator`.

The exact live binary running on NodeSafe still needs its version/commit confirmed against the published `v0.1.0-rc.2` release. Do not use a genesis gentx. Do not send an operator a transaction command until binary, fee policy, funding source for the 1 SOBY self-bond, and successful P2P sync are resolved.

## 6. Conditional support

Support is separate from technical admission. No applicant pays an application fee or sends funds to an individual to be considered. A grant can be considered only after eligibility is verified, a separate spendable support budget is independently confirmed, and the amount/milestones are approved by the required humans.

The consensus-controlled validator reserve is not an onboarding wallet. The experimental support service records administrative decisions only; it does not sign or broadcast transfers.

## 7. Safety boundary

This onboarding process must not require changing the running NodeSafe validator, modifying Genesis, restarting existing validators, or upgrading the live chain. Every new operator runs and secures their own infrastructure and keys.
