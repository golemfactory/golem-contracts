pragma solidity ^0.4.16;

import "./GolemNetworkToken.sol";

/* Holds all tGNT after simulated crowdfunding on testnet. */
/* To receive some tGNT just call create. */
contract Faucet {
    address public owner;
    GolemNetworkToken public token;

    function Faucet(address _token, address _owner) {
        owner = _owner;
        token = GolemNetworkToken(_token);
    }

    function create() external {
        var tokens = 1000 * 10 ** token.decimals();
        if (token.balanceOf(msg.sender) >= tokens) revert();
        token.transfer(msg.sender, tokens);
    }
}

