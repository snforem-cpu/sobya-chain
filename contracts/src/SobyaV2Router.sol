// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ISobyaRouterFactory {
    function getPair(address, address) external view returns (address);
    function createPair(address, address) external returns (address);
}
interface ISobyaRouterPair {
    function token0() external view returns (address);
    function getReserves() external view returns (uint112, uint112, uint32);
    function mint(address) external returns (uint256);
    function burn(address) external returns (uint256, uint256);
    function swap(uint256, uint256, address) external;
    function transferFrom(address, address, uint256) external returns (bool);
}
interface ISobyaRouterToken {
    function balanceOf(address) external view returns (uint256);
    function transfer(address, uint256) external returns (bool);
    function transferFrom(address, address, uint256) external returns (bool);
}
interface ISobyaWrappedNative is ISobyaRouterToken {
    function deposit() external payable;
    function withdraw(uint256) external;
}

/// @title SOBYA V2 Router
/// @notice Router for ERC-20 pairs and native SOBY through WSOBY.
/// @dev Fee-on-transfer swap methods measure actual pair input and recipient output.
///      Rebasing, reflection, callback-dependent and otherwise non-standard tokens remain unsupported.
contract SobyaV2Router {
    address public immutable factory;
    address public immutable wrappedSoby;

    struct LiquidityRequest {
        address tokenA;
        address tokenB;
        address pair;
        address recipient;
        uint256 nominalA;
        uint256 nominalB;
        uint256 minA;
        uint256 minB;
    }

    modifier ensure(uint256 deadline) {
        require(deadline >= block.timestamp, "SOBYA: EXPIRED");
        _;
    }

    constructor(address factory_, address wrappedSoby_) {
        require(factory_ != address(0) && factory_.code.length > 0, "SOBYA: INVALID_FACTORY");
        // Token-only router paths do not need WSOBY to be deployed; native-SOBY paths
        // will naturally revert if the configured wrapped token has no implementation.
        require(wrappedSoby_ != address(0), "SOBYA: INVALID_WRAPPED_SOBY");
        factory = factory_;
        wrappedSoby = wrappedSoby_;
    }

    receive() external payable {
        require(msg.sender == wrappedSoby, "SOBYA: NATIVE_SENDER_NOT_WRAPPED");
    }

    function _safeTransfer(address token, address to, uint256 value) private {
        (bool ok, bytes memory data) = token.call(
            abi.encodeWithSelector(ISobyaRouterToken.transfer.selector, to, value)
        );
        require(ok && (data.length == 0 || abi.decode(data, (bool))), "SOBYA: TRANSFER_FAILED");
    }

    function _safeTransferFrom(address token, address from, address to, uint256 value) private {
        (bool ok, bytes memory data) = token.call(
            abi.encodeWithSelector(ISobyaRouterToken.transferFrom.selector, from, to, value)
        );
        require(ok && (data.length == 0 || abi.decode(data, (bool))), "SOBYA: TRANSFER_FROM_FAILED");
    }

    function _safeNativeTransfer(address to, uint256 value) private {
        (bool ok,) = payable(to).call{value: value}("");
        require(ok, "SOBYA: NATIVE_TRANSFER_FAILED");
    }

    function _pairFor(address a, address b) private view returns (address pair) {
        pair = ISobyaRouterFactory(factory).getPair(a, b);
        require(pair != address(0), "SOBYA: PAIR_NOT_FOUND");
    }

    function _sort(address a, address b) private pure returns (bool aIs0) {
        require(a != b, "SOBYA: IDENTICAL_ADDRESSES");
        require(a != address(0) && b != address(0), "SOBYA: ZERO_ADDRESS");
        aIs0 = a < b;
    }

    function _reservesFor(address a, address b, address pair)
        private view returns (uint256 reserveA, uint256 reserveB)
    {
        (uint112 r0, uint112 r1,) = ISobyaRouterPair(pair).getReserves();
        (reserveA, reserveB) = _sort(a, b) ? (r0, r1) : (r1, r0);
    }

    function _reserves(address a, address b) private view returns (uint256 reserveA, uint256 reserveB) {
        return _reservesFor(a, b, _pairFor(a, b));
    }

    function quote(uint256 amountA, uint256 reserveA, uint256 reserveB)
        public pure returns (uint256 amountB)
    {
        require(amountA > 0, "SOBYA: INSUFFICIENT_AMOUNT");
        require(reserveA > 0 && reserveB > 0, "SOBYA: INSUFFICIENT_LIQUIDITY");
        amountB = amountA * reserveB / reserveA;
    }

    function getAmountOut(uint256 amountIn, uint256 reserveIn, uint256 reserveOut)
        public pure returns (uint256 amountOut)
    {
        require(amountIn > 0, "SOBYA: INSUFFICIENT_INPUT");
        require(reserveIn > 0 && reserveOut > 0, "SOBYA: INSUFFICIENT_LIQUIDITY");
        uint256 amountInWithFee = amountIn * 997;
        amountOut = amountInWithFee * reserveOut / (reserveIn * 1000 + amountInWithFee);
    }

    function getAmountIn(uint256 amountOut, uint256 reserveIn, uint256 reserveOut)
        public pure returns (uint256 amountIn)
    {
        require(amountOut > 0 && reserveIn > 0 && reserveOut > amountOut, "SOBYA: INSUFFICIENT_LIQUIDITY");
        amountIn = reserveIn * amountOut * 1000 / ((reserveOut - amountOut) * 997) + 1;
    }

    function getAmountsOut(uint256 amountIn, address[] calldata path)
        external view returns (uint256[] memory amounts)
    {
        require(path.length >= 2, "SOBYA: INVALID_PATH");
        amounts = new uint256[](path.length);
        amounts[0] = amountIn;
        for (uint256 i; i < path.length - 1; ++i) {
            (uint256 reserveIn, uint256 reserveOut) = _reserves(path[i], path[i + 1]);
            amounts[i + 1] = getAmountOut(amounts[i], reserveIn, reserveOut);
        }
    }

    function _optimalLiquidity(address a, address b, uint256 desiredA, uint256 desiredB, address pair)
        private view returns (uint256 amountA, uint256 amountB)
    {
        (uint256 reserveA, uint256 reserveB) = _reservesFor(a, b, pair);
        require((reserveA == 0 && reserveB == 0) || (reserveA > 0 && reserveB > 0),
            "SOBYA: INVALID_RESERVES");
        if (reserveA == 0) return (desiredA, desiredB);
        uint256 optimalB = quote(desiredA, reserveA, reserveB);
        if (optimalB <= desiredB) return (desiredA, optimalB);
        uint256 optimalA = quote(desiredB, reserveB, reserveA);
        require(optimalA <= desiredA, "SOBYA: INVALID_OPTIMAL_AMOUNT");
        return (optimalA, desiredB);
    }

    function _getOrCreatePair(address a, address b) private returns (address pair) {
        require(a != b && a != address(0) && b != address(0), "SOBYA: INVALID_TOKENS");
        pair = ISobyaRouterFactory(factory).getPair(a, b);
        if (pair == address(0)) pair = ISobyaRouterFactory(factory).createPair(a, b);
    }

    function addLiquidity(
        address a, address b, uint256 desiredA, uint256 desiredB,
        uint256 minA, uint256 minB, address to, uint256 deadline
    ) external ensure(deadline) returns (uint256 amountA, uint256 amountB, uint256 liquidity) {
        require(to != address(0), "SOBYA: ZERO_TO");
        LiquidityRequest memory request;
        request.tokenA = a;
        request.tokenB = b;
        request.recipient = to;
        request.minA = minA;
        request.minB = minB;
        request.pair = _getOrCreatePair(a, b);
        (request.nominalA, request.nominalB) =
            _optimalLiquidity(a, b, desiredA, desiredB, request.pair);
        return _addLiquidityMeasured(request);
    }

    function _addLiquidityMeasured(LiquidityRequest memory p)
        private returns (uint256 amountA, uint256 amountB, uint256 liquidity)
    {
        uint256 beforeA = ISobyaRouterToken(p.tokenA).balanceOf(p.pair);
        uint256 beforeB = ISobyaRouterToken(p.tokenB).balanceOf(p.pair);
        _safeTransferFrom(p.tokenA, msg.sender, p.pair, p.nominalA);
        _safeTransferFrom(p.tokenB, msg.sender, p.pair, p.nominalB);
        amountA = ISobyaRouterToken(p.tokenA).balanceOf(p.pair) - beforeA;
        amountB = ISobyaRouterToken(p.tokenB).balanceOf(p.pair) - beforeB;
        require(amountA >= p.minA && amountB >= p.minB, "SOBYA: SLIPPAGE");
        liquidity = ISobyaRouterPair(p.pair).mint(p.recipient);
    }

    function addLiquiditySOBY(
        address token, uint256 desiredToken, uint256 minToken, uint256 minSoby,
        address to, uint256 deadline
    ) external payable ensure(deadline) returns (uint256 amountToken, uint256 amountSoby, uint256 liquidity) {
        require(msg.value > 0 && to != address(0), "SOBYA: INVALID_VALUE_OR_TO");
        address pair = _getOrCreatePair(token, wrappedSoby);
        (uint256 nominalToken, uint256 nominalSoby) =
            _optimalLiquidity(token, wrappedSoby, desiredToken, msg.value, pair);
        uint256 beforeToken = ISobyaRouterToken(token).balanceOf(pair);
        _safeTransferFrom(token, msg.sender, pair, nominalToken);
        amountToken = ISobyaRouterToken(token).balanceOf(pair) - beforeToken;
        amountSoby = nominalSoby;
        require(amountToken >= minToken && amountSoby >= minSoby, "SOBYA: SLIPPAGE");
        ISobyaWrappedNative(wrappedSoby).deposit{value: amountSoby}();
        _safeTransfer(wrappedSoby, pair, amountSoby);
        liquidity = ISobyaRouterPair(pair).mint(to);
        if (msg.value > amountSoby) _safeNativeTransfer(msg.sender, msg.value - amountSoby);
    }

    function removeLiquidity(
        address a, address b, uint256 liquidity, uint256 minA, uint256 minB,
        address to, uint256 deadline
    ) external ensure(deadline) returns (uint256 amountA, uint256 amountB) {
        require(to != address(0), "SOBYA: ZERO_TO");
        address pair = _pairFor(a, b);
        require(ISobyaRouterPair(pair).transferFrom(msg.sender, pair, liquidity), "SOBYA: LP_TRANSFER_FAILED");
        (uint256 amount0, uint256 amount1) = ISobyaRouterPair(pair).burn(to);
        (amountA, amountB) = _sort(a, b) ? (amount0, amount1) : (amount1, amount0);
        require(amountA >= minA && amountB >= minB, "SOBYA: SLIPPAGE");
    }

    function removeLiquiditySupportingFeeOnTransferTokens(
        address a, address b, uint256 liquidity, uint256 minA, uint256 minB,
        address to, uint256 deadline
    ) external ensure(deadline) returns (uint256 amountA, uint256 amountB) {
        require(to != address(0), "SOBYA: ZERO_TO");
        address pair = _pairFor(a, b);
        uint256 beforeA = ISobyaRouterToken(a).balanceOf(to);
        uint256 beforeB = ISobyaRouterToken(b).balanceOf(to);
        require(
            ISobyaRouterPair(pair).transferFrom(msg.sender, pair, liquidity),
            "SOBYA: LP_TRANSFER_FAILED"
        );
        ISobyaRouterPair(pair).burn(to);
        amountA = ISobyaRouterToken(a).balanceOf(to) - beforeA;
        amountB = ISobyaRouterToken(b).balanceOf(to) - beforeB;
        require(amountA >= minA && amountB >= minB, "SOBYA: SLIPPAGE");
    }

    function removeLiquiditySOBY(
        address token, uint256 liquidity, uint256 minToken, uint256 minSoby,
        address to, uint256 deadline
    ) external ensure(deadline) returns (uint256 amountToken, uint256 amountSoby) {
        require(to != address(0), "SOBYA: ZERO_TO");
        address pair = _pairFor(token, wrappedSoby);
        require(ISobyaRouterPair(pair).transferFrom(msg.sender, pair, liquidity), "SOBYA: LP_TRANSFER_FAILED");
        uint256 beforeToken = ISobyaRouterToken(token).balanceOf(address(this));
        uint256 beforeWrapped = ISobyaRouterToken(wrappedSoby).balanceOf(address(this));
        uint256 beforeRecipient = ISobyaRouterToken(token).balanceOf(to);
        ISobyaRouterPair(pair).burn(address(this));
        uint256 receivedToken = ISobyaRouterToken(token).balanceOf(address(this)) - beforeToken;
        uint256 receivedWrapped = ISobyaRouterToken(wrappedSoby).balanceOf(address(this)) - beforeWrapped;
        _safeTransfer(token, to, receivedToken);
        // Enforce slippage against the recipient's net balance delta, including transfer tax.
        amountToken = ISobyaRouterToken(token).balanceOf(to) - beforeRecipient;
        ISobyaWrappedNative(wrappedSoby).withdraw(receivedWrapped);
        amountSoby = receivedWrapped;
        require(amountToken >= minToken && amountSoby >= minSoby, "SOBYA: SLIPPAGE");
        _safeNativeTransfer(to, amountSoby);
    }

    function _swap(uint256[] memory amounts, address[] calldata path, address to) private {
        for (uint256 i; i < path.length - 1; ++i) {
            (address input, address output) = (path[i], path[i + 1]);
            address pair = _pairFor(input, output);
            address nextTo = i < path.length - 2 ? _pairFor(output, path[i + 2]) : to;
            uint256 out = amounts[i + 1];
            bool inputIs0 = input < output;
            ISobyaRouterPair(pair).swap(inputIs0 ? 0 : out, inputIs0 ? out : 0, nextTo);
        }
    }

    function swapExactTokensForTokens(
        uint256 amountIn, uint256 amountOutMin, address[] calldata path,
        address to, uint256 deadline
    ) external ensure(deadline) returns (uint256[] memory amounts) {
        require(path.length >= 2 && to != address(0), "SOBYA: INVALID_PATH_OR_TO");
        amounts = new uint256[](path.length);
        amounts[0] = amountIn;
        for (uint256 i; i < path.length - 1; ++i) {
            (uint256 reserveIn, uint256 reserveOut) = _reserves(path[i], path[i + 1]);
            amounts[i + 1] = getAmountOut(amounts[i], reserveIn, reserveOut);
        }
        require(amounts[amounts.length - 1] >= amountOutMin, "SOBYA: INSUFFICIENT_OUTPUT_AMOUNT");
        _safeTransferFrom(path[0], msg.sender, _pairFor(path[0], path[1]), amountIn);
        _swap(amounts, path, to);
    }

    function swapExactTokensForTokensSupportingFeeOnTransferTokens(
        uint256 amountIn, uint256 amountOutMin, address[] calldata path,
        address to, uint256 deadline
    ) external ensure(deadline) {
        require(path.length >= 2 && to != address(0), "SOBYA: INVALID_PATH_OR_TO");
        uint256 beforeOut = ISobyaRouterToken(path[path.length - 1]).balanceOf(to);
        _safeTransferFrom(path[0], msg.sender, _pairFor(path[0], path[1]), amountIn);
        _swapSupportingFeeOnTransferTokens(path, to);
        uint256 received = ISobyaRouterToken(path[path.length - 1]).balanceOf(to) - beforeOut;
        require(received >= amountOutMin, "SOBYA: INSUFFICIENT_OUTPUT_AMOUNT");
    }

    function _swapSupportingFeeOnTransferTokens(address[] calldata path, address to) private {
        for (uint256 i; i < path.length - 1; ++i) {
            (address input, address output) = (path[i], path[i + 1]);
            address pair = _pairFor(input, output);
            (uint256 reserveInput, uint256 reserveOutput) = _reservesFor(input, output, pair);
            uint256 balanceInput = ISobyaRouterToken(input).balanceOf(pair);
            require(balanceInput >= reserveInput, "SOBYA: INPUT_BELOW_RESERVE");
            uint256 amountInput = balanceInput - reserveInput;
            uint256 amountOutput = getAmountOut(amountInput, reserveInput, reserveOutput);
            address nextTo = i < path.length - 2 ? _pairFor(output, path[i + 2]) : to;
            bool inputIs0 = input < output;
            ISobyaRouterPair(pair).swap(
                inputIs0 ? 0 : amountOutput,
                inputIs0 ? amountOutput : 0,
                nextTo
            );
        }
    }

    function swapExactSOBYForTokens(
        uint256 amountOutMin, address[] calldata path, address to, uint256 deadline
    ) external payable ensure(deadline) returns (uint256[] memory amounts) {
        require(path.length >= 2 && path[0] == wrappedSoby && msg.value > 0 && to != address(0),
            "SOBYA: INVALID_NATIVE_PATH");
        amounts = new uint256[](path.length);
        amounts[0] = msg.value;
        for (uint256 i; i < path.length - 1; ++i) {
            (uint256 reserveIn, uint256 reserveOut) = _reserves(path[i], path[i + 1]);
            amounts[i + 1] = getAmountOut(amounts[i], reserveIn, reserveOut);
        }
        require(amounts[amounts.length - 1] >= amountOutMin, "SOBYA: INSUFFICIENT_OUTPUT_AMOUNT");
        ISobyaWrappedNative(wrappedSoby).deposit{value: msg.value}();
        _safeTransfer(wrappedSoby, _pairFor(path[0], path[1]), msg.value);
        _swap(amounts, path, to);
    }

    function swapExactSOBYForTokensSupportingFeeOnTransferTokens(
        uint256 amountOutMin, address[] calldata path, address to, uint256 deadline
    ) external payable ensure(deadline) {
        require(path.length >= 2 && path[0] == wrappedSoby && msg.value > 0 && to != address(0),
            "SOBYA: INVALID_NATIVE_PATH");
        uint256 beforeOut = ISobyaRouterToken(path[path.length - 1]).balanceOf(to);
        ISobyaWrappedNative(wrappedSoby).deposit{value: msg.value}();
        _safeTransfer(wrappedSoby, _pairFor(path[0], path[1]), msg.value);
        _swapSupportingFeeOnTransferTokens(path, to);
        uint256 received = ISobyaRouterToken(path[path.length - 1]).balanceOf(to) - beforeOut;
        require(received >= amountOutMin, "SOBYA: INSUFFICIENT_OUTPUT_AMOUNT");
    }

    function swapExactTokensForSOBY(
        uint256 amountIn, uint256 amountOutMin, address[] calldata path,
        address to, uint256 deadline
    ) external ensure(deadline) returns (uint256 amountOut) {
        require(path.length >= 2 && path[path.length - 1] == wrappedSoby && to != address(0),
            "SOBYA: INVALID_NATIVE_PATH");
        uint256[] memory amounts = new uint256[](path.length);
        amounts[0] = amountIn;
        for (uint256 i; i < path.length - 1; ++i) {
            (uint256 reserveIn, uint256 reserveOut) = _reserves(path[i], path[i + 1]);
            amounts[i + 1] = getAmountOut(amounts[i], reserveIn, reserveOut);
        }
        amountOut = amounts[amounts.length - 1];
        require(amountOut >= amountOutMin, "SOBYA: INSUFFICIENT_OUTPUT_AMOUNT");
        _safeTransferFrom(path[0], msg.sender, _pairFor(path[0], path[1]), amountIn);
        _swap(amounts, path, address(this));
        ISobyaWrappedNative(wrappedSoby).withdraw(amountOut);
        _safeNativeTransfer(to, amountOut);
    }

    function swapExactTokensForSOBYSupportingFeeOnTransferTokens(
        uint256 amountIn, uint256 amountOutMin, address[] calldata path,
        address to, uint256 deadline
    ) external ensure(deadline) {
        require(path.length >= 2 && path[path.length - 1] == wrappedSoby && to != address(0),
            "SOBYA: INVALID_NATIVE_PATH");
        uint256 beforeWrapped = ISobyaRouterToken(wrappedSoby).balanceOf(address(this));
        _safeTransferFrom(path[0], msg.sender, _pairFor(path[0], path[1]), amountIn);
        _swapSupportingFeeOnTransferTokens(path, address(this));
        uint256 received = ISobyaRouterToken(wrappedSoby).balanceOf(address(this)) - beforeWrapped;
        require(received >= amountOutMin, "SOBYA: INSUFFICIENT_OUTPUT_AMOUNT");
        ISobyaWrappedNative(wrappedSoby).withdraw(received);
        _safeNativeTransfer(to, received);
    }
}
