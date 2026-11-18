// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./SobyaV2Pair.sol";

contract SobyaV2Factory {
    mapping(address => mapping(address => address)) public getPair;
    address[] public allPairs;
    event PairCreated(address indexed token0, address indexed token1, address pair, uint256 pairCount);

    function allPairsLength() external view returns (uint256) { return allPairs.length; }

    function createPair(address tokenA, address tokenB) external returns (address pair) {
        require(tokenA != tokenB, "SOBYA: IDENTICAL_ADDRESSES");
        (address token0, address token1) = tokenA < tokenB ? (tokenA, tokenB) : (tokenB, tokenA);
        require(token0 != address(0), "SOBYA: ZERO_ADDRESS");
        require(getPair[token0][token1] == address(0), "SOBYA: PAIR_EXISTS");
        pair = address(new SobyaV2Pair());
        SobyaV2Pair(pair).initialize(token0, token1);
        getPair[token0][token1] = pair;
        getPair[token1][token0] = pair;
        allPairs.push(pair);
        emit PairCreated(token0, token1, pair, allPairs.length);
    }
}
