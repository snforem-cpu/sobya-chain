// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title SOBYA Ethereum USDT source escrow
/// @notice Testnet-first escrow for one signed cross-chain swap order per orderId.
/// @dev Trust model: a fixed threshold of independent payout attestors confirms the
///      SOBYA payout. This is NOT a light client and is not trustless.
///      No owner, admin withdrawal, token rescue, or arbitrary release function.
contract SobyaEthereumUsdtEscrow {
    bytes32 private constant ORDER_TYPEHASH = keccak256(
        "Order(bytes32 orderId,address user,address token,uint256 sourceAmount,address solver,uint256 destinationChainId,address destinationRecipient,uint256 destinationAmount,uint256 quoteExpiry,uint256 refundAfter)"
    );
    bytes32 private constant PAYOUT_TYPEHASH = keccak256(
        "Payout(bytes32 orderId,bytes32 destinationTxHash,uint256 destinationChainId,address destinationRecipient,uint256 destinationAmount,address escrow,uint256 sourceChainId)"
    );
    bytes32 private constant DOMAIN_TYPEHASH = keccak256(
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    );
    bytes32 private constant NAME_HASH = keccak256("SOBYA Cross-Chain Escrow");
    bytes32 private constant VERSION_HASH = keccak256("1");
    uint256 private constant SECP256K1N_HALF =
        0x7fffffffffffffffffffffffffffffff5d576e7357a4501ddfe92f46681b20a0;

    struct Order {
        bytes32 orderId;
        address user;
        address token;
        uint256 sourceAmount;
        address solver;
        uint256 destinationChainId;
        address destinationRecipient;
        uint256 destinationAmount;
        uint256 quoteExpiry;
        uint256 refundAfter;
    }

    enum Status { NONE, FUNDED, CLAIMED, REFUNDED }

    address public immutable token;
    uint256 public immutable threshold;
    mapping(address => bool) public isAttestor;
    mapping(bytes32 => Status) public status;
    mapping(bytes32 => Order) public orders;
    uint256 private entered = 1;

    event OrderFunded(bytes32 indexed orderId, address indexed user, address indexed solver, uint256 amount);
    event SolverClaimed(bytes32 indexed orderId, bytes32 destinationTxHash, address solver);
    event UserRefunded(bytes32 indexed orderId, address user, uint256 amount);

    error InvalidConfiguration();
    error InvalidOrder();
    error InvalidSignature();
    error InvalidAttestorSet();
    error OrderAlreadyUsed();
    error WrongStatus();
    error TooEarly();
    error TransferFailed();
    error ReentrantCall();

    modifier nonReentrant() {
        if (entered != 1) revert ReentrantCall();
        entered = 2;
        _;
        entered = 1;
    }

    constructor(address token_, address[] memory attestors_, uint256 threshold_) {
        // A 1-of-1 or 1-of-2 signer set is too fragile for custody.
        // Require at least three distinct keys and a strict-majority threshold.
        if (
            token_ == address(0) || attestors_.length < 3 || attestors_.length > 32 ||
            threshold_ <= attestors_.length / 2 || threshold_ > attestors_.length
        ) {
            revert InvalidConfiguration();
        }
        token = token_;
        threshold = threshold_;
        for (uint256 i; i < attestors_.length; ++i) {
            address signer = attestors_[i];
            if (signer == address(0) || isAttestor[signer]) revert InvalidConfiguration();
            isAttestor[signer] = true;
        }
    }

    function domainSeparator() public view returns (bytes32) {
        return keccak256(abi.encode(
            DOMAIN_TYPEHASH, NAME_HASH, VERSION_HASH, block.chainid, address(this)
        ));
    }

    function orderDigest(Order calldata order) external view returns (bytes32) {
        return _orderDigest(order);
    }

    function _orderDigest(Order calldata order) private view returns (bytes32) {
        bytes32 structHash = keccak256(abi.encode(
            ORDER_TYPEHASH, order.orderId, order.user, order.token, order.sourceAmount,
            order.solver, order.destinationChainId, order.destinationRecipient,
            order.destinationAmount, order.quoteExpiry, order.refundAfter
        ));
        return keccak256(abi.encodePacked("\x19\x01", domainSeparator(), structHash));
    }

    function fund(Order calldata order, bytes calldata solverQuoteSignature) external nonReentrant {
        if (
            order.orderId == bytes32(0) || order.user != msg.sender || order.token != token ||
            order.sourceAmount == 0 || order.solver == address(0) ||
            order.destinationChainId == 0 || order.destinationRecipient == address(0) ||
            order.destinationAmount == 0 || block.timestamp >= order.quoteExpiry ||
            order.refundAfter <= order.quoteExpiry
        ) revert InvalidOrder();
        if (status[order.orderId] != Status.NONE) revert OrderAlreadyUsed();
        if (_recover(_orderDigest(order), solverQuoteSignature) != order.solver) revert InvalidSignature();

        status[order.orderId] = Status.FUNDED;
        orders[order.orderId] = order;
        uint256 beforeBalance = _balanceOf(token, address(this));
        _safeTransferFrom(token, msg.sender, address(this), order.sourceAmount);
        uint256 received = _balanceOf(token, address(this)) - beforeBalance;
        if (received != order.sourceAmount) revert TransferFailed();
        emit OrderFunded(order.orderId, msg.sender, order.solver, order.sourceAmount);
    }

    function claim(bytes32 orderId, bytes32 destinationTxHash, bytes[] calldata payoutSignatures)
        external nonReentrant
    {
        if (status[orderId] != Status.FUNDED) revert WrongStatus();
        Order storage order = orders[orderId];
        if (msg.sender != order.solver || destinationTxHash == bytes32(0)) revert InvalidOrder();
        // The solver must complete the claim before the user's refund deadline.
        if (block.timestamp >= order.refundAfter) revert TooEarly();

        bytes32 structHash = keccak256(abi.encode(
            PAYOUT_TYPEHASH, orderId, destinationTxHash, order.destinationChainId,
            order.destinationRecipient, order.destinationAmount, address(this), block.chainid
        ));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", domainSeparator(), structHash));
        _verifyThreshold(digest, payoutSignatures);

        status[orderId] = Status.CLAIMED;
        _safeTransfer(token, order.solver, order.sourceAmount);
        emit SolverClaimed(orderId, destinationTxHash, order.solver);
    }

    function refund(bytes32 orderId) external nonReentrant {
        if (status[orderId] != Status.FUNDED) revert WrongStatus();
        Order storage order = orders[orderId];
        if (msg.sender != order.user) revert InvalidOrder();
        if (block.timestamp < order.refundAfter) revert TooEarly();

        status[orderId] = Status.REFUNDED;
        _safeTransfer(token, order.user, order.sourceAmount);
        emit UserRefunded(orderId, order.user, order.sourceAmount);
    }

    function _verifyThreshold(bytes32 digest, bytes[] calldata signatures) private view {
        if (signatures.length < threshold || signatures.length > 32) revert InvalidAttestorSet();
        address previous;
        uint256 valid;
        for (uint256 i; i < signatures.length; ++i) {
            address signer = _recover(digest, signatures[i]);
            if (signer <= previous || !isAttestor[signer]) revert InvalidAttestorSet();
            previous = signer;
            ++valid;
        }
        if (valid < threshold) revert InvalidAttestorSet();
    }

    function _recover(bytes32 digest, bytes calldata signature) private pure returns (address signer) {
        if (signature.length != 65) revert InvalidSignature();
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := calldataload(signature.offset)
            s := calldataload(add(signature.offset, 32))
            v := byte(0, calldataload(add(signature.offset, 64)))
        }
        if (uint256(s) > SECP256K1N_HALF || (v != 27 && v != 28)) revert InvalidSignature();
        signer = ecrecover(digest, v, r, s);
        if (signer == address(0)) revert InvalidSignature();
    }

    function _balanceOf(address asset, address account) private view returns (uint256 value) {
        (bool ok, bytes memory data) = asset.staticcall(abi.encodeWithSignature("balanceOf(address)", account));
        if (!ok || data.length < 32) revert TransferFailed();
        value = abi.decode(data, (uint256));
    }

    function _safeTransfer(address asset, address to, uint256 amount) private {
        (bool ok, bytes memory data) = asset.call(abi.encodeWithSignature("transfer(address,uint256)", to, amount));
        if (!ok || (data.length != 0 && !abi.decode(data, (bool)))) revert TransferFailed();
    }

    function _safeTransferFrom(address asset, address from, address to, uint256 amount) private {
        (bool ok, bytes memory data) = asset.call(
            abi.encodeWithSignature("transferFrom(address,address,uint256)", from, to, amount)
        );
        if (!ok || (data.length != 0 && !abi.decode(data, (bool)))) revert TransferFailed();
    }
}
