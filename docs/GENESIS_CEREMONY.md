# Historical genesis ceremony reference — SOBYA Mainnet is already live

This document is retained for historical reference only. The genesis-ceremony process described here is not the procedure for joining the running SOBYA Mainnet.

**SOBYA Mainnet is live** with CometBFT chain ID `sobya-1` and EVM chain ID `357812033857`. Public endpoints and network details are maintained in the [repository overview](../README.md).

A new validator must synchronize to the existing network and use the supported live-chain validator-creation transaction. Do not create a replacement genesis, generate a new genesis gentx, change the chain ID, or ask existing operators to restart from a new genesis.

The allocation and tokenomics sections below are historical design records. For current operational rules, use the running chain's parameters and the current [validator onboarding guide](validator-support/ONBOARDING.md). Never treat draft addresses, historical genesis hashes, or old peer lists as current production configuration.

All operators must generate and retain their own private keys, mnemonics, keyrings, node keys and validator signing files. Never send secrets to the coordinator.
