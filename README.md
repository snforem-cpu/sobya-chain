![SOBYA official logo](assets/logo/sobya-coin-128.png)

# SOBYA Chain

Independent blockchain project for SOBYA (SOBY).

## Development status

This repository is being prepared on the `maintenance/verify-build` branch. The
Ignite scaffold workflow creates a **starter Cosmos SDK application** with the
`sobya` address prefix. A successful scaffold build is only a source-generation
and compilation check; it does not mean that a public SOBYA network is running.

The starter application is not yet the final SOBYA protocol. Do not use it for
real funds, announce a public mainnet, or treat its default genesis and validator
configuration as production settings.

## Current next steps

1. Generate and compile the starter source.
2. Implement and review SOBYA's actual token, fee, validator, and network rules.
3. Define and independently verify the genesis configuration.
4. Test multiple independent nodes, peer discovery, consensus, and transfers.
5. Publish reproducible node binaries and participant setup instructions.

## Repository safety

- Development changes belong on `maintenance/verify-build` until explicitly
  approved for integration.
- Never commit private validator keys, node keys, wallet seed phrases, or other
  secrets.
- GitHub Actions runners are temporary build machines, not permanent blockchain
  validators or network hosting.
