const truffleAssert = require('truffle-assertions');
const helpers = require('openzeppelin-test-helpers');

const BN = require('bn.js');

const setup = require('./setup');

const GNTPaymentChannels = artifacts.require("GNTPaymentChannels");
const closeDelay = 60 * 60;

contract("GNTPaymentChannels", async accounts_ => {
  // accounts_ are shared across all tests (even from different files)
  let accounts = accounts_.slice();
  let golemfactory = accounts.pop();
  let owner = accounts.pop();
  let receiver = accounts.pop();
  let gnt;
  let faucet;
  let gntb;
  let gntpc;
  let balance = new BN(1000);

  beforeEach("setup", async () => {
    [gnt, faucet] = await setup.deployGntAndFaucet(golemfactory);
    gntb = await setup.deployGntb(gnt.address);
    gntpc = await GNTPaymentChannels.new(gntb.address, closeDelay);

    await setup.createGntb(owner, gnt, gntb, faucet);
    await gntb.transferAndCall(gntpc.address, balance, web3.utils.bytesToHex(new Buffer(receiver.substr(2), 'hex')), {from: owner});
    assert.isTrue(balance.eq(await gntpc.getDeposited(owner, receiver)));
  });

  it("not a token calling onTokenReceived fails", async () => {
    await truffleAssert.reverts(gntpc.onTokenReceived(receiver, 124, [], {from: receiver}));
  });

  it("anreceiver top up", async () => {
    let amount = new BN(200);
    await gntb.transferAndCall(gntpc.address, amount, web3.utils.bytesToHex(new Buffer(receiver.substr(2), 'hex')), {from: owner});
    assert.isTrue(balance.add(amount).eq(await gntpc.getDeposited(owner, receiver)));
  })

  async function signAmount(amount) {
    let amountBytes = amount.toBuffer('big', 32);
    let msg = '0x' + owner.substr(2) + receiver.substr(2) + web3.utils.bytesToHex(amountBytes).substr(2);
    let signature = await web3.eth.sign(msg, owner);
    signature = signature.substr(2);
    let r = '0x' + signature.substr(0, 64);
    let s = '0x' + signature.substr(64, 64);
    let v = (new BN(signature.substr(128, 2), 16)).addn(27);
    assert.isTrue(await gntpc.isValidSig(owner, receiver, amount, v, r, s));
    return [r, s, v];
  }

  it("withdraw", async () => {
    let amount = new BN(124);
    let [r, s, v] = await signAmount(amount);
    await truffleAssert.reverts(gntpc.withdraw(owner, amount.addn(1), v, r, s, {from: receiver}));
    await gntpc.withdraw(owner, amount, v, r, s, {from: receiver});
    await truffleAssert.reverts(gntpc.withdraw(owner, amount.addn(1), v, r, s, {from: receiver}));
    assert.isTrue(amount.eq(await gntb.balanceOf(receiver)));
    assert.isTrue(amount.eq(await gntpc.getWithdrawn(owner, receiver)));

    amount = amount.addn(222);
    [r, s, v] = await signAmount(amount);
    await gntpc.withdraw(owner, amount, v, r, s, {from: receiver});
    assert.isTrue(amount.eq(await gntb.balanceOf(receiver)));
    assert.isTrue(amount.eq(await gntpc.getWithdrawn(owner, receiver)));
  })

  it("close", async () => {
    await truffleAssert.reverts(gntpc.close(receiver, {from: owner}));
    await gntpc.unlock(receiver, {from: owner});
    assert.isTrue(await gntpc.isTimeLocked(owner, receiver));
    await truffleAssert.reverts(gntpc.close(receiver, {from: owner}));

    await helpers.time.increase(closeDelay + 1);
    assert.isFalse(await gntpc.isTimeLocked(owner, receiver));
    let startingBalance = await gntb.balanceOf(owner);
    await gntpc.close(receiver, {from: owner});
    assert.isTrue(startingBalance.add(balance).eq(await gntb.balanceOf(owner)));
    assert.isTrue(balance.eq(await gntpc.getWithdrawn(owner, receiver)));
  });
});
