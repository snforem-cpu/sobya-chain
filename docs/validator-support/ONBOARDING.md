# SOBYA Validator Onboarding

SOBYA mainnet uses CometBFT chain ID `sobya-1`. This guide has two stages: (A) prepare and synchronize an independent node, which interested operators can start now; and (B) create the live validator, which is done only after the node is fully synchronized and the final transaction settings are confirmed.

## 1. Apply and coordinate

Submit the no-fee [SOBYA Validator Application](https://github.com/snforem-cpu/sobya-chain/issues/new?template=validator-application.yml), or coordinate directly with the SOBYA team if already invited.

The issue is public. Share only public operator details, account/operator addresses, consensus public key, and public P2P/RPC endpoints. Never submit a seed phrase, private key, validator signing key, server password, SSH key, access token, or private contact information.

Applying is free. Admission and any optional support are reviewed separately; applying does not guarantee a grant.

## 2. Network details

- CometBFT chain ID: `sobya-1`
- Native coin: `SOBY`; base denomination: `asobya`; precision: 18 decimals (1 SOBY = 10^18 asobya)
- Public CometBFT RPC: https://sobya-rpc.nodesafe-app.xyz
- Cosmos REST: https://sobya-api.nodesafe-app.xyz
- EVM JSON-RPC: https://sobya-evm-rpc.nodesafe-app.xyz
- Explorer: https://explorer.nodesafe-app.xyz/sobya
- Current candidate NodeSafe P2P peer: `1dad50ff897c247cba0ff646d0ee1ad59c3abc88@188.68.36.11:26656`

Read-only external checks on 2026-11-11 confirmed the RPC chain ID and advancing blocks, Cosmos REST chain ID, EVM chain ID `357812033857`, and TCP reachability of `188.68.36.11:26656`. The old launch-package port `:36656` timed out. TCP reachability is not proof of a CometBFT handshake; the first joining operator's sync will provide the practical peer test. The candidate peer should be tested during node preparation.

## 3. Stage A — prepare and synchronize (operators can start now)

1. Provision a Linux server suitable for continuous operation. Keep the operating system updated and secure SSH access.
2. Download the published SOBYA `v0.1.0-rc.2` release for the server architecture from the project's GitHub Releases. Verify the published checksum before running it.
3. Obtain the exact immutable launch Genesis from the official SOBYA launch package. Its SHA-256 is `35207c189ee5548cb376cb4d5d9dbe4aa0509b3daf85b057e8e59db1c4b0314a`. NodeSafe confirmed it used this Genesis at launch. Do not generate a new Genesis, use the BonyNode rehearsal Genesis, or create a genesis `gentx`.
4. Configure the node for chain ID `sobya-1`, use the candidate NodeSafe peer above as a persistent peer, and expose the CometBFT P2P port required by the operator's configuration. Do not expose private validator keys or RPC admin interfaces.
5. Start the node and allow it to synchronize. Compare its reported chain ID and block height with the public RPC. Wait until `catching_up=false` and its height follows the live network.
6. Send the SOBYA team the public node ID, P2P endpoint, software version/commit, and a recent status/height. Never send `priv_validator_key.json`, `node_key.json`, keyring files, or passwords.

The team can review the peer handshake, sync, and release compatibility while the operator completes preparation. A new operator does not need to wait for a validator-creation transaction to begin this stage.

## 4. Live network facts checked

- Live staking denomination: `asobya`.
- `max_validators=100`; unbonding period 21 days; minimum commission rate 0.
- NodeSafe is BONDED and not jailed. Its current self-bond is 1 SOBY and its commission is 10%. These are NodeSafe's current values, not a universal recommended self-bond for every new operator.
- The chain's `min_self_delegation` field is one `asobya` base unit; it is not a meaningful network-wide self-bond recommendation.
- The launch package sets local Cosmos `minimum-gas-prices = "1000000000asobya"`. EVM RPC returned zero gas-price samples, while FeeMarket REST endpoints returned HTTP 501. These observations do not establish that Cosmos staking transactions are free.
- No live validator-creation transaction has been sent by the SOBYA team.

## 5. Stage B — create the validator (only after sync and final confirmation)

A validator joining after launch is created with a signed live-chain staking transaction, not a genesis `gentx`.

Before issuing the final command, the SOBYA team and operator must confirm:
- the node is fully synchronized and follows advancing blocks;
- the running `sobyad` version and source commit match the approved release;
- the operator's own account address, consensus public key, moniker, commission settings, and public P2P endpoint are correct;
- the exact self-bond amount and source of any starter funding are agreed;
- the Cosmos transaction gas/fee policy is confirmed with the live operator.

The operator creates and signs the transaction locally using its own wallet/keyring. The SOBYA team must never request or receive the operator's mnemonic, private account key, or validator signing key. Do not copy an unverified gas price or self-bond amount from old configuration.

## 6. Validator incentives and support

The published validator program reserves 150,000,000 SOBY for validator incentives and allocates 30% of network transaction fees to validators, subject to the live implementation and eligibility rules. NodeSafe is the initial launch operator and is recognized as the founding operator with continuing program privileges.

The current validator-reserve module releases scheduled rewards to eligible validators; it does not provide an immediate post-launch starter grant. Any initial 1 SOBY self-bond support must be approved separately and transferred only after the recipient address is verified. The reserve is not an onboarding wallet. No applicant pays an application fee or sends funds to an individual to apply.

## 7. Safety boundary

This onboarding process must not require changing the running NodeSafe validator, modifying or regenerating Genesis, restarting existing validators, or upgrading the live chain. Each operator runs and secures their own infrastructure and keys.