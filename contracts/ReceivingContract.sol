pragma solidity 0.5.11;

/// Contracts implementing this interface are compatible with
/// GolemNetworkTokenBatching's transferAndCall method
contract ReceivingContract {
    function onTokenReceived(address _from, uint _value, bytes calldata _data) external;
}
