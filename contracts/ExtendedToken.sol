// Copyright 2018 Golem Factory
// Licensed under the GNU General Public License v3. See the LICENSE file.

pragma solidity ^0.4.16;

import "./open_zeppelin/StandardToken.sol";
import "./open_zeppelin/ERC20Basic.sol";
import "./ReceivingContract.sol";

contract ExtendedToken is StandardToken {
    event BatchTransfer(address indexed from, address indexed to, uint256 value,
        uint64 closureTime);

    // This function allows batch payments using sent value and
    // sender's balance.
    // Opcode estimation:
    // Cost: 21000 + 2000 + 5000 + (20000 + 5000) * n
    // 2000 - arithmetics
    // 5000 - balance update at the end
    // 20000 - pesimistic case of balance update in the loop
    // 5000 - arithmetics + event in the loop
    function batchTransfer(bytes32[] payments, uint64 closureTime) external {
        require(block.timestamp >= closureTime);

        uint balance = balances[msg.sender];

        for (uint i = 0; i < payments.length; ++i) {
            // A payment contains compressed data:
            // first 96 bits (12 bytes) is a value,
            // following 160 bits (20 bytes) is an address.
            bytes32 payment = payments[i];
            address addr = address(payment);
            uint v = uint(payment) / 2**160;
            require(v <= balance);
            balances[addr] += v;
            balance -= v;
            BatchTransfer(msg.sender, addr, v, closureTime);
        }

        balances[msg.sender] = balance;
    }

    function transferAndCall(address to, uint256 value, bytes data) external {
      // Transfer always returns true so no need to check return value
      transfer(to, value);

      // No need to check whether recipient is a contract, this method is
      // supposed to used only with contract recipients
      ReceivingContract(to).onTokenReceived(msg.sender, value, data);
    }
}
