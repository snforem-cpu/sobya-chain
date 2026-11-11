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

The reachable P2P peer string is:

```text
1dad50ff897c247cba0ff646d0ee1ad59c3abc88@188.68.36.11:26656
```

TCP reachability is confirmed, but a second independent SOBYA node has not yet completed a CometBFT handshake and block sync. A zero peer count on the single existing node does not by itself mean that the public P2P port is closed.

## 3. Mandatory live validator preflight — PARTIALLY CLEARED

Before telling an applicant to create a validator, the team must verify and publish all of the following:

1. **P2P/bootstrap:** use the reachable NodeSafe peer above; confirm an independent node actually connects, catches up, and follows advancing blocks.
2. **Exact live Genesis:** obtain the Genesis file and SHA-256 from the current mainnet operator and compare it with an independently trusted copy. Do not use the repository's older BonyNode rehearsal Genesis; its manifest identifies it as a public testnet rehearsal, not the currently running NodeSafe mainnet.
3. **Binary:** GitHub publishes `v0.1.0-rc.2` with Linux amd64/arm64 assets. NodeSafe must confirm the running `sobyad version` and source commit match the approved release before new operators are instructed to install it.
4. **Staking:** read current on-chain staking parameters, minimum self-delegation, denomination, transaction fees, and validator eligibility rules.
5. **Support:** publish the operator support contact and incident procedure.

Until the exact live Genesis checksum and staking/self-delegation/fee parameters are confirmed, collect expressions of interest and prepare operator hosts only. Do not send applicants a genesis gentx, live `create-validator` command, self-bond amount, or fee instructions.

## 4. Review applications

The team reviews each application manually:

- Confirm operator identity and uniqueness.
- Check the exact binary, public consensus key, P2P reachability, infrastructure, monitoring, and backup plan.
- Verify the applicant can securely hold its own validator keys and operate independently.
- Do not fetch applicant-supplied URLs automatically; verify endpoints through controlled tooling.

## 5. Joining after chain launch

A validator joining after chain launch is not a genesis validator:

- Use only the approved live Genesis and verified peer/bootstrap information.
- Synchronize to the live chain and verify chain ID and height before attempting validator creation.
- Do not generate or submit a new genesis gentx for a network that is already running.
- Only after the synchronization and eligibility checks are complete may the operator use its own wallet and the supported binary's live-chain validator-creation transaction.
- The operator signs its own transactions. The SOBYA team must never request a seed phrase or private validator key.

The exact command, denomination, required amount, and transaction fees remain unpublished until confirmed against the current live binary and on-chain parameters.

## 6. Conditional support

Support is separate from technical admission. No applicant pays an application fee or sends funds to an individual to be considered. A grant can be considered only after eligibility is verified, a separate spendable support budget is independently confirmed, and the amount/milestones are approved by the required humans.

The consensus-controlled validator reserve is not an onboarding wallet. The experimental support service records administrative decisions only; it does not sign or broadcast transfers.

## 7. Safety boundary

This onboarding process must not require changing the running NodeSafe validator, modifying Genesis, restarting existing validators, or upgrading the live chain. Every new operator runs and secures their own infrastructure and keys.
