pragma solidity ^0.6.6;

import "./GoverningPreferencesExample.sol";

contract ProxyCaller {
    GoverningPreferencesExample gpe;
    constructor(GoverningPreferencesExample _gpe) public {
        gpe = _gpe;
    }
    
    function setPreference(uint256 _value) public returns (bool) {
        return gpe.setPreference(_value);
    }

    function removePreference() public returns (bool) {
        return gpe.removePreference();
    }
}
