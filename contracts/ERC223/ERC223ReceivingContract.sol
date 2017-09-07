pragma solidity ^0.4.16;

 /*
 * Contract that is working with ERC223 tokens
 */

contract ERC223ReceivingContract {
    function onTokenReceived(address _from, uint _value, bytes _data);
}
