// Copyright 2018 Golem Factory
// Licensed under the GNU General Public License v3. See the LICENSE file.

pragma solidity ^0.5.3;

import "./ReceivingContract.sol";
import "./TokenProxy.sol";
import "@openzeppelin/contracts/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/ownership/Ownable.sol";


/// GolemNetworkTokenBatching can be treated as an upgraded GolemNetworkToken.
/// 1. It is fully ERC20 compliant (GNT is missing approve and transferFrom)
/// 2. It implements slightly modified ERC677 (transferAndCall method)
/// 3. It provides batchTransfer method - an optimized way of executing multiple transfers
///
/// On how to convert between GNT and GNTB see TokenProxy documentation.
contract GolemNetworkTokenBatching is TokenProxy, Ownable {
    using ECDSA for bytes32;

    string public constant name = "Golem Network Token Batching";
    string public constant symbol = "GNTBQ";
    uint8 public constant decimals = 18;

    // 1 wei ETH is worth _rate wei GNT
    uint256 private _rate;
    address private _rateProvider;


    event BatchTransfer(address indexed from, address indexed to, uint256 value,
        uint64 closureTime);

    constructor(ERC20 _gntToken) TokenProxy(_gntToken) public {
    }

    modifier onlyRateProvider() {
        require(_msgSender() == _rateProvider);
        _;
    }

    enum GSNBouncerErrorCodes {
        INSUFFICIENT_BALANCE,
        INVALID_SIGNER
    }

    function acceptRelayedCall(
        address relay,
        address from,
        bytes calldata encodedFunction,
        uint256 transactionFee,
        uint256 gasPrice,
        uint256 gasLimit,
        uint256 nonce,
        bytes calldata approvalData,
        uint256 maxPossibleCharge
    ) external view returns (uint256, bytes memory) {
        if (balanceOf(from) < maxPossibleCharge) {
            return _rejectRelayedCall(uint256(GSNBouncerErrorCodes.INSUFFICIENT_BALANCE));
        }

        bytes memory blob = abi.encodePacked(
            relay,
            from,
            encodedFunction,
            transactionFee,
            gasPrice,
            gasLimit,
            nonce, // Prevents replays on RelayHub
            getHubAddr(), // Prevents replays in multiple RelayHubs
            address(this) // Prevents replays in multiple recipients
        );
        if (keccak256(blob).toEthSignedMessageHash().recover(approvalData) != from) {
            return _rejectRelayedCall(uint256(GSNBouncerErrorCodes.INVALID_SIGNER));
        }
        return _approveRelayedCall(abi.encode(from, maxPossibleCharge, transactionFee, gasPrice));
    }

    function _preRelayedCall(bytes memory context) internal returns (bytes32) {
        (address from, uint256 maxPossibleCharge) = abi.decode(context, (address, uint256));

        // The maximum token charge is pre-charged from the user
        _transfer(from, address(this), _ethToGnt(maxPossibleCharge));
    }

    function _postRelayedCall(bytes memory context, bool /* success */, uint actualCharge, bytes32 /* preRetVal */) internal {
      (address from, uint256 maxPossibleCharge, uint256 transactionFee, uint256 gasPrice) =
          abi.decode(context, (address, uint256, uint256, uint256));

      // actualCharge is an _estimated_ charge, which assumes postRelayedCall will use all available gas.
      // This implementation's gas cost can be roughly estimated as 10k gas, for the two SSTORE operations in an
      // ERC20 transfer.
      uint256 overestimation = _computeCharge(POST_RELAYED_CALL_MAX_GAS.sub(10000), gasPrice, transactionFee);
      actualCharge = actualCharge.sub(overestimation);

      // After the relayed call has been executed and the actual charge estimated, the excess pre-charge is returned
      _transfer(address(this), from, _ethToGnt(maxPossibleCharge.sub(actualCharge)));
    }

    function batchTransfer(bytes32[] calldata payments, uint64 closureTime) external {
        require(block.timestamp >= closureTime);

        /* uint balance = balances[msg.sender]; */

        for (uint i = 0; i < payments.length; ++i) {
            // A payment contains compressed data:
            // first 96 bits (12 bytes) is a value,
            // following 160 bits (20 bytes) is an address.
            bytes32 payment = payments[i];
            address addr = address(uint256(payment));
            require(addr != address(0) && addr != _msgSender());
            uint v = uint(payment) / 2**160;
            /* FIXME no access to _balances */
            _transfer(_msgSender(), addr, v);
            /* require(v <= balance); */
            /* balances[addr] += v; */
            /* balance -= v; */
            emit BatchTransfer(_msgSender(), addr, v, closureTime);
        }

        /* balances[msg.sender] = balance; */
    }

    function transferAndCall(address to, uint256 value, bytes calldata data) external {
      // Transfer always returns true so no need to check return value
      transfer(to, value);

      // No need to check whether recipient is a contract, this method is
      // supposed to used only with contract recipients
      ReceivingContract(to).onTokenReceived(_msgSender(), value, data);
    }

    function setRateProvider(address rateProvider) onlyOwner external {
        _rateProvider = rateProvider;
    }

    function setExchangeRate(uint256 rate) onlyRateProvider external {
        _rate = rate;
    }

    function topUp() external payable {}

    function withdrawTokens(address to) onlyOwner external {
        _transfer(address(this), to, balanceOf(address(this)));
    }

    function _ethToGnt(uint256 amount) internal view returns (uint256) {
        return amount.mul(_rate);
    }
}
