pragma solidity ^0.4.16;

contract ReceivingContract {
    function onTokenReceived(address _from, uint _value, bytes _data) public;
}
