pragma solidity ^0.4.16;

import "./ERC223/ERC223.sol";
import "./ERC223/ERC223ReceivingContract.sol";
import "./ERC20/ERC20Basic.sol";
import "./ERC20/ERC20Extended.sol";

// ERC223 and ERC20 -compliant wrapper token for GNT
// reworked from original GNTW implementation.
// Original GNTW implementation notice:
// // ERC20-compliant wrapper token for GNT
// // adapted from code provided by u/JonnyLatte


// ERC223 is used because it is easier to handle than ERC20
// ERC20 is used because of lack of support of ERC223 from Raiden
contract Token is ERC223, ERC20Extended, ERC20Basic {

    function balanceOf(address _owner) view returns (uint256 balance) {
        return balances[_owner];
    }

    // Function that is called when a user or another contract wants to transfer funds.
    function transfer(address _to, uint _value, bytes _data)
        returns (bool success)
    {
        uint codeLength;

        assembly {
            // Retrieve the size of the code on target address, this needs assembly .
            codeLength := extcodesize(_to)
        }

        var senderBalance = balances[msg.sender];
        if (senderBalance >= _value && _value > 0) {
            senderBalance -= _value;
            balances[msg.sender] = senderBalance;
            balances[_to] += _value;
            if(codeLength>0) {
                ERC223ReceivingContract receiver = ERC223ReceivingContract(_to);
                // onTokenReceived does revert() if anything goes wrong
                receiver.onTokenReceived(msg.sender, _value, _data);
            }
            // FIXME: when ERC223 will stabilize a bit, revisit this:
            Transfer(msg.sender, _to, _value);
            Transfer(msg.sender, _to, _value, _data);
            return true;
        }
        return false;
    }

    // Standard function transfer similar to ERC20 transfer with no _data .
    // Added due to backwards compatibility reasons .
    function transfer(address _to, uint _value)
        returns (bool success)
    {
        bytes empty;
        return transfer(_to, _value, empty);
    }

    function _transferFrom(address _from,
                           address _to,
                           uint256 _amount) internal returns (bool success) {
        if (balances[_from] >= _amount
            && allowed[_from][msg.sender] >= _amount
            && _amount > 0) {

            balances[_to] += _amount;
            balances[_from] -= _amount;
            allowed[_from][msg.sender] -= _amount;
            Transfer(_from, _to, _amount);
            return true;
        } else {
            return false;
        }
    }

    function approve(address _spender, uint256 _amount) returns (bool success) {
        allowed[msg.sender][_spender] = _amount;
        Approval(msg.sender, _spender, _amount);
        return true;
    }

    function allowance(address _owner,
                       address _spender) view returns (uint256 remaining) {
        return allowed[_owner][_spender];
    }
}

contract DepositSlot {
    address public GNT;

    address public wrapper;

    modifier onlyWrapper {
        if (msg.sender != wrapper) revert();
        _;
    }

    function DepositSlot(address _token, address _wrapper) {
        GNT = _token;
        wrapper = _wrapper;
    }

    function collect() onlyWrapper {
        uint amount = ERC20Basic(GNT).balanceOf(this);
        if (amount == 0) revert();

        ERC20Basic(GNT).transfer(wrapper, amount);
    }
}

contract GolemNetworkTokenWrapped is Token {
    string public constant standard = "Token 0.1";
    string public constant name = "Golem Network Token Wrapped";
    string public constant symbol = "GNTW";
    uint8 public constant decimals = 18;     // same as GNT

    /* address public constant GNT = 0xa74476443119A942dE498590Fe1f2454d7D4aC0d; */
    address public GNT;

    mapping (address => address) depositSlots;

    function GolemNetworkTokenWrapped(address _token) {
        GNT = _token;
    }

    function createPersonalDepositAddress() returns (address depositAddress) {
        if (depositSlots[msg.sender] == 0) {
            depositSlots[msg.sender] = new DepositSlot(GNT, this);
        }

        return depositSlots[msg.sender];
    }

    function getPersonalDepositAddress(
                address depositer) view returns (address depositAddress) {
        return depositSlots[depositer];
    }

    function processDeposit() {
        address depositSlot = depositSlots[msg.sender];
        if (depositSlot == 0) revert();

        DepositSlot(depositSlot).collect();

        uint balance = ERC20Basic(GNT).balanceOf(this);
        if (balance <= totalSupply) revert();

        uint freshGNTW = balance - totalSupply;
        totalSupply += freshGNTW;
        balances[msg.sender] += freshGNTW;
        Transfer(address(this), msg.sender, freshGNTW);
    }

    function transfer(address _to,
                      uint256 _amount) returns (bool success) {
        if (_to == address(this)) {
            withdrawGNT(_amount);   // convert back to GNT
            return true;
        } else {
            bytes empty;
            return Token.transfer(_to, _amount, empty);     // standard transfer
        }
    }

    function transfer(address _to,
                      uint256 _amount,
                      bytes _data) returns (bool success) {
        if (_to == address(this)) {
            withdrawGNT(_amount);   // convert back to GNT
            return true;
        } else {
            return Token.transfer(_to, _amount, _data);  // standard transfer
        }
    }

    function transferFrom(address _from,
                          address _to,
                          uint256 _amount) returns (bool success) {
        if (_to == address(this)) revert();        // not supported
        return Token.transferFrom(_from, _to, _amount);
    }


    function withdrawGNT(uint amount) internal {
        if (balances[msg.sender] < amount) revert();

        balances[msg.sender] -= amount;
        totalSupply -= amount;
        Transfer(msg.sender, address(this), amount);

        ERC20Basic(GNT).transfer(msg.sender, amount);
    }
}
