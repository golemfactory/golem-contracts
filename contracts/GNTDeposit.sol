pragma solidity ^0.4.13;

import "./GolemNetworkTokenWrapped.sol";

contract GNTDeposit {
    string public ensaddress;
    address public oracle;
    GolemNetworkTokenWrapped public token;
    // owner => amount
    mapping (address => uint256) public balances;
    // owner => block_number
    mapping (address =>  uint256) public locked_until;

    event Deposit(address indexed _from, uint256 _amount, uint256 until);
    event Withdraw(address indexed _from, address indexed _to, uint256 _amount);
    event Burn(address indexed _who, uint256 _amount);
    event Reimburse(address indexed _owner, address _payee, uint256 _amount);

    function GNTDeposit(address _token,
                        address _oracle,
                        string _ensaddress) {
        token = GolemNetworkTokenWrapped(_token);
        oracle = _oracle;
        ensaddress = _ensaddress;
    }

    function balanceOf(address _owner) external constant returns (uint256) {
        return balances[_owner];
    }

    function lockBlock(address _owner) external constant returns (uint256) {
        return locked_until[_owner];
    }

    // _locked_until must grow
    function deposit(uint256 _amount, uint256 _locked_until)
        external returns (bool) {
        if (_locked_until < locked_until[msg.sender])
            return false;
        if (token.transferFrom(msg.sender, address(this), _amount)) {
            balances[msg.sender] += _amount;
            locked_until[msg.sender] = _locked_until;
            Deposit(msg.sender, _amount, _locked_until); // event
            return true;
        }
        return false;
    }

    function withdraw(address _to)
        external returns (bool) {
        if (block.number < locked_until[msg.sender])
            return false;
        var _amount = balances[msg.sender];
        if (token.transfer(_to, balances[msg.sender])) {
            balances[msg.sender] = 0;
            Withdraw(msg.sender, _to, _amount); // event
            return true;
        }
        return false;
    }

    function burn(address _whom, uint256 _burn)
        external returns (bool) {
        if (msg.sender != oracle)
            revert();
        if (balances[_whom] < _burn)
            revert();
        if (token.transfer(0xdeadbeef, _burn)) {
            balances[_whom] -= _burn;
            Burn(_whom, _burn); // event
            return true;
        }
        return false;
    }

    function reimburse(address _owner, address _payee, uint256 _reimbursement)
        external returns (bool) {
        if (msg.sender != oracle)
            revert();
        if (balances[_owner] < _reimbursement)
            revert();
        if (token.transfer(_payee, _reimbursement)) {
            balances[_owner] -= _reimbursement;
            Reimburse(_owner, _payee, _reimbursement); // event
            return true;
        }
        return false;
    }
}
