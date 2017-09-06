pragma solidity ^0.4.16;

contract ERC20Basic {
    mapping (address => uint256) balances;
    uint256 public totalSupply;
    function balanceOf(address who) constant returns (uint256);
    function transfer(address to, uint256 value) returns (bool);
    event Transfer(address indexed from, address indexed to, uint256 value);
}
