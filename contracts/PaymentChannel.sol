pragma solidity ^0.4.13;

import "./GolemNetworkTokenWrapped.sol";

contract GNTPaymentChannels {

    GolemNetworkTokenWrapped public token;

    struct PaymentChannel {
        bool is_valid;
        address owner;
        address receiver;
        uint256 value;
        uint256 withdrawn;
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

    function GNTPaymentChannels(address _token, uint256 _close_delay)
        public {
        token = GolemNetworkTokenWrapped(_token);
        id = 0;
        close_delay = _close_delay;
    }

    function createChannel(address _receiver)
        external {
        bytes32 channel = sha3(id++);
        var ch = PaymentChannel(true, msg.sender, _receiver, 0, 0, 0);
        channels[channel] = ch;
        NewChannel(msg.sender, _receiver, channel); // event
    }

    function setValid(bytes32 _channel, bool value)
        external {
        channels[_channel].is_valid = value;
    }

    function isValid(bytes32 _channel)
        external
        returns (bool) {
        return channels[_channel].is_valid;
    }

    function getHash(bytes32 _channel, uint _value) constant returns(bytes32) {
        return sha3(_channel, _value);
    }

    modifier validSig(bytes32 _channel, uint _value,
                      uint8 _v, bytes32 _r, bytes32 _s) {
        PaymentChannel ch = channels[_channel];
        require(ch.owner == ecrecover(getHash(_channel, _value), _v, _r, _s));
        _;
    }

    modifier onlyOwner(bytes32 _channel) {
        require(msg.sender == channels[_channel].owner);
        _;
    }

    modifier unlocked(bytes32 _channel) {
        PaymentChannel ch = channels[_channel];
        require(ch.locked_until > 0);
        require(block.timestamp > ch.locked_until);
        _;
    }

    function value(bytes32 _channel)
        external
        returns (uint256) {
        PaymentChannel ch = channels[_channel];
        return ch.value;
    }


    function getOwner(bytes32 _channel)
        external
        returns (address) {
        return channels[_channel].owner;
    }

    function getPayee(bytes32 _channel)
        external
        returns (address) {
        return channels[_channel].receiver;
    }

    function isMine(bytes32 _channel)
        external
        returns (bool) {
        PaymentChannel ch = channels[_channel];
        return ch.owner == msg.sender;
    }

    function fund(bytes32 _channel, uint256 _value)
        external
        returns (bool) {
        PaymentChannel ch = channels[_channel];
        if (token.transferFrom(msg.sender, address(this), _value)) {
            ch.value += _value;
            ch.locked_until = 0;
            ch.is_valid = true;
            Fund(ch.owner, ch.receiver, _channel); // event
            return true;
        }
        return false;
    }


    function withdraw(bytes32 _channel, uint256 _value,
                      uint8 _v, bytes32 _r, bytes32 _s)
        external
        validSig(_channel, _value, _v, _r, _s)
        returns (bool) {
        PaymentChannel ch = channels[_channel];
        require(ch.withdrawn < _value);
        var amount = _value - ch.withdrawn;
        // Receiver was cheated by owner, withdraw as much as possible
        if (ch.value < amount)
            amount = ch.value;
        if (token.transfer(ch.receiver, amount)) {
            ch.withdrawn += amount;
            ch.value -= amount;
            Withdraw(ch.owner, ch.receiver);
            return true;
        }
        return false;
    }


    function unlock(bytes32 _channel)
        external
        /* onlyOwner(_channel) */
        returns (bool) {
        PaymentChannel ch = channels[_channel];
        ch.locked_until = block.timestamp + close_delay;
        Unlock(ch.owner, ch.receiver, _channel);
        return true;
    }

    function close(bytes32 _channel)
        external
        onlyOwner(_channel)
        unlocked(_channel)
        returns (bool) {
        PaymentChannel ch = channels[_channel];
        if (token.transfer(ch.owner, ch.value)) {
            Close(ch.owner, ch.receiver, _channel);
            delete channels[_channel];
            return true;
        }
        return false;
    }

    function forceClose(bytes32 _channel)
        external
        returns (bool) {
        PaymentChannel ch = channels[_channel];
        require(msg.sender == ch.receiver);
        if (token.transfer(ch.owner, ch.value)) {
            Close(ch.owner, ch.receiver, _channel);
            delete channels[_channel];
            return true;
        }
        return false;
    }
}
