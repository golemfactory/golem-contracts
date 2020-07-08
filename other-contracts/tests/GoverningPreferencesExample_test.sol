pragma solidity ^0.6.6;

import "remix_tests.sol"; // this import is automatically injected by Remix.
import "remix_accounts.sol";
import "../GoverningPreferencesExample.sol";
import "../GoverningPreferencesProxyCaller.sol";

contract testSuite {
    
    GoverningPreferencesExample gp;

    function beforeAll() public {
        gp = new GoverningPreferencesExample();
    }
    
    /// #sender: account-0
    function t1() public {
        Assert.equal(gp.getPreferencesSize(), uint256(0), "pre");
        
        Assert.equal(gp.setPreference(uint256(11)), true, "setPreference");
        
        Assert.equal(gp.getPreferencesSize(), uint256(1), "size");
        Assert.equal(gp.getPreference(address(this)), uint256(11), "preference");
        
        Assert.equal(gp.setGlobalParameter(uint256(11)), true, "setGlobalParameter1");
        Assert.equal(gp.setGlobalParameter(uint256(12)), false, "setGlobalParameter2");
        Assert.equal(gp.setGlobalParameter(uint256(10)), false, "setGlobalParameter3");
        Assert.equal(gp.getGlobalParameter(), uint256(11), "getGlobalParameter");
        
        Assert.equal(gp.setPreference(uint256(22)), true, "setPreference");
        
        Assert.equal(gp.getPreferencesSize(), uint256(1), "size2");
        Assert.equal(gp.getPreference(address(this)), uint256(22), "preference2");

        Assert.equal(gp.removePreference(), true, "removePreference");
        Assert.equal(gp.getPreferencesSize(), uint256(0), "size post");
    }
    
    function t2() public {
        ProxyCaller caller1 = new ProxyCaller(gp);
        ProxyCaller caller2 = new ProxyCaller(gp);
        ProxyCaller caller3 = new ProxyCaller(gp);
        
        Assert.equal(caller1.setPreference(uint256(11)), true, "setPreference1");
        Assert.equal(caller2.setPreference(uint256(22)), true, "setPreference2");
        Assert.equal(caller3.setPreference(uint256(33)), true, "setPreference3");
        
        Assert.equal(gp.getPreferencesSize(), uint256(3), "size1");

        Assert.equal(gp.setGlobalParameter(uint256(22)), true, "setGlobalParameter");
        
        Assert.equal(caller1.removePreference(), true, "removePreference1");
        Assert.equal(caller2.removePreference(), true, "removePreference2");
        Assert.equal(caller3.removePreference(), true, "removePreference3");
        Assert.equal(gp.getPreferencesSize(), uint256(0), "size2");
    }

}
