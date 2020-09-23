pragma solidity ^0.6.6;

import "remix_tests.sol"; // this import is automatically injected by Remix.
//import "remix_accounts.sol";
import "../ContinuousNetworkShares.sol";
import "../ERC20.sol";
import "../ContinuousNetworkSharesProxyCaller.sol";

// File name has to end with '_test.sol', this file can contain more than one testSuite contracts
contract testSuite {
    
    ERC20 gnt;
    ERC20 dai;
    ContinuousNetworkShares networkShares;

    function beforeAll() public {
        gnt = new ERC20("GNT", "GNT");
        dai = new ERC20("DAI", "DAI");
        networkShares = new ContinuousNetworkShares(gnt, dai);
    }

    function t1() public {
        Assert.equal(networkShares.getTotalStake(), uint256(0), "initial shares");
        Assert.equal(dai.balanceOf(address(networkShares)), uint256(0), "initial dai");
        
        ProxyCaller p1 = new ProxyCaller(gnt, networkShares);
        gnt.mint(address(p1), 10**6*10**18);
        
        Assert.equal(networkShares.getStake(address(p1)), uint256(0), "before deposit");
        Assert.equal(gnt.balanceOf(address(p1)), uint256(10**6*10**18), "balance before deposit");
        p1.approveAndDeposit(10**6*10**18);
        Assert.equal(networkShares.getStake(address(p1)), uint256(10**6*10**18), "after deposit");
        Assert.equal(gnt.balanceOf(address(p1)), uint256(0), "balance after deposit");
        p1.withdraw();
        Assert.equal(networkShares.getStake(address(p1)), uint256(0), "after withdraw");
        Assert.equal(gnt.balanceOf(address(p1)), uint256(10**6*10**18), "balance after withdraw");
    }
    
    function t2() public {
        Assert.equal(networkShares.getTotalStake(), uint256(0), "initial shares");
        Assert.equal(dai.balanceOf(address(networkShares)), uint256(0), "initial dai");

        ProxyCaller p1 = new ProxyCaller(gnt, networkShares);
        gnt.mint(address(p1), 10**6*10**18);
        ProxyCaller p2 = new ProxyCaller(gnt, networkShares);
        gnt.mint(address(p2), 10**6*10**18);
        dai.mint(address(this), 10**6*10**18);
        
        p1.approveAndDeposit(25*10**4*10**18);
        p2.approveAndDeposit(75*10**4*10**18);
        dai.transfer(address(networkShares), 10**3*10**18);
        p1.collect();
        p2.collect();
        
        Assert.equal(dai.balanceOf(address(p1)), uint256(250*10**18), "p1 dividends");
        Assert.equal(dai.balanceOf(address(p2)), uint256(750*10**18), "p2 dividends");

        p1.withdraw();
        p2.withdraw();
    }

    function t3() public {
        Assert.equal(networkShares.getTotalStake(), uint256(0), "initial shares");
        Assert.equal(dai.balanceOf(address(networkShares)), uint256(0), "initial dai");

        ProxyCaller p1 = new ProxyCaller(gnt, networkShares);
        gnt.mint(address(p1), 10**7*10**18);
        ProxyCaller p2 = new ProxyCaller(gnt, networkShares);
        gnt.mint(address(p2), 10**7*10**18);
        ProxyCaller p3 = new ProxyCaller(gnt, networkShares);
        gnt.mint(address(p3), 10**7*10**18);
        dai.mint(address(this), 10**6*10**18);
        
        p1.approveAndDeposit(25*10**4*10**18);
        dai.transfer(address(networkShares), 10**3*10**18);
        p2.approveAndDeposit(75*10**4*10**18);
        dai.transfer(address(networkShares), 2*10**3*10**18);
        p1.withdraw();
        p2.approveAndDeposit(25*10**4*10**18);
        p3.approveAndDeposit(200*10**4*10**18);
        dai.transfer(address(networkShares), 3*10**3*10**18);
        p2.withdraw();
        p3.withdraw();
        
        Assert.equal(dai.balanceOf(address(p1)), uint256(10**3*10**18+500*10**18), "p1 dividends");
        Assert.equal(dai.balanceOf(address(p2)), uint256(1500*10**18+10**3*10**18), "p2 dividends");
        Assert.equal(dai.balanceOf(address(p3)), uint256(2*10**3*10**18), "p3 dividends");
    }

}
