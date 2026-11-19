// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../src/SobyaV2Factory.sol";
import "../src/SobyaV2Router.sol";
import "../src/SobyaV2Pair.sol";
import "../src/WSOBY.sol";

interface VmDex {
    function warp(uint256) external;
    function deal(address account,uint256 newBalance) external;
}

contract SobyaMockERC20 {
    string public name;
    string public symbol;
    uint8 public constant decimals = 18;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    uint256 public feeBps;
    constructor(string memory n,string memory s) { name=n; symbol=s; }
    function setFeeBps(uint256 bps) external { require(bps <= 1000, "MOCK: FEE_TOO_HIGH"); feeBps = bps; }
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
        balanceOf[from]-=amount;
        uint256 fee = amount * feeBps / 10_000;
        balanceOf[to] += amount - fee;
        totalSupply -= fee;
    }
}

contract SobyaV2Test {
    receive() external payable {}

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
    }

    function _addInitialLiquidity() private {
        router.addLiquidity(address(tokenA),address(tokenB),100 ether,100 ether,100 ether,100 ether,address(this),block.timestamp+1 hours);
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

    function testWrappedNativeSobyCanBeUsedInAnAmmPool() public {
        vm.deal(address(this),20 ether);
        WSOBY wrapped=new WSOBY();
        wrapped.deposit{value:10 ether}();
        SobyaV2Router wrappedRouter=new SobyaV2Router(address(factory),address(wrapped));
        wrapped.approve(address(wrappedRouter),type(uint256).max);
        tokenB.approve(address(wrappedRouter),type(uint256).max);
        wrappedRouter.addLiquidity(address(wrapped),address(tokenB),5 ether,5 ether,5 ether,5 ether,address(this),block.timestamp+1 hours);
        address wrappedPair=factory.getPair(address(wrapped),address(tokenB));
        require(wrappedPair!=address(0),"WSOBY_PAIR_NOT_CREATED");
        address[] memory path=new address[](2);
        path[0]=address(tokenB); path[1]=address(wrapped);
        uint256[] memory amounts=wrappedRouter.swapExactTokensForTokens(1 ether,1,path,address(this),block.timestamp+1 hours);
        require(amounts[1]>0,"WSOBY_SWAP_FAILED");
        require(wrapped.balanceOf(address(this))>5 ether,"WSOBY_NOT_RECEIVED");
    }

    function testMultiHopSwapAcrossTwoPools() public {
        _addInitialLiquidity();
        SobyaMockERC20 tokenC=new SobyaMockERC20("Token C","TKC");
        tokenC.mint(address(this),1_000_000 ether);
        tokenC.approve(address(router),type(uint256).max);
        router.addLiquidity(address(tokenB),address(tokenC),100 ether,100 ether,100 ether,100 ether,address(this),block.timestamp+1 hours);
        address[] memory path=new address[](3);
        path[0]=address(tokenA); path[1]=address(tokenB); path[2]=address(tokenC);
        uint256 beforeC=tokenC.balanceOf(address(this));
        uint256[] memory amounts=router.swapExactTokensForTokens(1 ether,1,path,address(this),block.timestamp+1 hours);
        require(amounts[2]>0&&tokenC.balanceOf(address(this))==beforeC+amounts[2],"MULTIHOP_OUTPUT_NOT_RECEIVED");
    }

    function testFuzzSwapPreservesConstantProduct(uint96 rawAmount) public {
        _addInitialLiquidity();
        address[] memory path=new address[](2);
        path[0]=address(tokenA); path[1]=address(tokenB);
        SobyaV2Pair p=SobyaV2Pair(pair);
        (uint112 r0Before,uint112 r1Before,)=p.getReserves();
        uint256 kBefore=uint256(r0Before)*uint256(r1Before);
        uint256 amountIn=1 ether+(uint256(rawAmount)%1 ether);
        router.swapExactTokensForTokens(amountIn,1,path,address(this),block.timestamp+1 hours);
        (uint112 r0After,uint112 r1After,)=p.getReserves();
        uint256 kAfter=uint256(r0After)*uint256(r1After);
        require(kAfter>=kBefore,"CONSTANT_PRODUCT_DECREASED");
    }

    function testRejectsOneSidedSyncedReserves() public {
        address p=factory.createPair(address(tokenA),address(tokenB));
        tokenA.transfer(p,1 ether);
        SobyaV2Pair(p).sync();
        (bool ok,)=address(router).call(abi.encodeCall(router.addLiquidity,(
            address(tokenA),address(tokenB),10 ether,10 ether,0,0,address(this),block.timestamp+1 hours
        )));
        require(!ok,"ONE_SIDED_POOL_ACCEPTED");
    }

    function testRejectsZeroLiquidityRecipient() public {
        (bool ok,)=address(router).call(abi.encodeCall(router.addLiquidity,(
            address(tokenA),address(tokenB),100 ether,100 ether,100 ether,100 ether,address(0),block.timestamp+1 hours
        )));
        require(!ok,"ZERO_LP_RECIPIENT_ACCEPTED");
    }

    function testPairRejectsZeroAndSelfSwapRecipients() public {
        _addInitialLiquidity();
        SobyaV2Pair p=SobyaV2Pair(pair);
        (bool zeroOk,)=address(p).call(abi.encodeCall(p.swap,(1 ether,0,address(0))));
        require(!zeroOk,"ZERO_SWAP_RECIPIENT_ACCEPTED");
        (bool selfOk,)=address(p).call(abi.encodeCall(p.swap,(1 ether,0,address(p))));
        require(!selfOk,"PAIR_SELF_SWAP_RECIPIENT_ACCEPTED");
    }


    function testFeeOnTransferLiquidityUsesActualReceivedAmounts() public {
        tokenA.setFeeBps(100);
        (uint256 amountA, uint256 amountB,) = router.addLiquidity(
            address(tokenA), address(tokenB), 100 ether, 100 ether,
            99 ether, 100 ether, address(this), block.timestamp + 1 hours
        );
        require(amountA == 99 ether && amountB == 100 ether, "FOT_DEPOSIT_NOT_MEASURED");
    }

    function testFeeOnTransferLiquidityRemovalChecksRecipientNetAmounts() public {
        _addInitialLiquidity();
        SobyaV2Pair p = SobyaV2Pair(pair);
        uint256 lp = p.balanceOf(address(this));
        p.approve(address(router), lp);
        tokenB.setFeeBps(100);
        (uint256 amountA, uint256 amountB) = router.removeLiquiditySupportingFeeOnTransferTokens(
            address(tokenA), address(tokenB), lp, 1, 1, address(this), block.timestamp + 1 hours
        );
        require(amountA > 0 && amountB > 0, "FOT_REMOVE_NO_NET_OUTPUT");
        require(amountB < 100 ether, "FOT_REMOVE_DID_NOT_ACCOUNT_FOR_TAX");
    }

    function testFeeOnTransferSwapUsesActualPairInput() public {
        _addInitialLiquidity();
        tokenA.setFeeBps(100);
        address[] memory path = new address[](2);
        path[0] = address(tokenA);
        path[1] = address(tokenB);
        uint256 beforeB = tokenB.balanceOf(address(this));
        router.swapExactTokensForTokensSupportingFeeOnTransferTokens(
            1 ether, 1, path, address(this), block.timestamp + 1 hours
        );
        require(tokenB.balanceOf(address(this)) > beforeB, "FOT_SWAP_NO_OUTPUT");
    }

    function testNativeSobyLiquidityAndBothSwapDirections() public {
        vm.deal(address(this), 30 ether);
        WSOBY wrapped = new WSOBY();
        SobyaV2Router nativeRouter = new SobyaV2Router(address(factory), address(wrapped));
        tokenB.approve(address(nativeRouter), type(uint256).max);

        nativeRouter.addLiquiditySOBY{value: 5 ether}(
            address(tokenB), 5 ether, 5 ether, 5 ether,
            address(this), block.timestamp + 1 hours
        );

        address[] memory buyPath = new address[](2);
        buyPath[0] = address(wrapped);
        buyPath[1] = address(tokenB);
        uint256 beforeB = tokenB.balanceOf(address(this));
        nativeRouter.swapExactSOBYForTokens{value: 1 ether}(
            1, buyPath, address(this), block.timestamp + 1 hours
        );
        require(tokenB.balanceOf(address(this)) > beforeB, "NATIVE_TO_TOKEN_FAILED");

        address[] memory sellPath = new address[](2);
        sellPath[0] = address(tokenB);
        sellPath[1] = address(wrapped);
        uint256 beforeNative = address(this).balance;
        nativeRouter.swapExactTokensForSOBY(
            1 ether, 1, sellPath, address(this), block.timestamp + 1 hours
        );
        require(address(this).balance > beforeNative, "TOKEN_TO_NATIVE_FAILED");

        address pairAddress = factory.getPair(address(tokenB), address(wrapped));
        SobyaV2Pair p = SobyaV2Pair(pairAddress);
        uint256 lp = p.balanceOf(address(this));
        p.approve(address(nativeRouter), lp);
        uint256 beforeRemove = address(this).balance;
        nativeRouter.removeLiquiditySOBY(
            address(tokenB), lp, 1, 1, address(this), block.timestamp + 1 hours
        );
        require(address(this).balance > beforeRemove, "NATIVE_LIQUIDITY_REMOVE_FAILED");
    }

    function testExpiredDeadlineReverts() public {
        _addInitialLiquidity();
        address[] memory path=new address[](2);
        path[0]=address(tokenA); path[1]=address(tokenB);
        uint256 expiredDeadline=block.timestamp+1 hours;
        vm.warp(expiredDeadline+1);
        (bool ok,)=address(router).call(abi.encodeCall(router.swapExactTokensForTokens,(1 ether,0,path,address(this),expiredDeadline)));
        require(!ok,"EXPIRED_SWAP_ALLOWED");
    }
}
