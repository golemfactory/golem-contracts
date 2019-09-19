const truffleAssert = require('truffle-assertions');
const web3 = require("web3");
const BN = require('bn.js');

const setup = require('./setup')
const GNTBounty = artifacts.require("GNTBounty");


contract("GNTBounty", async accounts_ => {
  // accounts_ are shared across all tests (even from different files)
  let accounts = accounts_.slice();
  let golemfactory = accounts.pop();
  let gnt;
  let faucet;

  let secrets;
  let hashes;
  let bounties;
  let addr;
  let gntbounty;

  beforeEach("setup", async () => {
    [gnt, faucet] = await setup.deployGntAndFaucet(golemfactory);
    await faucet.create({from: golemfactory});
    secrets = ["asd", "qwe", "klopsiki"];
    hashes = [];
    for (var i in secrets) {
      hashes.push(web3.utils.soliditySha3({type: 'string', value: secrets[i]}));
    }
    bounties = [new BN(1), new BN(2), new BN(3)];
    addr = accounts[0];
    gntbounty = await GNTBounty.new(gnt.address, hashes, bounties, addr);

    let totalBounty = new BN();
    for (var i in bounties) {
      totalBounty.iadd(bounties[i]);
    }
    await gnt.transfer(gntbounty.address, totalBounty, {from: golemfactory});
  });

  it("gnt transfer after claim", async () => {
    let balance = new BN(0);
    for (var i in bounties) {
      await gntbounty.claim(secrets[i], addr, {from: addr});
      balance.iadd(bounties[i]);
      assert.isTrue(balance.eq(await gnt.balanceOf(addr)));
    }
  });

  it("reused secret", async () => {
    await gntbounty.claim(secrets[0], addr, {from: addr});
    await truffleAssert.reverts(gntbounty.claim(secrets[0], addr, {from: addr}), "Invalid or already used secret");
  });

  it("invalid claimer", async () => {
    let claimer = accounts[1];
    await truffleAssert.reverts(gntbounty.claim(secrets[0], claimer, {from: claimer}), "Unauthorized sender");
  });

  it("same claimer, different secrets", async () => {
    await gntbounty.claim(secrets[0], addr, {from: addr});
    await gntbounty.claim(secrets[1], addr, {from: addr});
  });

});
