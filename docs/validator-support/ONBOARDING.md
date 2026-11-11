# SOBYA Validator Onboarding

This guide separates expressions of interest from permission to execute live-chain transactions. SOBYA mainnet is live on CometBFT chain ID `sobya-1`. A live endpoint preflight was run from external GitHub-hosted runners on 2026-11-11.

## 1. Apply (manual intake)

Submit the public [SOBYA Validator Application](https://github.com/snforem-cpu/sobya-chain/issues/new?template=validator-application.yml).

The issue is public. Provide only public operator details, public addresses, public consensus keys, and public P2P/RPC endpoints. Never submit a seed phrase, private key, validator signing key, server password, SSH key, access token, or private contact information. The team follows up through the applicant's GitHub account.

There is no application fee. Applying does not guarantee admission or a support grant. The issue form is a manual GitHub workflow; it is not connected to the experimental Go support API.

## 2. Published public endpoints

NodeSafe supplied these public endpoints:

- CometBFT RPC: https://sobya-rpc.nodesafe-app.xyz
- Cosmos REST API: https://sobya-api.nodesafe-app.xyz
- EVM JSON-RPC: https://sobya-evm-rpc.nodesafe-app.xyz
- Explorer: https://explorer.nodesafe-app.xyz/sobya

External read-only preflight results on 2026-11-11:

- CometBFT RPC returned chain ID `sobya-1`; block height advanced from 12851 to 12855 over 20 seconds.
- Cosmos REST returned chain ID `sobya-1`; staking query returned one validator record.
- EVM JSON-RPC returned production EVM chain ID `357812033857`, a non-zero block height, and successful `eth_getBalance` responses for the published founder and shared wallet addresses. Returned balances matched 400,000,000 SOBY and 450,000,000 SOBY respectively.
- CometBFT `/net_info` reported zero connected peers during the check.
- External TCP connection to the previously supplied NodeSafe P2P endpoint `188.68.36.11:36656` timed out from a GitHub-hosted runner.

The read-only RPC, REST, and EVM checks passed. P2P reachability did not pass. These checks establish endpoint responses at the time tested; they are not a security audit or a guarantee of continuous availability.

## 3. Mandatory validator synchronization gate — NOT YET CLEARED

Before instructing an applicant to synchronize or create a validator, the team must verify and publish all of the following:

1. A publicly reachable P2P endpoint, seed, or verified State Sync procedure. The current tested P2P address timed out and the node reported zero peers.
2. The exact supported binary release and its SHA-256 checksum.
3. The approved live Genesis SHA-256 and verified bootstrap/peer information.
4. Current on-chain staking parameters, minimum self-delegation, denomination, transaction fees, and validator eligibility rules.
5. A documented operator support contact and incident procedure.

Until the P2P/State Sync path and the remaining release/staking checks are verified, collect expressions of interest and prepare operator hosts only. Do not send applicants a gentx, live `create-validator` command, self-bond amount, or fee instructions.

## 4. Review applications

The team reviews each application manually:

- Confirm operator identity and uniqueness.
- Check the exact binary, public consensus key, P2P reachability, infrastructure, monitoring, and backup plan.
- Verify the applicant can securely hold its own validator keys and operate independently.
- Do not fetch applicant-supplied URLs automatically; verify endpoints through controlled tooling.

## 5. Joining after chain launch

A validator joining after chain launch is not a genesis validator:

- Use only the approved live Genesis and peer/bootstrap information published by the project after verification.
- Synchronize to the live chain and verify chain ID and height before attempting validator creation.
- Do not generate or submit a new genesis gentx for a network that is already running.
- Only after the synchronization gate and eligibility checks are complete may the operator use its own wallet and the supported binary's live-chain validator-creation transaction.
- The operator signs its own transactions. The SOBYA team must never request a seed phrase or private validator key.

The exact command, denomination, required amount, and transaction fees remain intentionally unpublished until confirmed against the current live binary and on-chain parameters.

## 6. Conditional support

Support is separate from technical admission. No applicant pays an application fee or sends funds to an individual to be considered. A grant can be considered only after eligibility is verified, a separate spendable support budget is independently confirmed, and the amount/milestones are approved by the required humans.

The consensus-controlled validator reserve is not an onboarding wallet. The experimental support service records administrative decisions only; it does not sign or broadcast transfers.

## 7. Safety boundary

This onboarding process must not require changing the running NodeSafe validator, modifying Genesis, restarting existing validators, or upgrading the live chain. Every new operator runs and secures their own infrastructure and keys.
