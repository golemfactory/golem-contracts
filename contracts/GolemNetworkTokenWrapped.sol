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
