pragma solidity ^0.4.16;

import "./GolemNetworkTokenWrapped.sol";
import "./ERC223/ERC223ReceivingContract.sol";

contract GNTDeposit is ERC223ReceivingContract {
    address public oracle;
    address public coldwallet;
    uint256 public withdrawal_delay;

    GolemNetworkTokenWrapped public token;
    // owner => amount
    mapping (address => uint256) public balances;
    // owner => timestamp after which withdraw is possible
    //        | 0 if locked
    mapping (address =>  uint256) public locked_until;

    event Deposit(address indexed _owner, uint256 _amount);
    event Withdraw(address indexed _from, address indexed _to, uint256 _amount);
    event Lock(address indexed _owner);
    event Unlock(address indexed _owner);
    event Burn(address indexed _who, uint256 _amount);
    event ReimburseForSubtask(address indexed _requestor, address _provider, uint256 _amount, bytes32 _subtask_id);
    event ReimburseForNoPayment(address indexed _requestor, address _provider, uint256 _amount, uint256 indexed _closure_time);
    event ReimburseForVerificationCosts(address indexed _from, uint256 _amount, bytes32 _subtask_id);

    function GNTDeposit(address _token,
                        address _oracle,
                        address _coldwallet,
                        uint256 _withdrawal_delay) {
        token = GolemNetworkTokenWrapped(_token);
        oracle = _oracle;
        coldwallet = _coldwallet;
        withdrawal_delay = _withdrawal_delay;
    }

    // modifiers

    modifier onlyUnlocked() {
        require(isUnlocked(msg.sender));
        _;
    }

    modifier onlyOracle() {
        require(msg.sender == oracle);
        _;
    }

    modifier onlyToken() {
        require(msg.sender == address(token));
        _;
    }

    // views

    function balanceOf(address _owner) external view returns (uint256) {
        return balances[_owner];
    }

    function isLocked(address _owner) external view returns (bool) {
        return locked_until[_owner] == 0;
    }

    function isTimeLocked(address _owner) external view returns (bool) {
        return locked_until[_owner] > block.timestamp;
    }

    function isUnlocked(address _owner) public view returns (bool) {
        return ((locked_until[_owner] != 0) &&
                (locked_until[_owner] < block.timestamp));
    }

    function getTimelock(address _owner) external view returns (uint256) {
        return locked_until[_owner];
    }

    // deposit API

    function unlock() external {
        locked_until[msg.sender] = block.timestamp + withdrawal_delay;
        Unlock(msg.sender); // event
    }

    function lock() external {
        locked_until[msg.sender] = 0;
        Lock(msg.sender); // event
    }

    // ERC-223 - below are three proposed names for the same function
    // Send GNT using transfer(this.address, amount, channel)
    // to this contract to deposit GNT.
    function onTokenTransfer(address _from, uint _value, bytes _data)
        onlyToken
    {
        _do_deposit(_from, _value);
    }

    function onTokenReceived(address _from, uint _value, bytes _data)
        onlyToken
    {
        _do_deposit(_from, _value);
    }

    function tokenFallback(address _from, uint _value, bytes _data)
        onlyToken
    {
        _do_deposit(_from, _value);
    }

    // Use onTokenTransfer instead - it allows you to achieve same effect
    // using one transaction instead of two!
    // Deposit GNT, using token's ERC-20 interfaces.
    function deposit(uint256 _amount)
        external
        returns (bool)
    {
        if (token.transferFrom(msg.sender, address(this), _amount)) {
            return _do_deposit(msg.sender, _amount);
        }
        return false;
    }

    function withdraw(address _to)
        onlyUnlocked
        external
    {
        var _amount = balances[msg.sender];
        balances[msg.sender] = 0;
        locked_until[msg.sender] = 0;
        require(token.transfer(_to, _amount));
        Withdraw(msg.sender, _to, _amount);
    }

    function burn(address _whom, uint256 _burn)
        onlyOracle
        external
    {
        _reimburse(_whom, 0xdeadbeef, _burn);
        Burn(_whom, _burn);
    }

    function reimburseForSubtask(address _requestor, address _provider, uint256 _amount, bytes32 _subtask_id)
        onlyOracle
        external
    {
        _reimburse(_requestor, _provider, _amount);
        ReimburseForSubtask(_requestor, _provider, _amount, _subtask_id);
    }

    function reimburseForNoPayment(address _requestor, address _provider, uint256 _amount, uint256 _closure_time)
        onlyOracle
        external
    {
        _reimburse(_requestor, _provider, _amount);
        ReimburseForNoPayment(_requestor, _provider, _amount, _closure_time);
    }

    function reimburseForVerificationCosts(address _from, uint256 _amount, bytes32 _subtask_id)
        onlyOracle
        external
    {
        _reimburse(_from, coldwallet, _amount);
        ReimburseForVerificationCosts(_from, _amount, _subtask_id);
    }
    // internals

    function _do_deposit(address _owner, uint _amount)
        private
        returns (bool)
    {
        balances[_owner] += _amount;
        Deposit(_owner, _amount); // event
        return true;
    }

    function _reimburse(address _from, address _to, uint256 _amount)
        private
    {
        require(balances[_from] >= _amount);
        balances[_from] -= _amount;
        if (balances[_from] == 0) {
            locked_until[_from] = 0;
        }
        require(token.transfer(_to, _amount));
    }

}
