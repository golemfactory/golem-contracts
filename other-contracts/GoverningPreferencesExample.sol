pragma solidity ^0.6.6;

contract GoverningPreferencesExample {
    
    struct PreferenceStruct {
        address addr;
        uint256 preference;
    }
    
    mapping(address => uint256) preferenceMapping;
    PreferenceStruct[] preferences;
    uint256 globalParameter;
    
    function getPreference(address _member) public view returns (uint256) {
        return preferences[preferenceMapping[_member]-1].preference;
    }
    function getGlobalParameter() public view returns (uint256) {
        return globalParameter;
    }
    
    // for testing
    function getPreferencesSize() public view returns (uint256) {
        return preferences.length;
    }
    // for testing
    function getPreferenceId(address _member) public view returns (uint256) {
        return preferenceMapping[_member]-1;
    }
    // for testing
    function getPreferenceById(uint256 _id) public view returns (uint256) {
        return preferences[_id].preference;
    }
    // for testing
    function getPreferenceAddrById(uint256 _id) public view returns (address) {
        return preferences[_id].addr;
    }
    
    function setPreference(uint256 _value) public returns (bool) {
        if (preferenceMapping[msg.sender] != 0) {
            preferences[preferenceMapping[msg.sender]-1].preference = _value;
        } else {
            preferences.push(PreferenceStruct(msg.sender, _value));
            preferenceMapping[msg.sender] = preferences.length;
        }
        return true;
    }
    
    function removePreference() public returns (bool) {
        if (preferenceMapping[msg.sender] == 0) {
            return false;
        }
        if (preferenceMapping[msg.sender] < preferences.length-1) {
            preferences[preferenceMapping[msg.sender]] = preferences[preferences.length-1];
            preferenceMapping[preferences[preferences.length-1].addr] = preferenceMapping[msg.sender];
        }
        delete preferenceMapping[msg.sender];
        preferences.pop();
        return true;
    }
    
    function setGlobalParameter(uint256 _value) public returns (bool) {
        if (preferences.length == 0) {
            return false;
        }
        uint256 less = 0;
        uint256 equal = 0;
        uint256 greater = 0;
        for (uint j = 0; j < preferences.length; j++) {
            if (preferences[j].preference < _value) {
                less ++;
            } else if (preferences[j].preference > _value) {
                greater ++;
            } else {
                equal ++;
            }
        }
        if (3*less > preferences.length) {
            return false;
        }
        if (3*greater > preferences.length) {
            return false;
        }
        globalParameter = _value;
        return true;
    }
    
}
