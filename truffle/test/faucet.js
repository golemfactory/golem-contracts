const truffleAssert = require('truffle-assertions');

const GolemNetworkToken = artifacts.require("GolemNetworkToken");
const Faucet = artifacts.require("Faucet");

contract("Faucet", async accounts => {
  let golemfactory;
  let gnt;
  let faucet;
  let decimals;

  beforeEach("setup", async () => {
    golemfactory = accounts.pop();
    let currentBlock = await web3.eth.getBlockNumber();
    gnt = await GolemNetworkToken.new(
      golemfactory,
      golemfactory,
      currentBlock + 2,
      currentBlock + 3,
    );
    decimals = await gnt.decimals.call();

    let tcr = await gnt.tokenCreationRate.call();
    let tcc = await gnt.tokenCreationCap.call();
    let requiredEth = tcc / tcr;
    await gnt.create({from: golemfactory, value: requiredEth});
    await gnt.finalize();

    assert.isFalse(await gnt.funding.call());

    faucet = await Faucet.new(gnt.address);
    await gnt.transfer(faucet.address, tcc, {from: golemfactory});
  });

  it("create", async () => {
    let account = accounts[0];
    assert.equal(0, await gnt.balanceOf(account));
    await faucet.create({from: account});
    assert.equal(1000 * 10 ** decimals, await gnt.balanceOf(account));
    await truffleAssert.reverts(faucet.create({from: account}));
  });
});
