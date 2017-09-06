pragma solidity ^0.4.16;

import "./GolemNetworkTokenWrapped.sol";
import "./ERC223/ERC223ReceivingContract.sol";

contract GNTDeposit is ERC223ReceivingContract {
    string public ensaddress;
    address public oracle;
    uint256 public withdrawal_delay;

    GolemNetworkTokenWrapped public token;
    // owner => amount
    mapping (address => uint256) public balances;
    // owner => timestamp after which withdraw is possible
    //        | 0 if locked
    mapping (address =>  uint256) public locked_until;

    event Deposit(address indexed _from, uint256 _amount);
    event Withdraw(address indexed _from, address indexed _to, uint256 _amount);
    event Lock(address indexed _owner);
    event Unlock(address indexed _owner);
    event Burn(address indexed _who, uint256 _amount);
    event Reimburse(address indexed _owner, address _receiver, uint256 _amount);

    function GNTDeposit(address _token,
                        address _oracle,
                        string _ensaddress,
                        uint256 _withdrawal_delay) {
        token = GolemNetworkTokenWrapped(_token);
        oracle = _oracle;
        ensaddress = _ensaddress;
        withdrawal_delay = _withdrawal_delay;
    }

    function tokenFallback(address _from, uint _value, bytes _data) {
    }

    modifier onlyOracle() {
        require(msg.sender == oracle);
        _;
    }

    function balanceOf(address _owner) external view returns (uint256) {
        return balances[_owner];
    }

    function isLocked(address _owner) external view returns (bool) {
        return locked_until[_owner] == 0;
    }

    function isTimeLocked(address _owner) external view returns (bool) {
        return locked_until[_owner] > block.timestamp;
    }

    function isUnlocked(address _owner) external view returns (bool) {
        return ((locked_until[_owner] != 0) &&
                (locked_until[_owner] < block.timestamp));
    }

    function getTimelock(address _owner) external view returns (uint256) {
        return locked_until[_owner];
    }

    modifier onlyUnlocked() {
        require((locked_until[msg.sender] != 0) &&
                (locked_until[msg.sender] < block.timestamp));
        _;
    }

    function deposit(uint256 _amount)
        external returns (bool) {
        if (token.transferFrom(msg.sender, address(this), _amount)) {
            balances[msg.sender] += _amount;
            locked_until[msg.sender] = 0;
            Deposit(msg.sender, _amount); // event
            return true;
        }
        return false;
    }

    function unlock() external {
        locked_until[msg.sender] = block.timestamp + withdrawal_delay;
        Unlock(msg.sender); // event
    }

    function lock() external {
        locked_until[msg.sender] = 0;
        Lock(msg.sender); // event
    }

    function withdraw(address _to)
        onlyUnlocked
        external
    {
        var _amount = balances[msg.sender];
        if (!token.transfer(_to, balances[msg.sender])) {
            revert();
        }
        delete balances[msg.sender];
        delete locked_until[msg.sender];
        Withdraw(msg.sender, _to, _amount); // event
    }

    function burn(address _whom, uint256 _burn)
        onlyOracle
        external
        returns (bool)
        {
        if (balances[_whom] < _burn)
            revert();
        if (token.transfer(0xdeadbeef, _burn)) {
            balances[_whom] -= _burn;
            if (balances[_whom] == 0) {
                delete balances[_whom];
                delete locked_until[_whom];
            }
            Burn(_whom, _burn); // event
            return true;
        }
        return false;
    }

    function reimburse(address _owner, address _receiver, uint256 _reimbursement)
        onlyOracle
        external
        returns (bool)
        {
        if (balances[_owner] < _reimbursement)
            revert();
        if (token.transfer(_receiver, _reimbursement)) {
            balances[_owner] -= _reimbursement;
            if (balances[_owner] == 0) {
                delete balances[_owner];
                delete locked_until[_owner];
            }
            Reimburse(_owner, _receiver, _reimbursement); // event
            return true;
        }
        return false;
    }
}
