pragma solidity ^0.5.11;

interface GNT {
  function totalSupply() external view returns (uint256);
  function balanceOf(address account) external view returns (uint256);
  function transfer(address recipient, uint256 amount) external returns (bool);
}

contract GNTBounty {
  GNT public _gnt;

  mapping(address => uint256) private _bounties;
  mapping(bytes32 => bool) private _hashes;

  constructor(
    GNT gnt,
    bytes32[] memory hashes,
    uint256[] memory bounties,
    address[] memory addresses
  ) public {
    require(hashes.length == bounties.length);
    require(bounties.length == addresses.length);

    _gnt = gnt;

    for (uint256 i = 0; i < hashes.length; i++) {
      _hashes[hashes[i]] = true;
      _bounties[addresses[i]] = bounties[i];
    }
  }

  function claim(string memory secret, address to) public {
    bytes32 h = hash(secret);
    require(_hashes[h], "Invalid or already used secret");

    uint256 bounty = _bounties[msg.sender];
    require(bounty > 0, "Invalid sender or bounty already claimed");

    _hashes[h] = false;
    _bounties[msg.sender] = 0;
    require(_gnt.transfer(to, bounty), "Failed to transfer GNT");
  }

  function hash(string memory secret) public pure returns (bytes32) {
    return keccak256(abi.encodePacked(secret));
  }

  function check(string memory secret) public view returns (bool) {
    return _hashes[hash(secret)];
  }
}
