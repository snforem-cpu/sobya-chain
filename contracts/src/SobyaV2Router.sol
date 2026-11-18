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
    function transferFrom(address, address, uint256) external returns (bool);
}

contract SobyaV2Router {
    address public immutable factory;
    address public immutable wrappedSoby;
    modifier ensure(uint256 deadline) { require(deadline >= block.timestamp, "SOBYA: EXPIRED"); _; }

    constructor(address factory_, address wrappedSoby_) {
        require(factory_ != address(0) && wrappedSoby_ != address(0), "SOBYA: ZERO_ADDRESS");
        factory = factory_;
        wrappedSoby = wrappedSoby_;
    }

    function _safeTransferFrom(address token, address from, address to, uint256 value) private {
        (bool ok, bytes memory data) = token.call(abi.encodeWithSelector(ISobyaRouterToken.transferFrom.selector, from, to, value));
        require(ok && (data.length == 0 || abi.decode(data, (bool))), "SOBYA: TRANSFER_FROM_FAILED");
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

    function _reserves(address a, address b) private view returns (uint256 reserveA, uint256 reserveB) {
        address pair = _pairFor(a, b);
        (uint112 r0, uint112 r1,) = ISobyaRouterPair(pair).getReserves();
        (reserveA, reserveB) = _sort(a,b) ? (r0,r1) : (r1,r0);
    }

    function quote(uint256 amountA, uint256 reserveA, uint256 reserveB) public pure returns (uint256 amountB) {
        require(amountA > 0, "SOBYA: INSUFFICIENT_AMOUNT");
        require(reserveA > 0 && reserveB > 0, "SOBYA: INSUFFICIENT_LIQUIDITY");
        amountB = amountA * reserveB / reserveA;
    }

    function getAmountOut(uint256 amountIn, uint256 reserveIn, uint256 reserveOut) public pure returns (uint256 amountOut) {
        require(amountIn > 0, "SOBYA: INSUFFICIENT_INPUT");
        require(reserveIn > 0 && reserveOut > 0, "SOBYA: INSUFFICIENT_LIQUIDITY");
        uint256 amountInWithFee = amountIn * 997;
        amountOut = amountInWithFee * reserveOut / (reserveIn * 1000 + amountInWithFee);
    }

    function getAmountIn(uint256 amountOut, uint256 reserveIn, uint256 reserveOut) public pure returns (uint256 amountIn) {
        require(amountOut > 0 && reserveIn > 0 && reserveOut > amountOut, "SOBYA: INSUFFICIENT_LIQUIDITY");
        amountIn = reserveIn * amountOut * 1000 / ((reserveOut - amountOut) * 997) + 1;
    }

    function addLiquidity(address a, address b, uint256 desiredA, uint256 desiredB, uint256 minA, uint256 minB, address to, uint256 deadline)
        external ensure(deadline) returns (uint256 amountA, uint256 amountB, uint256 liquidity)
    {
        require(a != b && a != address(0) && b != address(0), "SOBYA: INVALID_TOKENS");
        address pair = ISobyaRouterFactory(factory).getPair(a,b);
        if (pair == address(0)) pair = ISobyaRouterFactory(factory).createPair(a,b);
        (uint256 reserveA, uint256 reserveB) = _reservesForExisting(a,b,pair);
        if (reserveA == 0 && reserveB == 0) { (amountA, amountB) = (desiredA, desiredB); }
        else {
            uint256 optimalB = quote(desiredA, reserveA, reserveB);
            if (optimalB <= desiredB) { require(optimalB >= minB, "SOBYA: INSUFFICIENT_B_AMOUNT"); (amountA, amountB) = (desiredA, optimalB); }
            else { uint256 optimalA = quote(desiredB, reserveB, reserveA); require(optimalA <= desiredA && optimalA >= minA, "SOBYA: INSUFFICIENT_A_AMOUNT"); (amountA, amountB) = (optimalA, desiredB); }
        }
        require(amountA >= minA && amountB >= minB, "SOBYA: SLIPPAGE");
        _safeTransferFrom(a,msg.sender,pair,amountA);
        _safeTransferFrom(b,msg.sender,pair,amountB);
        liquidity = ISobyaRouterPair(pair).mint(to);
    }

    function _reservesForExisting(address a,address b,address pair) private view returns(uint256 reserveA,uint256 reserveB) {
        (uint112 r0,uint112 r1,) = ISobyaRouterPair(pair).getReserves();
        (reserveA,reserveB) = _sort(a,b) ? (r0,r1) : (r1,r0);
    }

    function removeLiquidity(address a,address b,uint256 liquidity,uint256 minA,uint256 minB,address to,uint256 deadline)
        external ensure(deadline) returns(uint256 amountA,uint256 amountB)
    {
        address pair = _pairFor(a,b);
        require(ISobyaRouterPair(pair).transferFrom(msg.sender,pair,liquidity), "SOBYA: LP_TRANSFER_FAILED");
        (uint256 amount0,uint256 amount1) = ISobyaRouterPair(pair).burn(to);
        (amountA,amountB) = _sort(a,b) ? (amount0,amount1) : (amount1,amount0);
        require(amountA >= minA && amountB >= minB, "SOBYA: SLIPPAGE");
    }

    function swapExactTokensForTokens(uint256 amountIn,uint256 amountOutMin,address[] calldata path,address to,uint256 deadline)
        external ensure(deadline) returns(uint256[] memory amounts)
    {
        require(path.length >= 2, "SOBYA: INVALID_PATH");
        amounts = new uint256[](path.length);
        amounts[0] = amountIn;
        for(uint256 i=0;i<path.length-1;i++) {
            (uint256 reserveIn,uint256 reserveOut) = _reserves(path[i],path[i+1]);
            amounts[i+1] = getAmountOut(amounts[i],reserveIn,reserveOut);
        }
        require(amounts[amounts.length-1] >= amountOutMin, "SOBYA: INSUFFICIENT_OUTPUT_AMOUNT");
        _safeTransferFrom(path[0],msg.sender,_pairFor(path[0],path[1]),amounts[0]);
        for(uint256 i=0;i<path.length-1;i++) {
            (address input,address output) = (path[i],path[i+1]);
            address pair = _pairFor(input,output);
            address nextTo = i < path.length-2 ? _pairFor(output,path[i+2]) : to;
            bool inputIs0 = input < output;
            uint256 out = amounts[i+1];
            ISobyaRouterPair(pair).swap(inputIs0 ? 0 : out,inputIs0 ? out : 0,nextTo);
        }
    }
}
