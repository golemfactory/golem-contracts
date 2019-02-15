const truffleAssert = require('truffle-assertions');
const helpers = require('openzeppelin-test-helpers');

const BN = require('bn.js');

const setup = require('./setup');

const withdrawalDelay = 24 * 60 * 60;

contract("GNTDeposit", async accounts_ => {
  // accounts_ are shared across all tests (even from different files)
  let accounts = accounts_.slice();
  let golemfactory = accounts.pop();
  let user = accounts.pop();
  let concent = accounts.pop();
  let other = accounts.pop();
  let gnt;
  let faucet;
  let gntb;
  let gntdeposit;
  let depositBalance;

  beforeEach("setup", async () => {
    [gnt, faucet, gntb, gntdeposit] = await setup.deployAll(
      golemfactory,
      concent,
      withdrawalDelay,
    );
    await setup.createGntb(user, gnt, gntb, faucet);
    depositBalance = await gntb.balanceOf.call(user);
    await gntb.transferAndCall(gntdeposit.address, depositBalance, [], {from: user});
    assert.isTrue(depositBalance.eq(await gntdeposit.balanceOf(user)));
  });

  it("not a token calling onTokenReceived fails", async () => {
    await truffleAssert.reverts(gntdeposit.onTokenReceived(other, 124, [], {from: other}), "Token only method");
  });

  it("withdraw", async () => {
    let balance = await gntdeposit.balanceOf.call(user);
    assert.isFalse(await gntdeposit.isUnlocked.call(user));
    await truffleAssert.reverts(gntdeposit.withdraw(other, {from: user}), "Deposit is not unlocked");

    await gntdeposit.unlock({from: user});
    assert.isFalse(await gntdeposit.isUnlocked.call(user));
    await truffleAssert.reverts(gntdeposit.withdraw(other, {from: user}), "Deposit is not unlocked");

    let lockedUntil = await gntdeposit.getTimelock.call(user);
    await helpers.time.increaseTo(lockedUntil - 1);
    assert.isFalse(await gntdeposit.isUnlocked.call(user));
    await truffleAssert.reverts(gntdeposit.withdraw(other, {from: user}), "Deposit is not unlocked");

    await helpers.time.increase(2);
    assert.isTrue(await gntdeposit.isUnlocked.call(user));
    await gntdeposit.withdraw(other, {from: user});
    assert.equal(0, await gntdeposit.balanceOf.call(user));
  });

  it("reset lock on top up", async () => {
    await gntdeposit.unlock({from: user});
    assert.notEqual(0, await gntdeposit.getTimelock.call(user));

    await setup.createGntb(user, gnt, gntb, faucet);
    let balance = await gntb.balanceOf.call(user);
    await gntb.transferAndCall(gntdeposit.address, balance, [], {from: user});
    assert.equal(0, await gntdeposit.getTimelock.call(user));
  });

  it("burn", async () => {
    let amount = new BN(124);
    // not Concent
    await truffleAssert.reverts(gntdeposit.burn(user, amount, {from: user}), "Concent only method");

    await gntdeposit.burn(user, amount, {from: concent});
    assert.isTrue(depositBalance.sub(amount).eq(await gntdeposit.balanceOf(user)));
  });

  async function reimbursePairImpl(fnName, args, eventName, evFunction) {
    let amount = new BN(124);
    // not Concent
    await truffleAssert.reverts(gntdeposit[fnName](user, other, amount, ...args, {from: other}), "Concent only method");

    let tx = await gntdeposit[fnName](user, other, amount, ...args, {from: concent});
    assert.isTrue(depositBalance.sub(amount).eq(await gntdeposit.balanceOf(user)));
    assert.isTrue(amount.eq(await gntb.balanceOf(other)));
    truffleAssert.eventEmitted(tx, eventName, (ev) => {
      return ev._requestor == user &&
      ev._provider == other &&
      ev._amount.eq(amount) &&
      evFunction(ev);
    });
  }

  it("reimburseForSubtask", async () => {
    let subtaskId = new Array(32);
    subtaskId[0] = 34;
    await reimbursePairImpl('reimburseForSubtask', [subtaskId], 'ReimburseForSubtask', (ev) => {
      return ev._subtask_id == web3.utils.bytesToHex(subtaskId);
    });
  });

  it("reimburseForNoPayment", async () => {
    let closureTime = new BN(44431);
    await reimbursePairImpl('reimburseForNoPayment', [closureTime], 'ReimburseForNoPayment', (ev) => {
      return ev._closure_time.eq(closureTime);
    });
  });

  async function reimburseSingleImpl(fnName, args, eventName, evFunction) {
    let amount = new BN(124);
    // not Concent
    await truffleAssert.reverts(gntdeposit[fnName](user, amount, ...args, {from: other}), "Concent only method");

    let tx = await gntdeposit[fnName](user, amount, ...args, {from: concent});
    assert.isTrue(depositBalance.sub(amount).eq(await gntdeposit.balanceOf(user)));
    assert.isTrue(amount.eq(await gntb.balanceOf(concent)));
    truffleAssert.eventEmitted(tx, eventName, (ev) => {
      return ev._from == user &&
      ev._amount.eq(amount) &&
      evFunction(ev);
    });
  }

  it("reimburseForVerificationCosts", async () => {
    let subtaskId = new Array(32);
    subtaskId[0] = 34;
    await reimburseSingleImpl('reimburseForVerificationCosts', [subtaskId], 'ReimburseForVerificationCosts', (ev) => {
      return ev._subtask_id == web3.utils.bytesToHex(subtaskId);
    });
  });

  it("reimburseForCommunication", async () => {
    await reimburseSingleImpl('reimburseForCommunication', [], 'ReimburseForCommunication', (ev) => {
      return true;
    });
  });

  it("transfer Concent", async () => {
    assert.equal(concent, await gntdeposit.concent.call());
    await truffleAssert.reverts(gntdeposit.transferConcent(user, {from: user}), "Owner only method");
    await truffleAssert.reverts(gntdeposit.transferConcent(user, {from: concent}), "Owner only method");

    await gntdeposit.transferConcent(other, {from: golemfactory});
    assert.equal(other, await gntdeposit.concent.call());
  });

  it("transfer coldwallet", async () => {
    assert.equal(concent, await gntdeposit.coldwallet.call());
    await truffleAssert.reverts(gntdeposit.transferColdwallet(user, {from: user}), "Owner only method");
    await truffleAssert.reverts(gntdeposit.transferColdwallet(user, {from: concent}), "Owner only method");

    await gntdeposit.transferColdwallet(other, {from: golemfactory});
    assert.equal(other, await gntdeposit.coldwallet.call());
  });

  it("deposit limit", async () => {
    assert.equal(0, await gntdeposit.maximum_deposit_amount.call());
    let limit = new BN(1000);
    await truffleAssert.reverts(gntdeposit.setMaximumDepositAmount(limit, {from: other}), "Owner only method");
    await truffleAssert.reverts(gntdeposit.setMaximumDepositAmount(limit, {from: concent}), "Owner only method");
    await gntdeposit.setMaximumDepositAmount(limit, {from: golemfactory});
    assert.isTrue(limit.eq(await gntdeposit.maximum_deposit_amount.call()));

    await setup.createGntb(other, gnt, gntb, faucet);
    await truffleAssert.reverts(gntb.transferAndCall(gntdeposit.address, limit.addn(1), [], {from: other}), "Maximum deposit limit hit");
    await gntb.transferAndCall(gntdeposit.address, limit, [], {from: other});
    await truffleAssert.reverts(gntb.transferAndCall(gntdeposit.address, new BN(1), [], {from: other}), "Maximum deposit limit hit");
  });

  it("total deposit limit", async () => {
    // withdraw existing deposit so that GNTDeposit is empty
    await gntdeposit.unlock({from: user});
    let lockedUntil = await gntdeposit.getTimelock.call(user);
    await helpers.time.increaseTo(lockedUntil + 1);
    await gntdeposit.withdraw(user, {from: user});
    assert.equal(0, await gntb.balanceOf(gntdeposit.address));

    assert.equal(0, await gntdeposit.maximum_deposits_total.call());
    let limit = new BN(1000);
    await truffleAssert.reverts(gntdeposit.setMaximumDepositsTotal(limit, {from: other}), "Owner only method");
    await truffleAssert.reverts(gntdeposit.setMaximumDepositsTotal(limit, {from: concent}), "Owner only method");
    await gntdeposit.setMaximumDepositsTotal(limit, {from: golemfactory});
    assert.isTrue(limit.eq(await gntdeposit.maximum_deposits_total.call()));

    await setup.createGntb(other, gnt, gntb, faucet);
    await gntb.transferAndCall(gntdeposit.address, limit.subn(1), [], {from: user});
    await truffleAssert.reverts(gntb.transferAndCall(gntdeposit.address, new BN(2), [], {from: other}), "Total deposits limit hit");
    await gntb.transferAndCall(gntdeposit.address, new BN(1), [], {from: other});
  });

  it("reimburse limit", async () => {
    assert.equal(0, await gntdeposit.daily_reimbursement_limit.call());
    let limit = new BN(1000);
    await truffleAssert.reverts(gntdeposit.setDailyReimbursementLimit(limit, {from: other}), "Owner only method");
    await truffleAssert.reverts(gntdeposit.setDailyReimbursementLimit(limit, {from: concent}), "Owner only method");
    await gntdeposit.setDailyReimbursementLimit(limit, {from: golemfactory});
    assert.isTrue(limit.eq(await gntdeposit.daily_reimbursement_limit.call()));

    await truffleAssert.reverts(gntdeposit.reimburseForCommunication(user, limit.addn(1), {from: concent}), "Daily reimbursement limit hit");
    await gntdeposit.reimburseForCommunication(user, limit.subn(1), {from: concent});
    await gntdeposit.reimburseForCommunication(user, new BN(1), {from: concent});
    await truffleAssert.reverts(gntdeposit.reimburseForCommunication(user, new BN(1), {from: concent}), "Daily reimbursement limit hit");
    await helpers.time.increase(24 * 60 * 60 + 1);
    await gntdeposit.reimburseForCommunication(user, new BN(1), {from: concent});
  });
});
