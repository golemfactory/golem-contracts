const truffleAssert = require('truffle-assertions');

const setup = require('./setup')

contract("Faucet", async accounts => {
  let golemfactory = accounts.pop();
  let gnt;
  let faucet;

  beforeEach("setup", async () => {
    [gnt, faucet] = await setup.deployGntAndFaucet(golemfactory);
  });

  it("create", async () => {
    let decimals = await gnt.decimals.call();
    let account = accounts[0];
    assert.equal(0, await gnt.balanceOf(account));
    await faucet.create({from: account});
    assert.equal(1000 * 10 ** decimals, await gnt.balanceOf(account));
    await truffleAssert.reverts(faucet.create({from: account}));
  });
});
