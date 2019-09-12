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
  let addresses;
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
    addresses = [accounts[0], accounts[1], accounts[2]];
    gntbounty = await GNTBounty.new(gnt.address, hashes, bounties, addresses);

    let totalBounty = new BN();
    for (var i in bounties) {
      totalBounty.iadd(bounties[i]);
    }
    await gnt.transfer(gntbounty.address, totalBounty, {from: golemfactory});
  });

  it("gnt transfer after claim", async () => {
    for (var i in addresses) {
      let claimer = addresses[i];
      await gntbounty.claim(secrets[i], claimer, {from: claimer});
      assert.isTrue(bounties[i].eq(await gnt.balanceOf(claimer)));
    }
  });

  it("reused secret", async () => {
    let claimer = addresses[0];
    await gntbounty.claim(secrets[0], claimer, {from: claimer});
    await truffleAssert.reverts(gntbounty.claim(secrets[0], claimer, {from: claimer}), "Invalid or already used secret");
    await truffleAssert.reverts(gntbounty.claim(secrets[0], addresses[1], {from: addresses[1]}), "Invalid or already used secret");
  });

  it("invalid claimer", async () => {
    let claimer = accounts[4];
    await truffleAssert.reverts(gntbounty.claim(secrets[0], claimer, {from: claimer}), "Invalid sender or bounty already claimed");
  });

  it("same claimer, different secrets", async () => {
    let claimer = addresses[0];
    await gntbounty.claim(secrets[0], claimer, {from: claimer});
    await truffleAssert.reverts(gntbounty.claim(secrets[1], claimer, {from: claimer}), "Invalid sender or bounty already claimed");
  });

});
