// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface ISobyaV2ERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address) external view returns (uint256);
    function transfer(address, uint256) external returns (bool);
}

contract SobyaV2Pair {
    string public constant name = "SOBYA V2 LP";
    string public constant symbol = "SOBYA-V2";
    uint8 public constant decimals = 18;
    uint256 public constant MINIMUM_LIQUIDITY = 1000;
    uint256 private constant FEE_DENOMINATOR = 1000;
    uint256 private constant FEE_NUMERATOR = 3;

    address public immutable factory;
    address public token0;
    address public token1;
    uint112 private reserve0;
    uint112 private reserve1;
    uint32 private blockTimestampLast;
    uint256 public price0CumulativeLast;
    uint256 public price1CumulativeLast;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    uint256 private unlocked = 1;

    event Approval(address indexed owner, address indexed spender, uint256 value);
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Mint(address indexed sender, uint256 amount0, uint256 amount1);
    event Burn(address indexed sender, uint256 amount0, uint256 amount1, address indexed to);
    event Swap(address indexed sender, uint256 amount0In, uint256 amount1In, uint256 amount0Out, uint256 amount1Out, address indexed to);
    event Sync(uint112 reserve0, uint112 reserve1);

    modifier lock() {
        require(unlocked == 1, "SOBYA: LOCKED");
        unlocked = 0;
        _;
        unlocked = 1;
    }

    constructor() { factory = msg.sender; }

    function initialize(address a, address b) external {
        require(msg.sender == factory, "SOBYA: FORBIDDEN");
        require(token0 == address(0) && token1 == address(0), "SOBYA: INITIALIZED");
        require(a != address(0) && b != address(0) && a != b, "SOBYA: INVALID_TOKENS");
        (token0, token1) = a < b ? (a, b) : (b, a);
    }

    function getReserves() external view returns (uint112, uint112, uint32) {
        return (reserve0, reserve1, blockTimestampLast);
    }

    /// @notice Returns cumulative prices including the current, not-yet-synced block interval.
    /// @dev Timestamps intentionally wrap at uint32, matching the Uniswap V2 oracle model.
    function currentCumulativePrices() external view returns (
        uint256 price0Cumulative,
        uint256 price1Cumulative,
        uint32 timestamp
    ) {
        timestamp = uint32(block.timestamp);
        price0Cumulative = price0CumulativeLast;
        price1Cumulative = price1CumulativeLast;

        uint32 timeElapsed;
        unchecked { timeElapsed = timestamp - blockTimestampLast; }
        if (timeElapsed > 0 && reserve0 != 0 && reserve1 != 0) {
            unchecked {
                price0Cumulative += ((uint256(reserve1) << 112) / reserve0) * timeElapsed;
                price1Cumulative += ((uint256(reserve0) << 112) / reserve1) * timeElapsed;
            }
        }
    }

    function approve(address spender, uint256 value) external returns (bool) {
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function transfer(address to, uint256 value) external returns (bool) {
        _transfer(msg.sender, to, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        uint256 allowed = allowance[from][msg.sender];
        if (allowed != type(uint256).max) {
            require(allowed >= value, "SOBYA: LP_ALLOWANCE");
            unchecked { allowance[from][msg.sender] = allowed - value; }
            emit Approval(from, msg.sender, allowance[from][msg.sender]);
        }
        _transfer(from, to, value);
        return true;
    }

    function _transfer(address from, address to, uint256 value) private {
        require(to != address(0), "SOBYA: ZERO_TO");
        require(balanceOf[from] >= value, "SOBYA: LP_BALANCE");
        unchecked { balanceOf[from] -= value; }
        balanceOf[to] += value;
        emit Transfer(from, to, value);
    }

    function _mint(address to, uint256 value) private {
        totalSupply += value;
        balanceOf[to] += value;
        emit Transfer(address(0), to, value);
    }

    function _burn(address from, uint256 value) private {
        require(balanceOf[from] >= value, "SOBYA: LP_BALANCE");
        unchecked { balanceOf[from] -= value; totalSupply -= value; }
        emit Transfer(from, address(0), value);
    }

    function _safeTransfer(address token, address to, uint256 value) private {
        (bool success, bytes memory data) = token.call(abi.encodeWithSelector(ISobyaV2ERC20.transfer.selector, to, value));
        require(success && (data.length == 0 || abi.decode(data, (bool))), "SOBYA: TRANSFER_FAILED");
    }

    function _update(uint256 balance0, uint256 balance1) private {
        require(balance0 <= type(uint112).max && balance1 <= type(uint112).max, "SOBYA: RESERVE_OVERFLOW");

        uint32 timestamp = uint32(block.timestamp);
        uint32 timeElapsed;
        unchecked { timeElapsed = timestamp - blockTimestampLast; }

        // Accumulate the previous block's reserve price before changing reserves.
        if (timeElapsed > 0 && reserve0 != 0 && reserve1 != 0) {
            unchecked {
                price0CumulativeLast += ((uint256(reserve1) << 112) / reserve0) * timeElapsed;
                price1CumulativeLast += ((uint256(reserve0) << 112) / reserve1) * timeElapsed;
            }
        }

        reserve0 = uint112(balance0);
        reserve1 = uint112(balance1);
        blockTimestampLast = timestamp;
        emit Sync(reserve0, reserve1);
    }

    function mint(address to) external lock returns (uint256 liquidity) {
        require(to != address(0), "SOBYA: ZERO_TO");
        (uint112 r0, uint112 r1,) = (reserve0, reserve1, blockTimestampLast);
        uint256 b0 = ISobyaV2ERC20(token0).balanceOf(address(this));
        uint256 b1 = ISobyaV2ERC20(token1).balanceOf(address(this));
        uint256 amount0 = b0 - r0;
        uint256 amount1 = b1 - r1;
        if (totalSupply == 0) {
            liquidity = _sqrt(amount0 * amount1) - MINIMUM_LIQUIDITY;
            _mint(address(0xdead), MINIMUM_LIQUIDITY);
        } else {
            liquidity = _min(amount0 * totalSupply / r0, amount1 * totalSupply / r1);
        }
        require(liquidity > 0, "SOBYA: INSUFFICIENT_LIQUIDITY_MINTED");
        _mint(to, liquidity);
        _update(b0, b1);
        emit Mint(msg.sender, amount0, amount1);
    }

    function burn(address to) external lock returns (uint256 amount0, uint256 amount1) {
        require(to != address(0), "SOBYA: ZERO_TO");
        address a = token0;
        address b = token1;
        uint256 liquidity = balanceOf[address(this)];
        uint256 supply = totalSupply;
        amount0 = liquidity * ISobyaV2ERC20(a).balanceOf(address(this)) / supply;
        amount1 = liquidity * ISobyaV2ERC20(b).balanceOf(address(this)) / supply;
        require(amount0 > 0 && amount1 > 0, "SOBYA: INSUFFICIENT_LIQUIDITY_BURNED");
        _burn(address(this), liquidity);
        _safeTransfer(a, to, amount0);
        _safeTransfer(b, to, amount1);
        uint256 b0 = ISobyaV2ERC20(a).balanceOf(address(this));
        uint256 b1 = ISobyaV2ERC20(b).balanceOf(address(this));
        _update(b0, b1);
        emit Burn(msg.sender, amount0, amount1, to);
    }

    function swap(uint256 amount0Out, uint256 amount1Out, address to) external lock {
        require(amount0Out > 0 || amount1Out > 0, "SOBYA: INSUFFICIENT_OUTPUT");
        (uint112 r0, uint112 r1,) = (reserve0, reserve1, blockTimestampLast);
        require(amount0Out < r0 && amount1Out < r1, "SOBYA: INSUFFICIENT_LIQUIDITY");
        require(to != address(0) && to != address(this) && to != token0 && to != token1, "SOBYA: INVALID_TO");
        if (amount0Out > 0) _safeTransfer(token0, to, amount0Out);
        if (amount1Out > 0) _safeTransfer(token1, to, amount1Out);
        uint256 b0 = ISobyaV2ERC20(token0).balanceOf(address(this));
        uint256 b1 = ISobyaV2ERC20(token1).balanceOf(address(this));
        uint256 amount0In = b0 > uint256(r0) - amount0Out ? b0 - (uint256(r0) - amount0Out) : 0;
        uint256 amount1In = b1 > uint256(r1) - amount1Out ? b1 - (uint256(r1) - amount1Out) : 0;
        require(amount0In > 0 || amount1In > 0, "SOBYA: INSUFFICIENT_INPUT");
        uint256 adjusted0 = b0 * FEE_DENOMINATOR - amount0In * FEE_NUMERATOR;
        uint256 adjusted1 = b1 * FEE_DENOMINATOR - amount1In * FEE_NUMERATOR;
        require(adjusted0 * adjusted1 >= uint256(r0) * uint256(r1) * FEE_DENOMINATOR**2, "SOBYA: K");
        _update(b0, b1);
        emit Swap(msg.sender, amount0In, amount1In, amount0Out, amount1Out, to);
    }

    /// @notice Transfers token balances above recorded reserves without changing reserves.
    /// @dev Reverts if a token balance is below its reserve (e.g. unsupported rebasing behavior).
    function skim(address to) external lock {
        require(to != address(0) && to != address(this), "SOBYA: INVALID_TO");
        uint256 balance0 = ISobyaV2ERC20(token0).balanceOf(address(this));
        uint256 balance1 = ISobyaV2ERC20(token1).balanceOf(address(this));
        require(balance0 >= reserve0 && balance1 >= reserve1, "SOBYA: BALANCE_BELOW_RESERVE");
        _safeTransfer(token0, to, balance0 - reserve0);
        _safeTransfer(token1, to, balance1 - reserve1);
    }

    function sync() external lock {
        _update(ISobyaV2ERC20(token0).balanceOf(address(this)), ISobyaV2ERC20(token1).balanceOf(address(this)));
    }

    function _min(uint256 x, uint256 y) private pure returns (uint256) { return x < y ? x : y; }
    function _sqrt(uint256 y) private pure returns (uint256 z) {
        if (y > 3) {
            z = y;
            uint256 x = y / 2 + 1;
            while (x < z) { z = x; x = (y / x + x) / 2; }
        } else if (y != 0) { z = 1; }
    }
}
