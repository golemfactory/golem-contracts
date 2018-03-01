// Copyright 2018 Golem Factory
// Licensed under the GNU General Public License v3. See the LICENSE file.

pragma solidity ^0.4.16;

import "./ExtendedToken.sol";
import "./ReceivingContract.sol";

contract DepositSlot {
    address public GNT;

    address public wrapper;

    modifier onlyWrapper {
        require(msg.sender == wrapper);
        _;
    }

    function DepositSlot(address _token, address _wrapper) {
        GNT = _token;
        wrapper = _wrapper;
    }

    function collect() onlyWrapper {
        uint amount = ERC20Basic(GNT).balanceOf(this);
        require(amount != 0);

        ERC20Basic(GNT).transfer(wrapper, amount);
    }
}

contract GolemNetworkTokenWrapped is ExtendedToken {
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
        require(depositSlot != 0);

        DepositSlot(depositSlot).collect();

        uint balance = ERC20Basic(GNT).balanceOf(this);
        require(balance > totalSupply_);

        uint freshGNTW = balance - totalSupply_;
        totalSupply_ += freshGNTW;
        balances[msg.sender] += freshGNTW;
        Transfer(address(this), msg.sender, freshGNTW);
    }

    function withdrawGNT(uint amount) public {
        require(balances[msg.sender] >= amount);

        balances[msg.sender] -= amount;
        totalSupply_ -= amount;
        Transfer(msg.sender, address(this), amount);

        ERC20Basic(GNT).transfer(msg.sender, amount);
    }
}
