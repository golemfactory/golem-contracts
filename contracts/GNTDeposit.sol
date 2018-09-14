pragma solidity ^0.4.21;

import "./GolemNetworkTokenBatching.sol";
import "./ReceivingContract.sol";

contract GNTDeposit is ReceivingContract {
    address public concent;
    address public coldwallet;
    uint256 public withdrawal_delay;

    GolemNetworkTokenBatching public token;
    // owner => amount
    mapping (address => uint256) public balances;
    // owner => timestamp after which withdraw is possible
    //        | 0 if locked
    mapping (address => uint256) public locked_until;

    event Deposit(address indexed _owner, uint256 _amount);
    event Withdraw(address indexed _from, address indexed _to, uint256 _amount);
    event Lock(address indexed _owner);
    event Unlock(address indexed _owner);
    event Burn(address indexed _who, uint256 _amount);
    event ReimburseForSubtask(address indexed _requestor, address indexed _provider, uint256 _amount, bytes32 _subtask_id);
    event ReimburseForNoPayment(address indexed _requestor, address indexed _provider, uint256 _amount, uint256 _closure_time);
    event ReimburseForVerificationCosts(address indexed _from, uint256 _amount, bytes32 _subtask_id);
    event ReimburseForCommunication(address indexed _from, uint256 _amount);

    function GNTDeposit(
        GolemNetworkTokenBatching _token,
        address _concent,
        address _coldwallet,
        uint256 _withdrawal_delay
    )
        public
    {
        token = _token;
        concent = _concent;
        coldwallet = _coldwallet;
        withdrawal_delay = _withdrawal_delay;
    }

    // modifiers

    modifier onlyUnlocked() {
        require(isUnlocked(msg.sender));
        _;
    }

    modifier onlyConcent() {
        require(msg.sender == concent);
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
        return locked_until[_owner] != 0 && locked_until[_owner] < block.timestamp;
    }

    function getTimelock(address _owner) external view returns (uint256) {
        return locked_until[_owner];
    }

    // deposit API

    function unlock() external {
        locked_until[msg.sender] = block.timestamp + withdrawal_delay;
        emit Unlock(msg.sender);
    }

    function lock() external {
        locked_until[msg.sender] = 0;
        emit Lock(msg.sender);
    }

    function onTokenReceived(address _from, uint _amount, bytes /* _data */) public onlyToken {
        balances[_from] += _amount;
        locked_until[_from] = 0;
        emit Deposit(_from, _amount);
    }

    function withdraw(address _to) onlyUnlocked external {
        uint256 _amount = balances[msg.sender];
        balances[msg.sender] = 0;
        locked_until[msg.sender] = 0;
        require(token.transfer(_to, _amount));
        emit Withdraw(msg.sender, _to, _amount);
    }

    function burn(address _whom, uint256 _amount) onlyConcent external {
        require(balances[_whom] >= _amount);
        balances[_whom] -= _amount;
        if (balances[_whom] == 0) {
            locked_until[_whom] = 0;
        }
        token.burn(_amount);
        emit Burn(_whom, _amount);
    }

    function reimburseForSubtask(
        address _requestor,
        address _provider,
        uint256 _amount,
        bytes32 _subtask_id
    )
        onlyConcent
        external
    {
        _reimburse(_requestor, _provider, _amount);
        emit ReimburseForSubtask(_requestor, _provider, _amount, _subtask_id);
    }

    function reimburseForNoPayment(
        address _requestor,
        address _provider,
        uint256 _amount,
        uint256 _closure_time
    )
        onlyConcent
        external
    {
        _reimburse(_requestor, _provider, _amount);
        emit ReimburseForNoPayment(_requestor, _provider, _amount, _closure_time);
    }

    function reimburseForVerificationCosts(
        address _from,
        uint256 _amount,
        bytes32 _subtask_id
    )
        onlyConcent
        external
    {
        _reimburse(_from, coldwallet, _amount);
        emit ReimburseForVerificationCosts(_from, _amount, _subtask_id);
    }

    function reimburseForCommunication(
        address _from,
        uint256 _amount
    )
        onlyConcent
        external
    {
        _reimburse(_from, coldwallet, _amount);
        emit ReimburseForCommunication(_from, _amount);
    }

    // internals

    function _reimburse(address _from, address _to, uint256 _amount) private {
        require(balances[_from] >= _amount);
        balances[_from] -= _amount;
        if (balances[_from] == 0) {
            locked_until[_from] = 0;
        }
        require(token.transfer(_to, _amount));
    }

}
