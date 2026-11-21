// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaTronUsdtEscrow.sol";
import "../src/SobyaEthereumUsdtEscrow.sol";

interface VmTronEscrow {
    function addr(uint256 privateKey) external returns (address);
    function sign(uint256 privateKey, bytes32 digest) external returns (uint8 v, bytes32 r, bytes32 s);
    function prank(address sender) external;
    function warp(uint256 timestamp) external;
}

contract MockTronUsdt {
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    function mint(address to, uint256 amount) external { balanceOf[to] += amount; }
    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount; return true;
    }
    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "balance");
        balanceOf[msg.sender] -= amount; balanceOf[to] += amount; return true;
    }
    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(balanceOf[from] >= amount && allowance[from][msg.sender] >= amount, "funds");
        allowance[from][msg.sender] -= amount; balanceOf[from] -= amount; balanceOf[to] += amount; return true;
    }
}

contract SobyaTronUsdtEscrowTest {
    VmTronEscrow private constant vm = VmTronEscrow(address(uint160(uint256(keccak256("hevm cheat code")))));
    uint256 private constant USER_KEY = 0xA11CE;
    uint256 private constant SOLVER_KEY = 0xB0B;
    uint256 private constant ATTESTOR_KEY_1 = 0xC0FFEE;
    uint256 private constant ATTESTOR_KEY_2 = 0xD00D;
    uint256 private constant ATTESTOR_KEY_3 = 0xBEEF;
    MockTronUsdt private usdt;
    SobyaTronUsdtEscrow private escrow;
    address private user;
    address private solver;
    address private attestor1;
    address private attestor2;
    address private attestor3;

    function setUp() public {
        user = vm.addr(USER_KEY); solver = vm.addr(SOLVER_KEY);
        attestor1 = vm.addr(ATTESTOR_KEY_1); attestor2 = vm.addr(ATTESTOR_KEY_2);
        attestor3 = vm.addr(ATTESTOR_KEY_3);
        address[] memory attestors = new address[](3);
        attestors[0] = attestor1; attestors[1] = attestor2; attestors[2] = attestor3;
        for (uint256 i; i < attestors.length; ++i) {
            for (uint256 j = i + 1; j < attestors.length; ++j) {
                if (attestors[j] < attestors[i]) {
                    (attestors[i], attestors[j]) = (attestors[j], attestors[i]);
                }
            }
        }
        usdt = new MockTronUsdt();
        escrow = new SobyaTronUsdtEscrow(address(usdt), attestors, 2);
        usdt.mint(user, 100_000_000);
        vm.prank(user); usdt.approve(address(escrow), 100_000_000);
    }

    function _order() private view returns (SobyaEthereumUsdtEscrow.Order memory) {
        return SobyaEthereumUsdtEscrow.Order({
            orderId: keccak256("tron-test-order-1"), user: user, token: address(usdt),
            sourceAmount: 25_000_000, solver: solver,
            destinationChainId: 357812033857, destinationRecipient: address(0x5150),
            destinationAmount: 1 ether, quoteExpiry: block.timestamp + 300,
            refundAfter: block.timestamp + 900
        });
    }

    function _signature(uint256 key, bytes32 digest) private returns (bytes memory) {
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(key, digest);
        return abi.encodePacked(r, s, v);
    }

    function _payoutSignatures(bytes32 orderId) private returns (bytes[] memory signatures) {
        bytes32 typeHash = keccak256("Payout(bytes32 orderId,bytes32 destinationTxHash,uint256 destinationChainId,address destinationRecipient,uint256 destinationAmount,address escrow,uint256 sourceChainId)");
        bytes32 structHash = keccak256(abi.encode(
            typeHash, orderId, keccak256("sobya-tron-payout-tx"), 357812033857,
            address(0x5150), 1 ether, address(escrow), block.chainid
        ));
        bytes32 domainTypeHash = keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");
        bytes32 domain = keccak256(abi.encode(
            domainTypeHash, keccak256("SOBYA Cross-Chain Escrow"), keccak256("1"),
            block.chainid, address(escrow)
        ));
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", domain, structHash));
        signatures = new bytes[](2);
        if (attestor1 < attestor2) {
            signatures[0] = _signature(ATTESTOR_KEY_1, digest);
            signatures[1] = _signature(ATTESTOR_KEY_2, digest);
        } else {
            signatures[0] = _signature(ATTESTOR_KEY_2, digest);
            signatures[1] = _signature(ATTESTOR_KEY_1, digest);
        }
    }

    function testTronEscrowFundAndAttestedClaim() public {
        SobyaEthereumUsdtEscrow.Order memory order = _order();
        bytes memory quote = _signature(SOLVER_KEY, escrow.orderDigest(order));
        vm.prank(user); escrow.fund(order, quote);
        require(escrow.status(order.orderId) == SobyaEthereumUsdtEscrow.Status.FUNDED, "not funded");
        bytes[] memory sigs = _payoutSignatures(order.orderId);
        vm.prank(solver); escrow.claim(order.orderId, keccak256("sobya-tron-payout-tx"), sigs);
        require(escrow.status(order.orderId) == SobyaEthereumUsdtEscrow.Status.CLAIMED, "not claimed");
        require(usdt.balanceOf(solver) == order.sourceAmount, "solver not paid");
    }

    function testTronEscrowRefundIsExclusiveTerminalState() public {
        SobyaEthereumUsdtEscrow.Order memory order = _order();
        bytes memory quote = _signature(SOLVER_KEY, escrow.orderDigest(order));
        vm.prank(user); escrow.fund(order, quote);
        vm.warp(order.refundAfter);
        bytes[] memory sigs = _payoutSignatures(order.orderId);
        vm.prank(solver);
        (bool lateClaim,) = address(escrow).call(abi.encodeWithSelector(
            escrow.claim.selector, order.orderId, keccak256("sobya-tron-payout-tx"), sigs
        ));
        require(!lateClaim, "claim after refund deadline");
        vm.prank(user); escrow.refund(order.orderId);
        require(escrow.status(order.orderId) == SobyaEthereumUsdtEscrow.Status.REFUNDED, "not refunded");
        require(usdt.balanceOf(user) == 100_000_000, "user not refunded");
        vm.prank(solver);
        (bool ok,) = address(escrow).call(abi.encodeWithSelector(
            escrow.claim.selector, order.orderId, keccak256("sobya-tron-payout-tx"), sigs
        ));
        require(!ok, "claim after refund");
    }

    function testTronEscrowRejectsWrongSolverQuote() public {
        SobyaEthereumUsdtEscrow.Order memory order = _order();
        bytes memory badQuote = _signature(USER_KEY, escrow.orderDigest(order));
        vm.prank(user);
        (bool ok,) = address(escrow).call(abi.encodeWithSelector(escrow.fund.selector, order, badQuote));
        require(!ok, "wrong quote accepted");
        require(usdt.balanceOf(address(escrow)) == 0, "funds moved");
    }
}
