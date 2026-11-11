# SOBYA Live Validator Onboarding

This is the fast path for independent operators who want to join the already-running `sobya-1` network.

## Apply

Submit the public [SOBYA Validator Application](../../issues/new?template=validator-application.yml).

The issue is public. Provide only public operator details, public addresses, public consensus keys, and public P2P/RPC endpoints. Never submit a seed phrase, private key, validator signing key, server password, SSH key, access token, or other secret. The team will follow up through the applicant's GitHub account.

There is no application fee. Applying does not guarantee admission or a support grant.

## Fast admission checklist

The team reviews each application in this order:

1. Confirm the target chain ID is `sobya-1` and identify the exact supported SOBYA binary release.
2. Confirm the operator account and validator identity are unique and the submitted consensus key is a public key.
3. Verify current live-chain staking parameters and the actual minimum self-delegation requirement. Do not rely on old screenshots, draft genesis files, or assumed amounts.
4. Check the node's synchronization, P2P reachability, peer connectivity, server capacity, monitoring, and backup plan.
5. Confirm the operator can securely hold its own validator keys and maintain the node independently.
6. If the operator requests onboarding support, assess it separately against the published support policy and a verified, spendable support budget.

## Joining an already-running network

A validator joining after chain launch is not a genesis validator:

- Use the current live network's genesis and peer/bootstrap information supplied through the project's verified release/documentation.
- Synchronize the node to the live chain before attempting validator creation.
- Do **not** generate or submit a new genesis `gentx` for a network that is already running.
- Once eligibility and the live minimum self-delegation are verified, the operator uses their own wallet and the supported binary's live-chain validator creation transaction.
- The operator signs their own transactions. The SOBYA team must never ask for the operator's seed phrase or private validator key.

The exact command, denomination, required amount, and transaction fees must be confirmed against the current live binary and on-chain parameters before being sent to an applicant. This guide intentionally does not guess those values.

## Support grants

Support is separate from technical admission. No applicant should pay an application fee or send funds to an individual to be considered. A grant can be considered only after:

- eligibility and operator identity are verified;
- the total support budget is independently confirmed as spendable;
- the grant amount and milestones are approved under the program policy; and
- staged payments are approved by the required human approvers.

The existing consensus-controlled validator reserve must not be treated as a liquid onboarding wallet. The support service records administrative decisions; it does not sign or broadcast transfers.

## Safety boundary

This onboarding process does not require changing the running NodeSafe validator, modifying genesis, restarting existing validators, or upgrading the live chain. Every new operator runs and secures their own infrastructure and keys.
