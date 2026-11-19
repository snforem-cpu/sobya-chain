// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaV2Factory.sol";
import "../src/SobyaV2Pair.sol";
import "../src/SobyaV2Oracle.sol";

interface VmOracle {
    function warp(uint256) external;
}

contract OracleMockToken {
    mapping(address => uint256) public balanceOf;
    function mint(address to, uint256 amount) external { balanceOf[to] += amount; }
    function burn(address from, uint256 amount) external {
        require(balanceOf[from] >= amount, "MOCK: BALANCE");
        balanceOf[from] -= amount;
    }
    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "MOCK: BALANCE");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

contract SobyaV2OracleTest {
    VmOracle private constant vm = VmOracle(address(uint160(uint256(keccak256("hevm cheat code")))));
    SobyaV2Factory private factory;
    SobyaV2Oracle private oracle;
    OracleMockToken private tokenA;
    OracleMockToken private tokenB;
    SobyaV2Pair private pair;

    function setUp() public {
        vm.warp(1_000_000);
        factory = new SobyaV2Factory();
        oracle = new SobyaV2Oracle(address(factory));
        tokenA = new OracleMockToken();
        tokenB = new OracleMockToken();
        address pairAddress = factory.createPair(address(tokenA), address(tokenB));
        pair = SobyaV2Pair(pairAddress);
        tokenA.mint(address(this), 1_000 ether);
        tokenB.mint(address(this), 1_000 ether);
        tokenA.transfer(pairAddress, 100 ether);
        tokenB.transfer(pairAddress, 100 ether);
        pair.mint(address(this));
    }

    function testRequiresInitialObservationAndMinimumWindow() public {
        address token0 = pair.token0();
        (bool uninitialized,) = address(oracle).staticcall(
            abi.encodeCall(oracle.consultPriceX112, (address(pair), token0))
        );
        require(!uninitialized, "UNINITIALIZED_ORACLE_ACCEPTED");

        oracle.update(address(pair));
        vm.warp(block.timestamp + oracle.MIN_PERIOD() - 1);
        (bool tooSoon,) = address(oracle).staticcall(
            abi.encodeCall(oracle.consultPriceX112, (address(pair), token0))
        );
        require(!tooSoon, "SHORT_WINDOW_ACCEPTED");
    }

    function testEqualReservePoolReturnsOneToOneTwap() public {
        oracle.update(address(pair));
        vm.warp(block.timestamp + oracle.MIN_PERIOD());
        address token0 = pair.token0();
        (uint256 averagePrice, uint32 elapsed) = oracle.consultPriceX112(address(pair), token0);
        require(elapsed == oracle.MIN_PERIOD(), "WRONG_WINDOW");
        require(averagePrice == 2 ** 112, "WRONG_ONE_TO_ONE_PRICE");
        (uint256 amountOut,) = oracle.consult(address(pair), token0, 1 ether);
        require(amountOut == 1 ether, "WRONG_ONE_TO_ONE_QUOTE");
    }

    function testTwapAveragesAcrossReserveChangeRatherThanSpot() public {
        oracle.update(address(pair));
        vm.warp(block.timestamp + 15 minutes);

        address token0 = pair.token0();
        OracleMockToken input = token0 == address(tokenA) ? tokenA : tokenB;

        input.transfer(address(pair), 10 ether);
        pair.swap(0, 9 ether, address(this));

        vm.warp(block.timestamp + 15 minutes);
        (uint256 averagePrice,) = oracle.consultPriceX112(address(pair), token0);
        require(averagePrice < 2 ** 112, "TWAP_IGNORED_PRICE_CHANGE");
        require(averagePrice > (2 ** 112) / 2, "TWAP_OUT_OF_EXPECTED_RANGE");
    }

    function testPublicUpdateCannotKeepResettingConsultWindow() public {
        oracle.update(address(pair));
        vm.warp(block.timestamp + oracle.MIN_PERIOD());
        oracle.update(address(pair));

        (uint256 firstPrice, uint32 firstElapsed) =
            oracle.consultPriceX112(address(pair), pair.token0());
        require(firstPrice == 2 ** 112, "FIRST_CHECKPOINT_PRICE");
        require(firstElapsed == oracle.MIN_PERIOD(), "FIRST_CHECKPOINT_WINDOW");

        vm.warp(block.timestamp + oracle.MIN_PERIOD());
        oracle.update(address(pair));
        (uint256 nextPrice, uint32 nextElapsed) =
            oracle.consultPriceX112(address(pair), pair.token0());
        require(nextPrice == 2 ** 112, "NEXT_CHECKPOINT_PRICE");
        require(nextElapsed == oracle.MIN_PERIOD(), "NEXT_CHECKPOINT_WINDOW");
    }

    function testTimestampWrapKeepsTwapElapsedTimeCorrect() public {
        vm.warp((uint256(1) << 32) - 900);
        oracle.update(address(pair));
        vm.warp((uint256(1) << 32) + 900);
        (uint256 averagePrice, uint32 elapsed) =
            oracle.consultPriceX112(address(pair), pair.token0());
        require(elapsed == oracle.MIN_PERIOD(), "WRAP_WINDOW_INCORRECT");
        require(averagePrice == 2 ** 112, "WRAP_PRICE_INCORRECT");
    }

    function testToken1DirectionReturnsReciprocalTwap() public {
        oracle.update(address(pair));
        vm.warp(block.timestamp + oracle.MIN_PERIOD());
        (uint256 averagePrice,) = oracle.consultPriceX112(address(pair), pair.token1());
        require(averagePrice == 2 ** 112, "TOKEN1_PRICE_INCORRECT");
    }

    function testHistoricalTwapRemainsReadableAfterPoolLosesAllLiquidity() public {
        oracle.update(address(pair));
        vm.warp(block.timestamp + oracle.MIN_PERIOD());

        tokenA.burn(address(pair), tokenA.balanceOf(address(pair)));
        tokenB.burn(address(pair), tokenB.balanceOf(address(pair)));
        pair.sync();

        (uint256 averagePrice, uint32 elapsed) =
            oracle.consultPriceX112(address(pair), pair.token0());
        require(elapsed == oracle.MIN_PERIOD(), "EMPTY_POOL_WINDOW_INCORRECT");
        require(averagePrice == 2 ** 112, "EMPTY_POOL_HISTORICAL_PRICE_INCORRECT");

        (bool updateSucceeded,) = address(oracle).call(
            abi.encodeCall(oracle.update, (address(pair)))
        );
        require(!updateSucceeded, "EMPTY_POOL_NEW_OBSERVATION_ACCEPTED");
    }

    function testRejectsInvalidToken() public {
        address unknownToken = address(0x1234);
        (bool ok,) = address(oracle).staticcall(
            abi.encodeCall(oracle.consultPriceX112, (address(pair), unknownToken))
        );
        require(!ok, "INVALID_TOKEN_ACCEPTED");
    }

    function testRejectsStaleObservation() public {
        oracle.update(address(pair));
        vm.warp(block.timestamp + oracle.MAX_PERIOD() + 1);
        (bool ok,) = address(oracle).staticcall(
            abi.encodeCall(oracle.consultPriceX112, (address(pair), pair.token0()))
        );
        require(!ok, "STALE_PRICE_ACCEPTED");
    }

    function testRejectsUnregisteredPair() public {
        (bool ok,) = address(oracle).call(
            abi.encodeCall(oracle.update, (address(this)))
        );
        require(!ok, "UNREGISTERED_PAIR_ACCEPTED");
    }
}
