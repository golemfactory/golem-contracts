// Copyright 2018 Golem Factory
// Licensed under the GNU General Public License v3. See the LICENSE file.

pragma solidity ^0.4.19;

import "./ExtendedToken.sol";
import "./TokenProxy.sol";

contract GolemNetworkTokenBatching is TokenProxy, ExtendedToken {

    string public constant name = "Golem Network Token Batching";
    string public constant symbol = "GNTB";
    uint8 public constant decimals = 18;

    function GolemNetworkTokenBatching(ERC20Basic _gntToken) TokenProxy(_gntToken) public {
    }
}
