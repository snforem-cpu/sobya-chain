// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ISobyaUsdPoolOracle {
    function consult(address pair, address tokenIn, uint256 amountIn)
        external view returns (uint256 amountOut, uint32 elapsed);
}

interface ISobyaUsdPair {
    function token0() external view returns (address);
    function token1() external view returns (address);
    function getReserves() external view returns (uint112, uint112, uint32);
}

interface ISobyaUsdToken {
    function decimals() external view returns (uint8);
}

interface ISobyaUsdFeed {
    function decimals() external view returns (uint8);
    function latestRoundData() external view returns (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    );
}

/// @title SOBYA V2 USD Quote Adapter
/// @notice Converts one SOBY/quote-token pool TWAP into USD using a trusted quote-token/USD feed.
/// @dev This is NOT a global or multi-market price oracle. The deployer must choose a deep,
///      reputable quote pool and an independently operated, correctly denominated USD feed.
///      Applications needing a global price must aggregate independent venues and reject divergence.
contract SobyaV2UsdOracle {
    uint256 public constant USD_DECIMALS = 8;

    ISobyaUsdPoolOracle public immutable poolOracle;
    ISobyaUsdPair public immutable pair;
    ISobyaUsdFeed public immutable quoteUsdFeed;
    address public immutable sobyToken;
    address public immutable quoteToken;
    uint8 public immutable sobyDecimals;
    uint8 public immutable quoteDecimals;
    uint8 public immutable feedDecimals;
    uint256 public immutable minQuoteReserve;
    uint256 public immutable maxFeedAge;

    constructor(
        address poolOracle_,
        address pair_,
        address sobyToken_,
        address quoteToken_,
        address quoteUsdFeed_,
        uint256 minQuoteReserve_,
        uint256 maxFeedAge_
    ) {
        require(poolOracle_ != address(0) && poolOracle_.code.length > 0, "SOBYA_USD: INVALID_ORACLE");
        require(pair_ != address(0) && pair_.code.length > 0, "SOBYA_USD: INVALID_PAIR");
        require(sobyToken_ != address(0) && quoteToken_ != address(0) && sobyToken_ != quoteToken_,
            "SOBYA_USD: INVALID_TOKENS");
        require(quoteUsdFeed_ != address(0) && quoteUsdFeed_.code.length > 0, "SOBYA_USD: INVALID_FEED");
        require(minQuoteReserve_ > 0 && maxFeedAge_ > 0, "SOBYA_USD: INVALID_GUARDS");

        address token0 = ISobyaUsdPair(pair_).token0();
        address token1 = ISobyaUsdPair(pair_).token1();
        require(
            (token0 == sobyToken_ && token1 == quoteToken_) ||
            (token1 == sobyToken_ && token0 == quoteToken_),
            "SOBYA_USD: PAIR_TOKEN_MISMATCH"
        );

        uint8 sd = ISobyaUsdToken(sobyToken_).decimals();
        uint8 qd = ISobyaUsdToken(quoteToken_).decimals();
        uint8 fd = ISobyaUsdFeed(quoteUsdFeed_).decimals();
        require(sd <= 18 && qd <= 18 && fd <= 18, "SOBYA_USD: UNSUPPORTED_DECIMALS");

        poolOracle = ISobyaUsdPoolOracle(poolOracle_);
        pair = ISobyaUsdPair(pair_);
        quoteUsdFeed = ISobyaUsdFeed(quoteUsdFeed_);
        sobyToken = sobyToken_;
        quoteToken = quoteToken_;
        sobyDecimals = sd;
        quoteDecimals = qd;
        feedDecimals = fd;
        minQuoteReserve = minQuoteReserve_;
        maxFeedAge = maxFeedAge_;
    }

    /// @notice Returns the USD value of amountSoby, scaled to 8 decimals.
    /// @dev amountSoby is in raw SOBY units. Reverts on stale/incomplete feed rounds,
    ///      insufficient quote-side pool depth, stale pool TWAP, or arithmetic overflow.
    function consultSobyUsd(uint256 amountSoby) external view returns (uint256 usdAmount, uint32 twapElapsed) {
        require(amountSoby > 0, "SOBYA_USD: ZERO_AMOUNT");

        (uint112 reserve0, uint112 reserve1,) = pair.getReserves();
        uint256 quoteReserve = pair.token0() == quoteToken ? reserve0 : reserve1;
        require(quoteReserve >= minQuoteReserve, "SOBYA_USD: INSUFFICIENT_POOL_DEPTH");

        (uint80 roundId, int256 answer,, uint256 updatedAt, uint80 answeredInRound) =
            quoteUsdFeed.latestRoundData();
        require(answer > 0 && updatedAt != 0, "SOBYA_USD: INVALID_FEED_ANSWER");
        require(answeredInRound >= roundId, "SOBYA_USD: INCOMPLETE_FEED_ROUND");
        require(updatedAt <= block.timestamp && block.timestamp - updatedAt <= maxFeedAge,
            "SOBYA_USD: STALE_FEED");

        uint256 quoteAmount;
        (quoteAmount, twapElapsed) = poolOracle.consult(pairAddress(), sobyToken, amountSoby);
        uint256 feedAnswer = uint256(answer);
        uint256 scale = (10 ** uint256(quoteDecimals)) * (10 ** uint256(feedDecimals));
        require(quoteAmount <= type(uint256).max / feedAnswer / (10 ** USD_DECIMALS),
            "SOBYA_USD: VALUE_OVERFLOW");
        usdAmount = quoteAmount * feedAnswer * (10 ** USD_DECIMALS) / scale;
        require(usdAmount > 0, "SOBYA_USD: ZERO_USD_QUOTE");
    }

    function pairAddress() public view returns (address) {
        return address(pair);
    }

    /// @notice USD value of exactly one SOBY, scaled to 8 decimals.
    function sobyUsdPrice() external view returns (uint256 price, uint32 twapElapsed) {
        return this.consultSobyUsd(10 ** uint256(sobyDecimals));
    }
}
