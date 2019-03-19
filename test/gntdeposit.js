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

  async function signMsg(msg, account) {
      let signature = await web3.eth.sign(msg, account);
      signature = signature.substr(2);
      let r = '0x' + signature.substr(0, 64);
      let s = '0x' + signature.substr(64, 64);
      let v = (new BN(signature.substr(128, 2), 16)).addn(27);
      return [r, s, v];
  }

  async function reimbursePairImpl(fnName, amount, args, eventName, evFunction) {
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
    subtaskId[1] = 34;
    subtaskId = web3.utils.bytesToHex(subtaskId);
    let amount = new BN(124);
    let amountBytes = amount.toBuffer('big', 32)
    let msg = '0x' + user.substr(2) + other.substr(2) + web3.utils.bytesToHex(amountBytes).substr(2) + subtaskId.substr(2);
    let [r, s, v] = await signMsg(msg, user);
    await reimbursePairImpl('reimburseForSubtask', amount, [subtaskId, v, r, s], 'ReimburseForSubtask', (ev) => {
      return ev._subtask_id == subtaskId;
    });
  });

  it("reimburseForNoPayment", async () => {
    let amount1 = new BN(124);
    let amountBytes1 = amount1.toBuffer('big', 32)
    let subtaskId1 = new Array(32);
    subtaskId1[0] = 34;
    subtaskId1 = web3.utils.bytesToHex(subtaskId1);
    let amount2 = new BN(224);
    let amountBytes2 = amount2.toBuffer('big', 32)
    let subtaskId2 = new Array(32);
    subtaskId2[3] = 23;
    subtaskId2 = web3.utils.bytesToHex(subtaskId2);
    let closureTime = new BN(44431);

    let msg1 = '0x' + user.substr(2) + other.substr(2) + web3.utils.bytesToHex(amountBytes1).substr(2) + subtaskId1.substr(2);
    let [r1, s1, v1] = await signMsg(msg1, user);
    let msg2 = '0x' + user.substr(2) + other.substr(2) + web3.utils.bytesToHex(amountBytes2).substr(2) + subtaskId2.substr(2);
    let [r2, s2, v2] = await signMsg(msg2, user);

    // not Concent
    await truffleAssert.reverts(gntdeposit['reimburseForNoPayment'](
      user,
      other,
      [amountBytes1, amountBytes2],
      [subtaskId1, subtaskId2],
      [v1, v2],
      [r1, r2],
      [s1, s2],
      closureTime,
      {from: other},
    ), "Concent only method");

    let tx = await gntdeposit['reimburseForNoPayment'](
      user,
      other,
      [amount1, amount2],
      [subtaskId1, subtaskId2],
      [v1, v2],
      [r1, r2],
      [s1, s2],
      closureTime,
      {from: concent},
    );
    let total_amount = amount1.add(amount2);
    assert.isTrue(depositBalance.sub(total_amount).eq(await gntdeposit.balanceOf(user)));
    assert.isTrue(total_amount.eq(await gntb.balanceOf(other)));
    truffleAssert.eventEmitted(tx, 'ReimburseForNoPayment', (ev) => {
      return ev._requestor == user &&
      ev._provider == other &&
      ev._amount.eq(total_amount) &&
      ev._closure_time.eq(closureTime);
    });
  });

  async function reimburseSingleImpl(fnName, amount, args, eventName, evFunction) {
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
    let amount = new BN(124);
    let subtaskId = new Array(32);
    subtaskId[0] = 34;
    subtaskId = web3.utils.bytesToHex(subtaskId);
    let amountBytes = amount.toBuffer('big', 32)
    let msg = '0x' + user.substr(2) + gntdeposit.address.substr(2) + web3.utils.bytesToHex(amountBytes).substr(2) + subtaskId.substr(2);
    let [r, s, v] = await signMsg(msg, user);
    await reimburseSingleImpl('reimburseForVerificationCosts', amount, [subtaskId, v, r, s], 'ReimburseForVerificationCosts', (ev) => {
      return ev._subtask_id == subtaskId;
    });
  });

  it("reimburseForCommunication", async () => {
    let amount = new BN(124);
    await reimburseSingleImpl('reimburseForCommunication', amount, [], 'ReimburseForCommunication', (ev) => {
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
