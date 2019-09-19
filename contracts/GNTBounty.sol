pragma solidity ^0.5.11;

interface GNT {
  function totalSupply() external view returns (uint256);
  function balanceOf(address account) external view returns (uint256);
  function transfer(address recipient, uint256 amount) external returns (bool);
}

contract GNTBounty {
  GNT public _gnt;
  address public _addr;

  mapping(bytes32 => uint256) private _bounties;

  constructor(
    GNT gnt,
    bytes32[] memory hashes,
    uint256[] memory bounties,
    address addr
  ) public {
    require(hashes.length == bounties.length);

    _gnt = gnt;
    _addr = addr;

    for (uint256 i = 0; i < hashes.length; i++) {
      _bounties[hashes[i]] = bounties[i];
    }
  }

  function claim(string memory secret, address to) public {
    require(msg.sender == _addr, "Unauthorized sender");
    bytes32 h = hash(secret);
    uint256 bounty = _bounties[h];

    require(bounty > 0, "Invalid or already used secret");

    _bounties[h] = 0;
    require(_gnt.transfer(to, bounty), "Failed to transfer GNT");
  }

  function hash(string memory secret) public pure returns (bytes32) {
    return keccak256(abi.encodePacked(secret));
  }

  function check(string memory secret) public view returns (uint256) {
    return _bounties[hash(secret)];
  }
}
