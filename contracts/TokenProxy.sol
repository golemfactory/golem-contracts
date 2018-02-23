pragma solidity ^0.4.19;

contract TransferableToken {
    function balanceOf(address _addr) public constant returns (uint256);
    function transfer(address _to, uint256 _value) public returns (bool success);
}


/// The Gate is a temporary contract with unique address to allow a token holder
/// (called "User") to transfer token from original Token to the Proxy.
///
/// TODO: Rename to MigrationGate?
contract Gate {
    TransferableToken private TOKEN;
    TokenProxy private PROXY;

    /// Gates are to be created by the TokenProxy.
    function Gate(TransferableToken _token, TokenProxy _proxy) public {
        TOKEN = _token;
        PROXY = _proxy;
    }

    /// After the User transfers some tokens to the address of the Gate,
    /// this function can be executed to close the gate and notify the Proxy
    /// about this.
    function() external {

        // Transfer all Gate's tokens to Proxy address.
        uint256 balance = TOKEN.balanceOf(this);
        assert(TOKEN.transfer(PROXY, balance));

        // Notify the Proxy.
        PROXY.closeGate(balance);

        // Delete data before selfdestruct() to recover more gas.
        delete TOKEN;
        delete PROXY;

        // There should not be any Ether in the Gate balance, so use the "dead"
        // address for selfdestruct().
        selfdestruct(0x000000000000000000000000000000000000dEaD);
    }
}


/// The Proxy for existing tokens implementing a subset of ERC20 interface.
///
/// This contract creates a token Proxy contract to extend the original Token
/// contract interface. The Proxy requires only transfer() and balanceOf()
/// methods from ERC20 to be implemented in the original Token contract.
///
/// All migrated tokens are in Proxy's account on the Token side and distributed
/// among Users on the Proxy side.
///
/// For an user to migrate some amount of ones tokens from Token to Proxy
/// the procedure is as follows.
///
/// 1. Create an individual Gate for migration. The Gate address will be
///    reported with the GateOpened event.
/// 2. Transfer tokens to be migrated to the Gate address.
/// 3. Close the Gate by sending empty transaction to the Gate address.
///
/// In the step 3 the User's tokens are going to be moved from the Gate to
/// the User's balance in the Proxy. The Gate is going to be destroyed so
/// it cannot be used again (the User must create a new Gate). However,
/// the step 2 can be repeated multiple times.
contract TokenProxy {

    TransferableToken public TOKEN;

    uint256 public totalSupply;
    mapping(address => uint256) private balances;

    mapping(address => address) private gates;

    event GateOpened(address indexed gate, address indexed user);
    event GateClosed(address indexed gate, address indexed user, uint256 balance);

    function TokenProxy(TransferableToken _token) public {
        TOKEN = _token;
    }

    /// Create a new migration Gate for the User.
    function openGate() external {
        // Create new Gate.
        address gate = new Gate(TOKEN, this);

        // Remember User - Gate relationship.
        address user = msg.sender;
        gates[gate] = user;

        GateOpened(gate, user);
    }

    /// Notification handler for a Gate to be closed.
    function closeGate(uint256 _migratedBalance) external {
        address gate = msg.sender;
        address user = gates[gate];

        // Make sure the notification comes from an exisiting Gate.
        require(user != 0);

        // Remove the entry about the Gate. Another notification from the same
        // Gate is not possible, but this adds additional protection and
        // recovers some gas.
        delete gates[gate];

        // Handle the information about the amount of migrated tokens.
        // This is a trusted information becase it comes from the Gate.
        totalSupply += _migratedBalance;
        balances[user] += _migratedBalance;

        assert(TOKEN.balanceOf(this) == totalSupply);
    }
}
