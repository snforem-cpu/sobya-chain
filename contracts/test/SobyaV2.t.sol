// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaV2Factory.sol";
import "../src/SobyaV2Router.sol";
import "../src/SobyaV2Pair.sol";

interface VmDex {
    function warp(uint256) external;
}

contract SobyaMockERC20 {
    string public name;
    string public symbol;
    uint8 public constant decimals = 18;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    constructor(string memory n,string memory s) { name=n; symbol=s; }
    function mint(address to,uint256 amount) external { balanceOf[to]+=amount; totalSupply+=amount; }
    function approve(address spender,uint256 amount) external returns(bool) { allowance[msg.sender][spender]=amount; return true; }
    function transfer(address to,uint256 amount) external returns(bool) { _transfer(msg.sender,to,amount); return true; }
    function transferFrom(address from,address to,uint256 amount) external returns(bool) {
        uint256 allowed=allowance[from][msg.sender];
        if(allowed!=type(uint256).max){require(allowed>=amount,"MOCK: ALLOWANCE"); allowance[from][msg.sender]=allowed-amount;}
        _transfer(from,to,amount); return true;
    }
    function _transfer(address from,address to,uint256 amount) private {
        require(to!=address(0)&&balanceOf[from]>=amount,"MOCK: TRANSFER");
        balanceOf[from]-=amount; balanceOf[to]+=amount;
    }
}

contract SobyaV2Test {
    VmDex private constant vm = VmDex(address(uint160(uint256(keccak256("hevm cheat code")))));
    SobyaV2Factory private factory;
    SobyaV2Router private router;
    SobyaMockERC20 private tokenA;
    SobyaMockERC20 private tokenB;
    address private pair;

    function setUp() public {
        factory=new SobyaV2Factory();
        router=new SobyaV2Router(address(factory),address(0xBEEF));
        tokenA=new SobyaMockERC20("Token A","TKA");
        tokenB=new SobyaMockERC20("Token B","TKB");
        tokenA.mint(address(this),1_000_000 ether);
        tokenB.mint(address(this),1_000_000 ether);
        tokenA.approve(address(router),type(uint256).max);
        tokenB.approve(address(router),type(uint256).max);
        (,,)= (0,0,0);
    }

    function _addInitialLiquidity() private {
        (, , ) = router.addLiquidity(address(tokenA),address(tokenB),100 ether,100 ether,100 ether,100 ether,address(this),block.timestamp+1 hours);
        pair=factory.getPair(address(tokenA),address(tokenB));
        require(pair!=address(0),"PAIR_NOT_CREATED");
    }

    function testCreatePoolAndAddLiquidity() public {
        _addInitialLiquidity();
        SobyaV2Pair p=SobyaV2Pair(pair);
        (uint112 r0,uint112 r1,)=p.getReserves();
        require(r0==100 ether&&r1==100 ether,"BAD_RESERVES");
        require(p.balanceOf(address(this))>0,"LP_NOT_MINTED");
        require(factory.allPairsLength()==1,"BAD_PAIR_COUNT");
    }

    function testSwapExactTokensForTokens() public {
        _addInitialLiquidity();
        address[] memory path=new address[](2);
        path[0]=address(tokenA); path[1]=address(tokenB);
        uint256 beforeB=tokenB.balanceOf(address(this));
        uint256[] memory amounts=router.swapExactTokensForTokens(1 ether,0,path,address(this),block.timestamp+1 hours);
        require(amounts[1]>0&&amounts[1]<1 ether,"BAD_QUOTE");
        require(tokenB.balanceOf(address(this))==beforeB+amounts[1],"OUTPUT_NOT_RECEIVED");
    }

    function testSlippageMinimumReverts() public {
        _addInitialLiquidity();
        address[] memory path=new address[](2);
        path[0]=address(tokenA); path[1]=address(tokenB);
        (bool ok,)=address(router).call(abi.encodeCall(router.swapExactTokensForTokens,(1 ether,2 ether,path,address(this),block.timestamp+1 hours)));
        require(!ok,"SLIPPAGE_NOT_ENFORCED");
    }

    function testRemoveLiquidityReturnsBothAssets() public {
        _addInitialLiquidity();
        SobyaV2Pair p=SobyaV2Pair(pair);
        uint256 lp=p.balanceOf(address(this));
        p.approve(address(router),lp);
        uint256 beforeA=tokenA.balanceOf(address(this));
        uint256 beforeB=tokenB.balanceOf(address(this));
        (uint256 amountA,uint256 amountB)=router.removeLiquidity(address(tokenA),address(tokenB),lp,1,1,address(this),block.timestamp+1 hours);
        require(amountA>0&&amountB>0,"NO_ASSETS_RETURNED");
        require(tokenA.balanceOf(address(this))>beforeA&&tokenB.balanceOf(address(this))>beforeB,"BALANCES_NOT_RESTORED");
    }

    function testExpiredDeadlineReverts() public {
        _addInitialLiquidity();
        address[] memory path=new address[](2);
        path[0]=address(tokenA); path[1]=address(tokenB);
        vm.warp(block.timestamp+2 hours);
        (bool ok,)=address(router).call(abi.encodeCall(router.swapExactTokensForTokens,(1 ether,0,path,address(this),block.timestamp+1 hours)));
        require(!ok,"EXPIRED_SWAP_ALLOWED");
    }
}
