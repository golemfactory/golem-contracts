const truffleAssert = require('truffle-assertions');

const BN = require('bn.js');

const setup = require('./setup');

contract("GolemNetworkTokenBatching", async accounts_ => {
  // accounts_ are shared across all tests (even from different files)
  let accounts = accounts_.slice();
  let golemfactory = accounts.pop();
  let addr = accounts.pop();
  let gnt;
  let faucet;
  let gntb;

  beforeEach("setup", async () => {
    [gnt, faucet] = await setup.deployGntAndFaucet(golemfactory);
    gntb = await setup.deployGntb(gnt.address);

    await setup.createGntb(addr, gnt, gntb, faucet);
  });

  it("convert", async () => {
    let address = accounts[0];
    await faucet.create({from: address});
    let balance = await gnt.balanceOf(address);
    assert.notEqual(0, balance);
    assert.equal(0, await gntb.balanceOf(address));
    await setup.convertGnt(address, balance, gnt, gntb);
    assert.equal(0, await gnt.balanceOf(address));
    assert.isTrue(balance.eq(await gntb.balanceOf(address)));
  });

  it("convert zero fails", async () => {
    let address = accounts[0];
    await faucet.create({from: address});
    await truffleAssert.reverts(setup.convertGnt(address, 0, gnt, gntb));
  });

  it("withdraw", async () => {
    let other = accounts[0];
    let balance = await gntb.balanceOf(addr);
    let amount = 124;
    await gntb.withdrawTo(amount, other, {from: addr});
    assert.equal(balance - amount, await gntb.balanceOf(addr))
    assert.equal(amount, await gnt.balanceOf(other));
  });

  it("withdraw zero fails", async () => {
    let other = accounts[0];
    await truffleAssert.reverts(gntb.withdrawTo(0, other, {from: addr}));
  });

  it("withdraw to zero address fails", async () => {
    let zeroAddr = '0x' + '0'.repeat(40);
    await truffleAssert.reverts(gntb.withdrawTo(124, zeroAddr, {from: addr}));
  });

  it("batch transfer to self fails", async () => {
    let payments = encodePayments([[addr, new BN('65536', 10)]]);
    let closureTime = 321;
    await truffleAssert.reverts(gntb.batchTransfer(payments, closureTime, {from: addr}));
  });

  it("batch transfer to zero fails", async () => {
    let zeroAddr = '0x' + '0'.repeat(40);
    let payments = encodePayments([[zeroAddr, new BN('65536', 10)]]);
    let closureTime = 321;
    await truffleAssert.reverts(gntb.batchTransfer(payments, closureTime, {from: addr}));
  });

  it("batch transfer", async () => {
    let payments = [];
    assert.isAtLeast(accounts.length, 4);
    for (let i = 0; i < 4; i++) {
      assert.equal(0, await gntb.balanceOf(accounts[i]));
      payments.push([accounts[i], new BN('1'.repeat(i+1), 10)]);
    }
    let encoded = encodePayments(payments);
    let closureTime = 321;
    let tx = await gntb.batchTransfer(encoded, closureTime, {from: addr});
    for (let i = 0; i < 4; i++) {
      truffleAssert.eventEmitted(tx, 'BatchTransfer', (ev) => {
        return ev.from == addr &&
          ev.to == payments[i][0] &&
          ev.value.eq(payments[i][1]) &&
          ev.closureTime == closureTime;
      })
      assert.isTrue(payments[i][1].eq(await gntb.balanceOf(payments[i][0])));
    }
  });
});


function encodePayments(payments) {
  let encoded = [];
  for (let i = 0; i < payments.length; i++) {
    let addr = new Buffer(payments[i][0].substring(2), 'hex');
    let amount = payments[i][1].toBuffer('big', 12);
    let glued = Buffer.concat([amount, addr]);
    encoded.push(web3.utils.bytesToHex(glued));
  }
  return encoded;
}
