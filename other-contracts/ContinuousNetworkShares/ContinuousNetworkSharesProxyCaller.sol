pragma solidity ^0.6.6;

import "./ContinuousNetworkShares.sol";
import "./ERC20.sol";


contract ProxyCaller {
    ERC20 gnt;
    ContinuousNetworkShares networkShares;
    constructor(ERC20 _gnt, ContinuousNetworkShares _networkShares) public {
        gnt = _gnt;
        networkShares = _networkShares;
    }
    
    function collect() public {
        networkShares.collect();
    }
    
    function withdraw() public {
        networkShares.withdraw();
    }
    
    function approveAndDeposit(uint256 value) public {
        gnt.approve(address(networkShares), value);
        networkShares.deposit(value);
    }
}
