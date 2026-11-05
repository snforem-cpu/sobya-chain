# SOBYA Operator Release Process

This process describes how to create a versioned operator binary. A source commit or successful CI run is not itself a published release.

## Release rules

- Release only from a reviewed, exact source commit on the approved branch.
- Use a version tag such as `v0.1.0-rc.1` only after the release candidate passes the agreed tests.
- The current root workflow builds a Linux amd64 candidate and publishes it as a GitHub prerelease with SHA-256 checksums.
- A prerelease is a pre-mainnet operator candidate, not launch authorization. Release notes must state the exact source commit and that operators must wait for the signed launch bundle and genesis.
- Never attach genesis files containing private data or any operator keys/secrets.

## Candidate validation

Before tagging:
1. Confirm the source tree is clean and the commit SHA is recorded.
2. Run Go unit tests and the relevant localnet, multi-validator, EVM, fee-routing, reserve, and network-config workflows on that exact SHA.
3. Review dependency changes and vulnerability findings.
4. Confirm `sobyad version` reports the intended version and commit.
5. Confirm the binary starts and its help/version commands work.
6. Have an independent reviewer reproduce the build or verify the published checksum.

## Publish

After approval, create and push the agreed version tag on the reviewed commit. The root workflow builds `linux/amd64`, packages `sobyad`, emits `SHA256SUMS`, and creates a GitHub prerelease. Inspect the release assets and checksum before sharing them with operators.

No tag is created by this preparation change. No binary is claimed as released until the workflow actually completes and the release page contains the assets.

## Operator verification

Download the binary and checksum file from the same GitHub release:

```bash
sha256sum -c SHA256SUMS
./sobyad version
```

Operators must compare the reported version/commit with the coordinator's launch bundle. Do not install binaries from chat attachments, unofficial mirrors, or mutable branch downloads.
