// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ISobyaSolverInventoryVault {
    function reservations(bytes32 orderId) external view returns (
        address solver, address recipient, uint128 amount, uint64 releaseAfter, bool active
    );
    function executePayout(
        bytes32 orderId,
        bytes32 sourceChain,
        bytes32 sourceEscrow,
        bytes32 sourceAsset,
        uint256 sourceAmount,
        bytes[] calldata sourceAttestations
    ) external nonReentrant {
        if (
            orderId == bytes32(0) || sourceChain == bytes32(0) ||
            sourceEscrow == bytes32(0) || sourceAsset == bytes32(0) ||
            sourceAmount == 0
        ) revert InvalidPayout();
        if (orderStatus[orderId] != Status.NONE) revert OrderAlreadyPaid();

        VaultReservation memory reservation;
        (
            reservation.solver,
            reservation.recipient,
            reservation.amount,
            reservation.releaseAfter,
            reservation.active
        ) = inventoryVault.reservations(orderId);
        if (
            !reservation.active || reservation.solver == address(0) ||
            reservation.recipient == address(0) || reservation.amount == 0 ||
            block.timestamp >= reservation.releaseAfter
        ) revert ReservationUnavailable();

        Payout memory payout = Payout({
            sourceChain: sourceChain,
            sourceEscrow: sourceEscrow,
            sourceAsset: sourceAsset,
            sourceAmount: sourceAmount,
            recipient: reservation.recipient,
            sobyAmount: reservation.amount,
            solver: reservation.solver,
            destinationChainId: block.chainid
        });
        _verifySourceAttestations(orderId, payout, reservation.releaseAfter, sourceAttestations);

        orderStatus[orderId] = Status.PAID;
        payouts[orderId] = payout;
        inventoryVault.executePayout(orderId);

        emit PayoutExecuted(
            orderId, payout.sourceChain, payout.sourceEscrow, payout.sourceAsset,
            payout.sourceAmount, payout.recipient, payout.sobyAmount,
            payout.solver, payout.destinationChainId
        );
    }

    function _verifySourceAttestations(
        bytes32 orderId,\n        Payout memory payout,
        uint64 releaseAfter,
        bytes[] calldata signatures
    ) private view {
        if (
            signatures.length < attestationThreshold ||
            signatures.length > attestorCount
        ) revert InvalidAttestation();

        bytes32 domainSeparator = keccak256(abi.encode(
            DOMAIN_TYPEHASH, NAME_HASH, VERSION_HASH, block.chainid, address(this)
        ));
        bytes32 structHash = keccak256(abi.encode(
            PAYOUT_TYPEHASH,
            orderId,
            payout.sourceChain,
            payout.sourceEscrow,
            payout.sourceAsset,
            payout.sourceAmount,
            payout.recipient,
            payout.sobyAmount,
            payout.solver,
            payout.destinationChainId,
            releaseAfter
        ));
        bytes32 digest = keccak256(abi.encodePacked("\\x19\\x01", domainSeparator, structHash));

        address previousSigner;
        for (uint256 i; i < signatures.length; ++i) {
            address signer = _recover(digest, signatures[i]);
            if (
                signer == address(0) || !isAttestor[signer] ||
                uint160(signer) <= uint160(previousSigner)
            ) revert InvalidAttestation();
            previousSigner = signer;
        }
    }

    function _recover(bytes32 digest, bytes calldata signature) private pure returns (address signer) {
        if (signature.length != 65) revert InvalidAttestation();
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := calldataload(signature.offset)
            s := calldataload(add(signature.offset, 32))
            v := byte(0, calldataload(add(signature.offset, 64)))
        }
        if (uint256(s) > SECP256K1_HALF_ORDER || (v != 27 && v != 28)) {
            revert InvalidAttestation();
        }
        signer = ecrecover(digest, v, r, s);
    }
}
