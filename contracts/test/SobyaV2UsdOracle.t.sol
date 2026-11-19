// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaV2UsdOracle.sol";

interface VmUsd {
    function warp(uint256) external;
}

contract MockUsdToken {
    uint8 public immutable decimals;
    constructor(uint8 decimals_) { decimals = decimals_; }
}

contract MockUsdPair {
    address public immutable token0;
    address public immutable token1;
    uint112 public reserve0;
    uint112 public reserve1;
    constructor(address token0_, address token1_, uint112 reserve0_, uint112 reserve1_) {
        token0 = token0_;
        token1 = token1_;
        reserve0 = reserve0_;
        reserve1 = reserve1_;
    }
    function getReserves() external view returns (uint112, uint112, uint32) {
        return (reserve0, reserve1, 0);
    }
    function setReserves(uint112 reserve0_, uint112 reserve1_) external {
        reserve0 = reserve0_;
        reserve1 = reserve1_;
    }
}

contract MockUsdFeed {
    uint8 public immutable decimals;
    uint80 public roundId = 1;
    int256 public answer = 1e8;
    uint256 public updatedAt;
    uint80 public answeredInRound = 1;

    constructor(uint8 decimals_) { decimals = decimals_; }
    function setRound(uint80 roundId_, int256 answer_, uint256 updatedAt_, uint80 answeredInRound_) external {
        roundId = roundId_;
        answer = answer_;
        updatedAt = updatedAt_;
        answeredInRound = answeredInRound_;
    }
    function latestRoundData() external view returns (uint80, int256, uint256, uint256, uint80) {
        return (roundId, answer, updatedAt, updatedAt, answeredInRound);
    }
}

contract MockPoolOracle {
    uint256 public quoteAmount = 2e6;
    uint32 public elapsed = 1800;
    function setQuote(uint256 amount, uint32 elapsed_) external {
        quoteAmount = amount;
        elapsed = elapsed_;
    }
    function consult(address, address, uint256) external view returns (uint256, uint32) {
        require(elapsed >= 30 minutes && elapsed <= 2 hours, "MOCK: INVALID_TWAP_WINDOW");
        return (quoteAmount, elapsed);
    }
}

contract SobyaV2UsdOracleTest {
    VmUsd private constant vm = VmUsd(address(uint160(uint256(keccak256("hevm cheat code")))));
    MockUsdToken private soby;
    MockUsdToken private quote;
    MockUsdPair private pair;
    MockUsdFeed private feed;
    MockPoolOracle private poolOracle;
    SobyaV2UsdOracle private usdOracle;

    function setUp() public {
        vm.warp(1_000_000);
        soby = new MockUsdToken(18);
        quote = new MockUsdToken(6);
        pair = new MockUsdPair(address(soby), address(quote), 1_000e18, 1_000e6);
        feed = new MockUsdFeed(8);
        feed.setRound(1, 1e8, block.timestamp, 1);
        poolOracle = new MockPoolOracle();
        usdOracle = new SobyaV2UsdOracle(
            address(poolOracle), address(pair), address(soby), address(quote),
            address(feed), 100e6, 1 hours
        );
    }

    function testConvertsPoolTwapAndFeedToUsdEightDecimals() public view {
        (uint256 usdAmount, uint32 elapsed) = usdOracle.consultSobyUsd(1 ether);
        require(usdAmount == 2e8, "USD_DECIMAL_SCALING_WRONG");
        require(elapsed == 1800, "TWAP_ELAPSED_WRONG");
        (uint256 oneSobyPrice,) = usdOracle.sobyUsdPrice();
        require(oneSobyPrice == 2e8, "ONE_SOBY_PRICE_WRONG");
    }

    function testRejectsStaleUsdFeed() public {
        feed.setRound(2, 1e8, block.timestamp - 1 hours - 1, 2);
        (bool ok,) = address(usdOracle).staticcall(
            abi.encodeCall(usdOracle.consultSobyUsd, (1 ether))
        );
        require(!ok, "STALE_FEED_ACCEPTED");
    }

    function testRejectsIncompleteFeedRound() public {
        feed.setRound(2, 1e8, block.timestamp, 1);
        (bool ok,) = address(usdOracle).staticcall(
            abi.encodeCall(usdOracle.consultSobyUsd, (1 ether))
        );
        require(!ok, "INCOMPLETE_ROUND_ACCEPTED");
    }

    function testRejectsZeroOrNegativeFeedAnswer() public {
        feed.setRound(2, 0, block.timestamp, 2);
        (bool ok,) = address(usdOracle).staticcall(
            abi.encodeCall(usdOracle.consultSobyUsd, (1 ether))
        );
        require(!ok, "ZERO_FEED_ANSWER_ACCEPTED");
    }

    function testRejectsInsufficientQuotePoolDepth() public {
        pair.setReserves(1_000e18, 99e6);
        (bool ok,) = address(usdOracle).staticcall(
            abi.encodeCall(usdOracle.consultSobyUsd, (1 ether))
        );
        require(!ok, "THIN_POOL_ACCEPTED");
    }

    function testRejectsZeroAmount() public {
        (bool ok,) = address(usdOracle).staticcall(
            abi.encodeCall(usdOracle.consultSobyUsd, (0))
        );
        require(!ok, "ZERO_AMOUNT_ACCEPTED");
    }

    function testRejectsIncompleteOrStalePoolTwap() public {
        poolOracle.setQuote(2e6, 10);
        (bool ok,) = address(usdOracle).staticcall(
            abi.encodeCall(usdOracle.consultSobyUsd, (1 ether))
        );
        require(!ok, "SHORT_TWAP_ACCEPTED");
    }
}
