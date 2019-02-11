pragma solidity ^0.5.3;

import "./GolemNetworkTokenBatching.sol";

contract GNTPaymentChannels is ReceivingContract {

    GolemNetworkTokenBatching public token;

    struct PaymentChannel {
        uint256 deposited;
        // withdrawn <= deposited
        uint256 withdrawn;
        //   0, if locked
        // | timestamp, after which withdraw is possible
        uint256 locked_until;
    }

    mapping (bytes32 => PaymentChannel) public channels;
    uint256 close_delay;

    event Fund(address indexed _owner, address indexed _receiver, uint256 amount);
    event Withdraw(address indexed _owner, address indexed _receiver);
    event TimeLocked(address indexed _owner, address indexed _receiver);
    event Close(address indexed _owner, address indexed _receiver);

    constructor(address _token, uint256 _close_delay) public {
        token = GolemNetworkTokenBatching(_token);
        close_delay = _close_delay;
    }

    modifier onlyToken() {
        require(msg.sender == address(token));
        _;
    }

    modifier onlyValidSig(address _owner, address _receiver, uint _value, uint8 _v, bytes32 _r, bytes32 _s) {
        require(isValidSig(_owner, _receiver, _value, _v, _r, _s));
        _;
    }

    // helpers: check channel status

    function getDeposited(address owner, address receiver) external view returns (uint256) {
        return _getChannel(owner, receiver).deposited;
    }

    function getWithdrawn(address owner, address receiver) external view returns (uint256) {
        return _getChannel(owner, receiver).withdrawn;
    }

    function isLocked(address owner, address receiver) public view returns (bool) {
        return _getChannel(owner, receiver).locked_until == 0;
    }

    function isTimeLocked(address owner, address receiver) public view returns (bool) {
        return _getChannel(owner, receiver).locked_until >= block.timestamp;
    }

    function isValidSig(
        address _owner,
        address _receiver,
        uint256 _value,
        uint8 _v,
        bytes32 _r,
        bytes32 _s
    )
        public
        pure
        returns (bool)
    {
        return _owner == ecrecover(keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n72", _owner, _receiver, _value)), _v, _r, _s);
    }

    // functions that modify state

    // Fund existing channel; can be done multiple times.
    function onTokenReceived(address _owner, uint256 _value, bytes calldata _data) external onlyToken {
        require(_data.length == 20);
        bytes memory data = _data;
        address receiver;
        assembly {
          receiver := div(mload(add(data, 0x20)), 0x1000000000000000000000000)
        }
        PaymentChannel storage ch = _getChannel(_owner, receiver);
        ch.deposited += _value;
        emit Fund(_owner, receiver, _value);
    }

    // Receiver can withdraw multiple times without closing the channel
    function withdraw(
        address owner,
        uint256 _value,
        uint8 _v,
        bytes32 _r,
        bytes32 _s
    )
        external
        onlyValidSig(owner, msg.sender, _value, _v, _r, _s)
    {
        address receiver = msg.sender;
        PaymentChannel storage ch = _getChannel(owner, receiver);
        require(ch.withdrawn < _value);
        uint256 amount = _value - ch.withdrawn;
        // Receiver has been cheated! Withdraw as much as possible.
        if (ch.deposited - ch.withdrawn < amount) {
            amount = ch.deposited - ch.withdrawn;
        }

        ch.withdrawn += amount;
        require(token.transfer(receiver, amount));
        emit Withdraw(owner, receiver);
    }

    // If receiver does not want to close channel, owner can do that
    // by calling unlock and waiting for grace period (close_delay).
    function unlock(address receiver) external {
        address owner = msg.sender;
        PaymentChannel storage ch = _getChannel(owner, receiver);
        ch.locked_until = block.timestamp + close_delay;
        emit TimeLocked(owner, receiver);
    }

    // Owner can close channel to reclaim all their remaining money.
    // It doesn't actually deletes the struct from the storage, but it
    // invalidates all existing (up to the current amount) signed messages.
    function close(address receiver) external {
        address owner = msg.sender;
        PaymentChannel storage ch = _getChannel(owner, receiver);
        require(ch.locked_until != 0 && ch.locked_until < now);

        uint256 amount = ch.deposited - ch.withdrawn;
        ch.withdrawn = ch.deposited;
        require(token.transfer(owner, amount));
        emit Close(owner, receiver);
    }

    // internals

    function _getChannel(
        address owner,
        address receiver
    )
        private
        view
        returns (PaymentChannel storage)
    {
        return channels[keccak256(abi.encodePacked(owner, receiver))];
    }
}
