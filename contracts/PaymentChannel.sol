pragma solidity ^0.4.16;

import "./GolemNetworkTokenWrapped.sol";

contract GNTPaymentChannels {

    GolemNetworkTokenWrapped public token;

    struct PaymentChannel {
        address owner;
        address receiver;
        uint256 deposited;
        // withdrawn <= deposited
        uint256 withdrawn;
        // 0 if locked
        // | timestamp after which withdraw is possible
        uint256 locked_until;
    }

    uint256 id;
    mapping (bytes32 => PaymentChannel) public channels;
    uint256 close_delay;

    event NewChannel(address indexed _owner, address indexed _receiver, bytes32 _channel);
    event Fund(address indexed _owner, address indexed _receiver, bytes32 _channel);
    event Withdraw(address indexed _owner, address indexed _receiver);
    event Unlock(address indexed _owner, address indexed _receiver, bytes32 _channel);
    event Close(address indexed _owner, address indexed _receiver, bytes32 _channel);
    event ForceClose(address indexed _owner, address indexed _receiver, bytes32 _channel);

    function GNTPaymentChannels(address _token, uint256 _close_delay)
        public {
        token = GolemNetworkTokenWrapped(_token);
        id = 0;
        close_delay = _close_delay;
    }

    function createChannel(address _receiver)
        external {
        bytes32 channel = sha3(id++);
        channels[channel] = PaymentChannel(msg.sender, _receiver, 0, 0, 0);
        NewChannel(msg.sender, _receiver, channel); // event
    }

    function getHash(bytes32 _channel, uint _value) view returns(bytes32) {
        return sha3(_channel, _value);
    }

    modifier validSig(bytes32 _ch, uint _value,
                      uint8 _v, bytes32 _r, bytes32 _s) {
        require((channels[_ch].owner) == ecrecover(getHash(_ch, _value), _v, _r, _s));
        _;
    }

    modifier onlyOwner(bytes32 _channel) {
        require(msg.sender == channels[_channel].owner);
        _;
    }

    modifier unlocked(bytes32 _channel) {
        require(channels[_channel].locked_until > 0);
        require(block.timestamp > channels[_channel].locked_until);
        _;
    }

    // helpers: check channel status

    function getDeposited(bytes32 _channel)
        external
        view
        returns (uint256) {
        PaymentChannel ch = channels[_channel];
        return ch.deposited;
    }

    function getOwner(bytes32 _channel)
        external
        view
        returns (address) {
        return channels[_channel].owner;
    }

    function getReceiver(bytes32 _channel)
        external
        view
        returns (address) {
        return channels[_channel].receiver;
    }

    function getWithdrawn(bytes32 _channel)
        external
        view
        returns (uint256) {
        return channels[_channel].withdrawn;
    }

    function isLocked(bytes32 _channel) external view returns (bool) {
        return channels[_channel].locked_until == 0;
    }

    function isTimeLocked(bytes32 _channel) external view returns (bool) {
        return channels[_channel].locked_until > block.timestamp;
    }

    function isUnlocked(bytes32 _channel) external view returns (bool) {
        return ((channels[_channel].locked_until != 0) &&
                (channels[_channel].locked_until < block.timestamp));
    }

    // Fund existing channel; can be done multiple times.
    function fund(bytes32 _channel, address _receiver, uint256 _amount)
        external
        returns (bool) {
        PaymentChannel ch = channels[_channel];
        // check if channel exists
        // this prevents fund loss
        require(ch.receiver == _receiver);
        if (token.transferFrom(msg.sender, address(this), _amount)) {
            ch.deposited += _amount;
            ch.locked_until = 0;
            // todo drop ch.owner and add amount
            Fund(ch.owner, ch.receiver, _channel); // event
            return true;
        }
        return false;
    }

    // Receiver can withdraw multiple times.
    function withdraw(bytes32 _channel, uint256 _value,
                      uint8 _v, bytes32 _r, bytes32 _s)
        external
        validSig(_channel, _value, _v, _r, _s)
        returns (bool) {
        PaymentChannel ch = channels[_channel];
        require(ch.withdrawn < _value); // <- STRICT less than!
        var amount = _value - ch.withdrawn;
        if (amount < ch.deposited - ch.withdrawn)
            amount = ch.deposited - ch.withdrawn;
        return _do_withdraw(_channel, amount);
    }

    function _do_withdraw(bytes32 _channel, uint256 _amount)
        private
        returns (bool) {
        PaymentChannel ch = channels[_channel];
        if (token.transfer(ch.receiver, _amount)) {
            ch.withdrawn += _amount;
            Withdraw(ch.owner, ch.receiver);
            return true;
        }
        return false;
    }

    // If receiver does not want to close channel, owner can do that
    // after grace period (close_delay).
    function unlock(bytes32 _channel)
        external
        onlyOwner(_channel) {
        PaymentChannel ch = channels[_channel];
        ch.locked_until = block.timestamp + close_delay;
        Unlock(ch.owner, ch.receiver, _channel);
    }

    // Owner can close channel to reclaim its money.
    function close(bytes32 _channel)
        external
        onlyOwner(_channel)
        unlocked(_channel)
        returns (bool) {
        return _do_close(_channel, false);
    }

    // Receiver can close channel and return owner its money.
    // Receiver should `withdraw` its own funds first!
    function forceClose(bytes32 _channel)
        external
        returns (bool) {
        require(msg.sender == channels[_channel].receiver);
        return _do_close(_channel, true);
    }

    function _do_close(bytes32 _channel, bool force) private returns (bool) {
        PaymentChannel ch = channels[_channel];
        var amount = ch.deposited - ch.withdrawn;
        if (token.transfer(ch.owner, amount)) {
            if (force)
                { ForceClose(ch.owner, ch.receiver, _channel); }
            else
                { Close(ch.owner, ch.receiver, _channel); }
            delete channels[_channel];
            return true;
        }
        return false;
    }
}
