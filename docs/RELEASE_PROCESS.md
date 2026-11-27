# SOBYA Operator Release and Upgrade Process

SOBYA Mainnet is live. This document governs versioned binaries and safe upgrades to the existing network. A source commit or successful CI run is not itself a published release.

## Release rules

- Release from a reviewed, exact source commit on the approved branch.
- Run the full Go test suite and relevant localnet, multi-validator, EVM, fee-routing, reserve and network-configuration regression workflows on that exact commit.
- The dedicated `.github/workflows/validator-binary-release.yml` workflow builds Linux amd64 and arm64 binaries, packages them, produces SHA-256 checksums and publishes the GitHub release.
- Clearly identify whether a release is an upgrade candidate, a production-approved version, or a development build. Do not call an RC the active network version unless it is actually deployed.
- Never attach validator keys, wallet secrets, mnemonics or private genesis material.

## Validate a release

1. Confirm the source tree is clean and record the commit SHA.
2. Run unit and integration tests on that exact SHA.
3. Review dependency changes and vulnerability findings.
4. Confirm `sobyad version` reports the intended version and commit.
5. Verify the binary starts and its help/version commands work.
6. Reproduce the build or independently verify the published checksum.
7. Compare the candidate with the currently running network version and document compatibility and upgrade requirements.

## Publish and deploy

After review, create and push the agreed version tag. Inspect the release assets and checksum before distributing the binary. Production deployment is a coordinated network operation: confirm upgrade height/time, validator instructions, state compatibility, rollback/recovery plan and operator communications. Never imply that publishing a GitHub release automatically upgrades the live network.

## Operator verification

Download the binary and checksum file from the same official GitHub release:

```bash
sha256sum -c SHA256SUMS
./sobyad version
```

Operators must compare the reported version/commit with the project's approved upgrade announcement. Do not install binaries from chat attachments, unofficial mirrors or mutable branch downloads.
