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
    address private USER;

    /// Gates are to be created by the TokenProxy.
    function Gate(TransferableToken _token, TokenProxy _proxy, address _user) public {
        TOKEN = _token;
        PROXY = _proxy;
        USER = _user;
    }

    function transferToProxy() public {
        // Transfer all Gate's tokens to Proxy address.
        uint256 balance = TOKEN.balanceOf(this);
        assert(TOKEN.transfer(PROXY, balance));

        // Notify the Proxy.
        PROXY.onTransferFromGate(balance);
    }

    /// Close the Gate.
    function close() external {
        require(msg.sender == USER);

        // Handle current Gate's balance.
        transferToProxy();

        PROXY.onGateClosed();

        // Delete data before selfdestruct() to recover more gas.
        delete TOKEN;
        delete PROXY;

        // There should not be any Ether in the Gate balance, so use the "dead"
        // address for selfdestruct().
        selfdestruct(0x000000000000000000000000000000000000dEaD);
    }

    function() external {
        // TODO: Check if needed.

        transferToProxy();
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
///    reported with the GateOpened event and accessible by getGateAddress().
/// 2. Transfer tokens to be migrated to the Gate address.
/// 3. Execute Gate.transferToProxy() to finalize the migration.
///
/// In the step 3 the User's tokens are going to be moved from the Gate to
/// the User's balance in the Proxy.
contract TokenProxy {

    TransferableToken public TOKEN;

    uint256 public totalSupply;
    mapping(address => uint256) private balances;

    mapping(address => address) private gates;

    event GateOpened(address indexed gate, address indexed user);
    event GateClosed(address indexed gate, address indexed user);

    // Events taken from ERC777:
    event Minted(address indexed operator, address indexed to, uint256 amount, bytes operatorData);
    event Burned(address indexed operator, address indexed from, uint256 amount, bytes userData, bytes operatorData);


    function TokenProxy(TransferableToken _token) public {
        TOKEN = _token;
    }

    /// Create a new migration Gate for the User.
    function openGate() external {
        address user = msg.sender;

        // Create new Gate.
        address gate = new Gate(TOKEN, this, user);

        // Remember User - Gate relationship.
        gates[gate] = user;

        GateOpened(gate, user);
    }

    function onTransferFromGate(uint256 _value) external {
        address gate = msg.sender;
        address user = gates[gate];

        // Make sure the notification comes from an exisiting Gate.
        require(user != 0);

        // Handle the information about the amount of migrated tokens.
        // This is a trusted information becase it comes from the Gate.
        totalSupply += _value;
        balances[user] += _value;

        // TODO: Transfer event here?
        Minted(this, user, _value, "");
    }

    /// Notification handler for a Gate to be closed.
    function onGateClosed() external {
        address gate = msg.sender;
        address user = gates[gate];

        // Make sure the notification comes from an exisiting Gate.
        require(user != 0);

        // Remove the entry about the Gate. Another notification from the same
        // Gate is not possible, but this adds additional protection and
        // recovers some gas.
        delete gates[gate];

        GateClosed(gate, user);
    }

    function withdraw(uint256 _value) external {
        address user = msg.sender;
        uint256 balance = balances[user];
        require(_value <= balance);

        balances[msg.sender] = (balance - _value);
        totalSupply -= _value;

        TOKEN.transfer(user, _value);

        Burned(this, user, _value, "", "");
    }
}
