# Independent observer quorum (prototype)

`observer_quorum.py` wraps the existing read-only chain-specific verifiers.
Configure one observer callback per independently operated RPC/observer path;
the wrapper accepts evidence only when a strict majority returns the same
normalized verified result.

## Properties

- Requires unique operator-supplied source IDs.
- Requires a strict majority (for example, 2 of 3 or 3 of 4 is rejected; 3 of
  4 is the minimum majority).
- Counts exceptions and malformed evidence as non-votes.
- Compares full dataclass/dictionary evidence, including block/transaction
  identity and amounts, rather than trusting a boolean success response.
- Returns agreeing and rejected source IDs without exposing provider exceptions
  or credentials.

## Security boundary

This is a local library, not a network service or proof system. Distinct source
IDs do not prove distinct operators, infrastructure, cloud regions, or upstream
data. Production configuration must document provider ownership, endpoint
independence, TLS/authentication, rate limits, monitoring, and outage policy.
A strict-majority RPC quorum reduces single-provider dependence but is not a
cryptographic light client and cannot prevent a colluding majority from lying.

The quorum wrapper does not sign attestations, hold keys, send transactions,
or release escrow funds. Chain-specific verifiers must still enforce each
network's finality rules before their evidence is eligible for quorum.
