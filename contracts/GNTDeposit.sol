pragma solidity ^0.5.3;

import "./open_zeppelin/Ownable.sol";
import "./GolemNetworkTokenBatching.sol";
import "./ReceivingContract.sol";

contract GNTDeposit is ReceivingContract, Ownable {
    address public concent;
    address public coldwallet;

    // Deposit will be locked for this much longer after unlocking and before
    // it's possible to withdraw.
    uint256 public withdrawal_delay;

    // Contract will not accept new deposits if the total amount of tokens it
    // holds would exceed this amount.
    uint256 public maximum_deposits_total;
    // Maximum deposit value per user.
    uint256 public maximum_deposit_amount;

    // Limit amount of tokens Concent can reimburse within a single day.
    uint256 public daily_reimbursement_limit;
    uint256 private current_reimbursement_day;
    uint256 private current_reimbursement_sum;

    GolemNetworkTokenBatching public token;
    // owner => amount
    mapping (address => uint256) public balances;
    // owner => timestamp after which withdraw is possible
    //        | 0 if locked
    mapping (address => uint256) public locked_until;

    event ConcentTransferred(address indexed _previousConcent, address indexed _newConcent);
    event ColdwalletTransferred(address indexed _previousColdwallet, address indexed _newColdwallet);
    event Deposit(address indexed _owner, uint256 _amount);
    event Withdraw(address indexed _from, address indexed _to, uint256 _amount);
    event Lock(address indexed _owner);
    event Unlock(address indexed _owner);
    event Burn(address indexed _who, uint256 _amount);
    event ReimburseForSubtask(address indexed _requestor, address indexed _provider, uint256 _amount, bytes32 _subtask_id);
    event ReimburseForNoPayment(address indexed _requestor, address indexed _provider, uint256 _amount, uint256 _closure_time);
    event ReimburseForVerificationCosts(address indexed _from, uint256 _amount, bytes32 _subtask_id);
    event ReimburseForCommunication(address indexed _from, uint256 _amount);

    constructor(
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
        require(isUnlocked(msg.sender), "Deposit is not unlocked");
        _;
    }

    modifier onlyConcent() {
        require(msg.sender == concent, "Concent only method");
        _;
    }

    modifier onlyToken() {
        require(msg.sender == address(token), "Token only method");
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

    function isDepositPossible(address _owner, uint256 _amount) external view returns (bool) {
        return !_isTotalDepositsLimitHit(_amount) && !_isMaximumDepositLimitHit(_owner, _amount);
    }

    // management

    function transferConcent(address _newConcent) onlyOwner external {
        require(_newConcent != address(0), "New concent address cannot be 0");
        emit ConcentTransferred(concent, _newConcent);
        concent = _newConcent;
    }

    function transferColdwallet(address _newColdwallet) onlyOwner external {
        require(_newColdwallet != address(0), "New coldwallet address cannot be 0");
        emit ColdwalletTransferred(coldwallet, _newColdwallet);
        coldwallet = _newColdwallet;
    }

    function setMaximumDepositsTotal(uint256 _value) onlyOwner external {
        maximum_deposits_total = _value;
    }

    function setMaximumDepositAmount(uint256 _value) onlyOwner external {
        maximum_deposit_amount = _value;
    }

    function setDailyReimbursementLimit(uint256 _value) onlyOwner external {
        daily_reimbursement_limit = _value;
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

    function onTokenReceived(address _from, uint256 _amount, bytes calldata /* _data */) external onlyToken {
        // Pass 0 as the amount since this check happens post transfer, thus
        // amount is already accounted for in the balance
        require(!_isTotalDepositsLimitHit(0), "Total deposits limit hit");
        require(!_isMaximumDepositLimitHit(_from, _amount), "Maximum deposit limit hit");
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
        require(balances[_whom] >= _amount, "Not enough funds to burn");
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
        bytes32 _subtask_id,
        uint8 _v,
        bytes32 _r,
        bytes32 _s,
        uint256 _reimburse_amount
    )
        onlyConcent
        external
    {
        require(_isValidSignature(_requestor, _provider, _amount, _subtask_id, _v, _r, _s), "Invalid signature");
        require(_reimburse_amount <= _amount, "Reimburse amount exceeds allowed");
        _reimburse(_requestor, _provider, _reimburse_amount);
        emit ReimburseForSubtask(_requestor, _provider, _reimburse_amount, _subtask_id);
    }

    function reimburseForNoPayment(
        address _requestor,
        address _provider,
        uint256[] calldata _amount,
        bytes32[] calldata _subtask_id,
        uint8[] calldata _v,
        bytes32[] calldata _r,
        bytes32[] calldata _s,
        uint256 _reimburse_amount,
        uint256 _closure_time
    )
        onlyConcent
        external
    {
        require(_amount.length == _subtask_id.length);
        require(_amount.length == _v.length);
        require(_amount.length == _r.length);
        require(_amount.length == _s.length);
        // Can't merge the following two loops as we exceed the number of veriables on the stack
        // and the compiler gives: CompilerError: Stack too deep, try removing local variables.
        for (uint256 i = 0; i < _amount.length; i++) {
          require(_isValidSignature(_requestor, _provider, _amount[i], _subtask_id[i], _v[i], _r[i], _s[i]), "Invalid signature");
        }
        uint256 total_amount = 0;
        for (uint256 i = 0; i < _amount.length; i++) {
          total_amount += _amount[i];
        }
        require(_reimburse_amount <= total_amount, "Reimburse amount exceeds total");
        _reimburse(_requestor, _provider, _reimburse_amount);
        emit ReimburseForNoPayment(_requestor, _provider, _reimburse_amount, _closure_time);
    }

    function reimburseForVerificationCosts(
        address _from,
        uint256 _amount,
        bytes32 _subtask_id,
        uint8 _v,
        bytes32 _r,
        bytes32 _s,
        uint256 _reimburse_amount
    )
        onlyConcent
        external
    {
        require(_isValidSignature(_from, address(this), _amount, _subtask_id, _v, _r, _s), "Invalid signature");
        require(_reimburse_amount <= _amount, "Reimburse amount exceeds allowed");
        _reimburse(_from, coldwallet, _reimburse_amount);
        emit ReimburseForVerificationCosts(_from, _reimburse_amount, _subtask_id);
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
        require(balances[_from] >= _amount, "Not enough funds to reimburse");
        if (daily_reimbursement_limit != 0) {
            if (current_reimbursement_day != block.timestamp / 1 days) {
                current_reimbursement_day = block.timestamp / 1 days;
                current_reimbursement_sum = 0;
            }
            require(current_reimbursement_sum + _amount <= daily_reimbursement_limit, "Daily reimbursement limit hit");
            current_reimbursement_sum += _amount;
        }
        balances[_from] -= _amount;
        if (balances[_from] == 0) {
            locked_until[_from] = 0;
        }
        require(token.transfer(_to, _amount));
    }

    function _isTotalDepositsLimitHit(uint256 _amount) private view returns (bool) {
        if (maximum_deposits_total == 0) {
            return false;
        }
        // SafeMath is not required here, as these numbers won't exceed token's total supply
        return token.balanceOf(address(this)) + _amount > maximum_deposits_total;
    }

    function _isMaximumDepositLimitHit(address _owner, uint256 _amount) private view returns (bool) {
        if (maximum_deposit_amount == 0) {
            return false;
        }
        // SafeMath is not required here, as these numbers won't exceed token's total supply
        return balances[_owner] + _amount > maximum_deposit_amount;
    }

    function _isValidSignature(
        address _from,
        address _to,
        uint256 _amount,
        bytes32 _subtask_id,
        uint8 _v,
        bytes32 _r,
        bytes32 _s
    ) public pure returns (bool) {
        return _from == ecrecover(keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n104", _from, _to, _amount, _subtask_id)), _v, _r, _s);
    }

}
