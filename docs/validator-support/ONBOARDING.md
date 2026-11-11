# SOBYA Validator Onboarding

This guide separates expression of interest from permission to execute live-chain transactions. The chain ID used in the operator launch materials is sobya-1, but every applicant-facing operational instruction must be checked against current live evidence first.

## 1. Apply (manual intake)

Submit the public [SOBYA Validator Application](https://github.com/snforem-cpu/sobya-chain/issues/new?template=validator-application.yml).

The issue is public. Provide only public operator details, public addresses, public consensus keys, and public P2P/RPC endpoints. Never submit a seed phrase, private key, validator signing key, server password, SSH key, access token, or private contact information. The team follows up through the applicant's GitHub account.

There is no application fee. Applying does not guarantee admission or a support grant. The issue form is a manual GitHub workflow; it is not connected to the experimental Go support API.

## 2. Mandatory live-network preflight (team-owned)

Before telling an applicant to synchronize or create a validator, the team must publish and verify all of the following:

1. A read-only public RPC endpoint reachable from outside the validator host.
2. A recent successful query showing chain ID sobya-1, current block height, and advancing blocks on repeated checks.
3. The exact supported binary release and its SHA-256 checksum.
4. The approved live Genesis SHA-256 and a verified P2P/bootstrap peer list.
5. Current staking parameters, minimum self-delegation, denomination, transaction fees, and validator eligibility rules read from the running chain.
6. A documented operator support contact and incident procedure.

**Current publication gap:** no public RPC endpoint is published in this repository. NodeSafe's previously supplied RPC endpoint was loopback-only; it is not an external RPC service. A P2P address alone cannot prove that the chain is producing blocks or replace RPC-based checks. Until the preflight above is complete, collect expressions of interest only and do not send transaction commands or amount/fee instructions.

## 3. Review applications

The team reviews each application manually:

- Confirm operator identity and uniqueness.
- Check the exact binary, public consensus key, P2P reachability, infrastructure, monitoring, and backup plan.
- Verify the applicant can securely hold its own validator keys and operate independently.
- Do not fetch applicant-supplied URLs automatically; verify endpoints through controlled tooling.

## 4. Joining after chain launch

A validator joining after chain launch is not a genesis validator:

- Use only the approved live Genesis and peer/bootstrap information published by the project after verification.
- Synchronize to the live chain and verify chain ID and height before attempting validator creation.
- Do not generate or submit a new genesis gentx for a network that is already running.
- Only after the preflight and eligibility checks are complete may the operator use its own wallet and the supported binary's live-chain validator-creation transaction.
- The operator signs its own transactions. The SOBYA team must never request a seed phrase or private validator key.

The exact command, denomination, required amount, and transaction fees are intentionally omitted until they are confirmed against the current live binary and on-chain parameters.

## 5. Conditional support

Support is separate from technical admission. No applicant pays an application fee or sends funds to an individual to be considered. A grant can be considered only after eligibility is verified, a separate spendable support budget is independently confirmed, and the amount/milestones are approved by the required humans.

The consensus-controlled validator reserve is not an onboarding wallet. The experimental support service records administrative decisions only; it does not sign or broadcast transfers.

## 6. Safety boundary

This onboarding process must not require changing the running NodeSafe validator, modifying Genesis, restarting existing validators, or upgrading the live chain. Every new operator runs and secures their own infrastructure and keys.
