# SOBYA Validator Onboarding

This guide covers joining the already-running SOBYA Mainnet. The production CometBFT chain ID is `sobya-1`; the production EVM chain ID is `357812033857`. New operators join the existing chain and must not generate a new genesis or genesis gentx.

## 1. Apply (manual intake)

Submit the public [SOBYA Validator Application](https://github.com/snforem-cpu/sobya-chain/issues/new?template=validator-application.yml).

The issue is public. Provide only public operator details, public addresses, public consensus keys, and public P2P/RPC endpoints. Never submit a seed phrase, private key, validator signing key, server password, SSH key, access token, or private contact information. The team follows up through the applicant's GitHub account.

There is no application fee. Applying does not guarantee admission or a support grant. The issue form is a manual GitHub workflow; it is not connected to the experimental Go support API.

## 2. Live network connection details

SOBYA Mainnet is live. Use these public endpoints:

- EVM JSON-RPC for MetaMask, EVM wallets and EVM applications: `https://sobya-evm-rpc.nodesafe-dapp.xyz` (EVM chain ID `357812033857`).
- CometBFT RPC for consensus/node queries: `https://sobya-rpc.nodesafe-dapp.xyz` (CometBFT chain ID `sobya-1`).
- REST API: `https://sobya-api.nodesafe-dapp.xyz`.
- Explorer: `https://explorer.nodesafe-app.xyz/sobya`.

These are different interfaces: do not configure CometBFT RPC or REST as an EVM wallet RPC. Confirm the current release, peer information, sync height, staking parameters, minimum self-delegation and fees with the project before creating a validator.

## 3. Review applications

The team reviews each application manually:

- Confirm operator identity and uniqueness.
- Check the exact binary, public consensus key, P2P reachability, infrastructure, monitoring, and backup plan.
- Verify the applicant can securely hold its own validator keys and operate independently.
- Do not fetch applicant-supplied URLs automatically; verify endpoints through controlled tooling.

## 4. Join the existing live chain

A validator joining after launch is not a genesis validator:

- Install the exact supported SOBYA release and verify its published checksum.
- Configure the production CometBFT chain ID `sobya-1` and EVM chain ID `357812033857`.
- Obtain the current verified peer/bootstrap information from the project.
- Synchronize to the existing live chain and confirm the expected chain ID and advancing height.
- Read current staking parameters, denomination, minimum self-delegation and transaction fees from the live network.
- Create the validator using the supported live-chain transaction with the operator's own wallet. The operator signs its own transaction.

Do not generate or submit a new genesis gentx, create a replacement genesis, or start a separate network. Never send a seed phrase or private validator key to the SOBYA team.

## 5. Conditional support

Support is separate from technical admission. No applicant pays an application fee or sends funds to an individual to be considered. A grant can be considered only after eligibility is verified, a separate spendable support budget is independently confirmed, and the amount/milestones are approved by the required humans.

The consensus-controlled validator reserve is not an onboarding wallet. The separate off-chain support service is administrative only; it does not sign or broadcast validator transactions or alter consensus.

## 6. Safety boundary

This onboarding process must not require changing the running NodeSafe validator, modifying Genesis, restarting existing validators, or upgrading the live chain. Every new operator runs and secures their own infrastructure and keys.
