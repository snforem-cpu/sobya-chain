// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaMultiMarketUsdOracle.sol";

contract MockSobyUsdSource {
    uint256 public price;
    uint32 public elapsed;
    bool public shouldRevert;

    constructor(uint256 price_, uint32 elapsed_) {
        price = price_;
        elapsed = elapsed_;
    }

    function set(uint256 price_, uint32 elapsed_, bool revert_) external {
        price = price_;
        elapsed = elapsed_;
        shouldRevert = revert_;
    }

    function sobyUsdPrice() external view returns (uint256, uint32) {
        require(!shouldRevert, "MOCK: SOURCE_UNAVAILABLE");
        return (price, elapsed);
    }
}

contract SobyaMultiMarketUsdOracleTest {
    MockSobyUsdSource private a;
    MockSobyUsdSource private b;
    MockSobyUsdSource private c;
    SobyaMultiMarketUsdOracle private oracle;

    function setUp() public {
        a = new MockSobyUsdSource(100e8, 30 minutes);
        b = new MockSobyUsdSource(102e8, 45 minutes);
        c = new MockSobyUsdSource(101e8, 2 hours);
        oracle = new SobyaMultiMarketUsdOracle(address(a), address(b), address(c), 500);
    }

    function testReturnsMedianAndShortestTwapWindow() public view {
        (uint256 price, uint32 elapsed) = oracle.sobyUsdPrice();
        require(price == 101e8, "MEDIAN_INCORRECT");
        require(elapsed == 30 minutes, "SHORTEST_WINDOW_INCORRECT");
    }

    function testRejectsDivergentMarkets() public {
        c.set(120e8, 30 minutes, false);
        (bool ok,) = address(oracle).staticcall(
            abi.encodeCall(oracle.sobyUsdPrice, ())
        );
        require(!ok, "DIVERGENT_SOURCES_ACCEPTED");
    }

    function testRejectsZeroPrice() public {
        b.set(0, 30 minutes, false);
        (bool ok,) = address(oracle).staticcall(
            abi.encodeCall(oracle.sobyUsdPrice, ())
        );
        require(!ok, "ZERO_PRICE_ACCEPTED");
    }

    function testRejectsInvalidTwapWindow() public {
        a.set(100e8, 29 minutes, false);
        (bool ok,) = address(oracle).staticcall(
            abi.encodeCall(oracle.sobyUsdPrice, ())
        );
        require(!ok, "INVALID_WINDOW_ACCEPTED");
    }

    function testUnavailableSourceReverts() public {
        b.set(102e8, 45 minutes, true);
        (bool ok,) = address(oracle).staticcall(
            abi.encodeCall(oracle.sobyUsdPrice, ())
        );
        require(!ok, "UNAVAILABLE_SOURCE_IGNORED");
    }

    function testRejectsDuplicateSources() public {
        (bool ok,) = address(this).call(abi.encodeWithSignature("deployDuplicateSources()"));
        require(!ok, "DUPLICATE_SOURCE_ACCEPTED");
    }

    function deployDuplicateSources() external {
        new SobyaMultiMarketUsdOracle(address(a), address(a), address(c), 500);
    }
}
