pragma solidity ^0.5.3;

import "./GolemNetworkToken.sol";

/* Holds all tGNT after simulated crowdfunding on testnet. */
/* To receive some tGNT just call create. */
contract Faucet {
    GolemNetworkToken public token;

    constructor(address _token) public {
        token = GolemNetworkToken(_token);
    }

    // Note that this function does not actually create tGNT!
    // Name was unchanged not to break API
    function create() external {
        uint256 tokens = 1000 * 10 ** uint256(token.decimals());
        if (token.balanceOf(msg.sender) >= tokens) revert();
        token.transfer(msg.sender, tokens);
    }
}
