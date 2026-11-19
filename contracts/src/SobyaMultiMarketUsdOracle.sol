// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ISobyaUsdPriceSource {
    /// @notice Returns USD per SOBY scaled to 8 decimals and the source TWAP window in seconds.
    function sobyUsdPrice() external view returns (uint256 price, uint32 twapElapsed);
}

/// @title SOBYA Multi-Market USD Oracle
/// @notice Median of three independently configured SOBY/USD market adapters.
/// @dev This is only as independent as its configured sources. Operators MUST use three
///      economically independent, liquid venues/quote markets and independent USD feeds.
///      Three contracts pointing at the same pool do not create independent price discovery.
contract SobyaMultiMarketUsdOracle {
    uint16 public constant BPS = 10_000;

    ISobyaUsdPriceSource public immutable source0;
    ISobyaUsdPriceSource public immutable source1;
    ISobyaUsdPriceSource public immutable source2;
    uint16 public immutable maxDeviationBps;

    constructor(address source0_, address source1_, address source2_, uint16 maxDeviationBps_) {
        require(
            source0_ != address(0) && source1_ != address(0) && source2_ != address(0) &&
            source0_.code.length > 0 && source1_.code.length > 0 && source2_.code.length > 0,
            "SOBYA_MULTI: INVALID_SOURCE"
        );
        require(
            source0_ != source1_ && source0_ != source2_ && source1_ != source2_,
            "SOBYA_MULTI: DUPLICATE_SOURCE"
        );
        require(maxDeviationBps_ > 0 && maxDeviationBps_ <= 2_000,
            "SOBYA_MULTI: INVALID_DEVIATION");
        source0 = ISobyaUsdPriceSource(source0_);
        source1 = ISobyaUsdPriceSource(source1_);
        source2 = ISobyaUsdPriceSource(source2_);
        maxDeviationBps = maxDeviationBps_;
    }

    /// @notice Returns the median USD price per SOBY (8 decimals) and shortest source TWAP window.
    /// @dev All three sources must be live and valid; the function fails closed if any source reverts.
    function sobyUsdPrice() external view returns (uint256 medianPrice, uint32 minTwapElapsed) {
        (uint256 p0, uint32 e0) = source0.sobyUsdPrice();
        (uint256 p1, uint32 e1) = source1.sobyUsdPrice();
        (uint256 p2, uint32 e2) = source2.sobyUsdPrice();
        require(p0 > 0 && p1 > 0 && p2 > 0, "SOBYA_MULTI: ZERO_PRICE");

        uint256 low = p0;
        uint256 mid = p1;
        uint256 high = p2;
        if (low > mid) (low, mid) = (mid, low);
        if (mid > high) (mid, high) = (high, mid);
        if (low > mid) (low, mid) = (mid, low);

        require(mid <= type(uint256).max / maxDeviationBps, "SOBYA_MULTI: PRICE_OVERFLOW");
        require(high - low <= mid * maxDeviationBps / BPS, "SOBYA_MULTI: SOURCE_DIVERGENCE");

        medianPrice = mid;
        minTwapElapsed = e0 < e1 ? e0 : e1;
        if (e2 < minTwapElapsed) minTwapElapsed = e2;
    }
}
