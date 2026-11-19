// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ISobyaOracleFactory {
    function getPair(address tokenA, address tokenB) external view returns (address);
}

interface ISobyaOraclePair {
    function token0() external view returns (address);
    function token1() external view returns (address);
    function getReserves() external view returns (uint112, uint112, uint32);
    function currentCumulativePrices() external view returns (uint256, uint256, uint32);
}

/// @title SOBYA V2 TWAP Oracle
/// @notice Permissionless, time-weighted prices for pairs created by one trusted SOBYA V2 factory.
/// @dev This is a pool TWAP, NOT a global market price or a USD oracle. Consumers must assess
///      pool depth, quote-asset quality, and independent market references for their use case.
contract SobyaV2Oracle {
    uint32 public constant MIN_PERIOD = 30 minutes;
    uint32 public constant MAX_PERIOD = 2 hours;
    uint256 private constant Q112 = 2 ** 112;

    address public immutable factory;

    struct Observation {
        uint256 price0Cumulative;
        uint256 price1Cumulative;
        uint32 timestamp;
        bool initialized;
    }

    mapping(address => Observation) public observations;
    mapping(address => Observation) public previousObservations;

    event ObservationInitialized(address indexed pair, uint32 timestamp);
    event ObservationUpdated(address indexed pair, uint32 timestamp, uint32 elapsed);

    constructor(address factory_) {
        require(factory_ != address(0) && factory_.code.length > 0, "SOBYA_ORACLE: INVALID_FACTORY");
        factory = factory_;
    }

    /// @notice Starts or rolls the observation window. Anyone may call this.
    /// @dev A fresh checkpoint requires nonzero reserves; prior checkpoints remain available.
    function update(address pair) external {
        _validatePair(pair);
        (uint112 reserve0, uint112 reserve1,) = ISobyaOraclePair(pair).getReserves();
        require(reserve0 > 0 && reserve1 > 0, "SOBYA_ORACLE: NO_LIQUIDITY");

        (uint256 cumulative0, uint256 cumulative1, uint32 timestamp) =
            ISobyaOraclePair(pair).currentCumulativePrices();

        Observation storage latest = observations[pair];
        if (!latest.initialized) {
            latest.price0Cumulative = cumulative0;
            latest.price1Cumulative = cumulative1;
            latest.timestamp = timestamp;
            latest.initialized = true;
            emit ObservationInitialized(pair, timestamp);
            return;
        }

        uint32 elapsed;
        unchecked { elapsed = timestamp - latest.timestamp; }
        require(elapsed >= MIN_PERIOD, "SOBYA_ORACLE: PERIOD_TOO_SHORT");

        previousObservations[pair] = latest;
        latest.price0Cumulative = cumulative0;
        latest.price1Cumulative = cumulative1;
        latest.timestamp = timestamp;
        emit ObservationUpdated(pair, timestamp, elapsed);
    }

    /// @notice Returns the average quote-token amount for a raw base-token amount.
    /// @return amountOut Raw units of the other token; account for each token's decimals.
    /// @return elapsed Seconds included in the TWAP.
    function consult(address pair, address tokenIn, uint256 amountIn)
        external view returns (uint256 amountOut, uint32 elapsed)
    {
        require(amountIn > 0, "SOBYA_ORACLE: ZERO_AMOUNT");
        uint256 averagePriceX112;
        (averagePriceX112, elapsed) = consultPriceX112(pair, tokenIn);
        require(amountIn <= type(uint256).max / averagePriceX112,
            "SOBYA_ORACLE: AMOUNT_OVERFLOW");
        amountOut = amountIn * averagePriceX112 / Q112;
        require(amountOut > 0, "SOBYA_ORACLE: ZERO_QUOTE");
    }

    /// @notice Returns the average price in UQ112x112 form and the observation window.
    /// @dev A historical TWAP remains readable after reserves reach zero because the pair's
    ///      cumulative-price function freezes (does not divide by zero) when reserves are empty.
    ///      This does not permit a new observation until liquidity is restored.
    function consultPriceX112(address pair, address tokenIn)
        public view returns (uint256 averagePriceX112, uint32 elapsed)
    {
        _validatePair(pair);
        address token0 = ISobyaOraclePair(pair).token0();
        address token1 = ISobyaOraclePair(pair).token1();
        require(tokenIn == token0 || tokenIn == token1, "SOBYA_ORACLE: INVALID_TOKEN");

        (uint256 cumulative0, uint256 cumulative1, uint32 timestamp) =
            ISobyaOraclePair(pair).currentCumulativePrices();

        Observation memory observation = previousObservations[pair];
        if (!observation.initialized) observation = observations[pair];
        else {
            uint32 previousAge;
            unchecked { previousAge = timestamp - observation.timestamp; }
            if (previousAge > MAX_PERIOD) observation = observations[pair];
        }
        require(observation.initialized, "SOBYA_ORACLE: NOT_INITIALIZED");

        unchecked { elapsed = timestamp - observation.timestamp; }
        require(elapsed >= MIN_PERIOD, "SOBYA_ORACLE: PERIOD_TOO_SHORT");
        require(elapsed <= MAX_PERIOD, "SOBYA_ORACLE: STALE_OBSERVATION");

        uint256 cumulativeDelta;
        if (tokenIn == token0) {
            unchecked { cumulativeDelta = cumulative0 - observation.price0Cumulative; }
        } else {
            unchecked { cumulativeDelta = cumulative1 - observation.price1Cumulative; }
        }
        averagePriceX112 = cumulativeDelta / elapsed;
        require(averagePriceX112 > 0, "SOBYA_ORACLE: INVALID_PRICE");
    }

    function _validatePair(address pair) private view {
        require(pair != address(0) && pair.code.length > 0, "SOBYA_ORACLE: INVALID_PAIR");
        address token0 = ISobyaOraclePair(pair).token0();
        address token1 = ISobyaOraclePair(pair).token1();
        require(token0 != address(0) && token1 != address(0) && token0 != token1,
            "SOBYA_ORACLE: INVALID_TOKENS");
        require(ISobyaOracleFactory(factory).getPair(token0, token1) == pair,
            "SOBYA_ORACLE: UNREGISTERED_PAIR");
    }
}
