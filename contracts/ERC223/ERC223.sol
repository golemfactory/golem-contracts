pragma solidity ^0.4.16;

contract ERC223 {
    function transfer(address to, uint256 amount, bytes data) returns (bool);
    event Transfer(address indexed from, address indexed to, uint256 value, bytes data);
}
