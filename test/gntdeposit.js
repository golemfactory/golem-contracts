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

  it("burn - funds left", async () => {
    let amount = new BN(124);
    // not Concent
    await truffleAssert.reverts(gntdeposit.burn(user, amount, {from: user}), "Concent only method");

    await gntdeposit.burn(user, amount, {from: concent});
    assert.isTrue(depositBalance.sub(amount).eq(await gntdeposit.balanceOf(user)));
  });

  it("burn - all funds", async () => {
    let amount = new BN(await gntdeposit.balanceOf.call(user));
    // not Concent
    await truffleAssert.reverts(gntdeposit.burn(user, amount, {from: user}), "Concent only method");

    await gntdeposit.burn(user, amount, {from: concent});
    assert.isTrue(depositBalance.sub(amount).eq(await gntdeposit.balanceOf(user)));
  });

  it("reimburseForSubtask", async () => {
    let amount = new BN(124);
    let subtaskIdBytes = new Array(32);
    subtaskIdBytes[1] = 34;
    let [msg, amountBytes, subtaskId] = _prepareSubtask(amount, subtaskIdBytes);
    let [r, s, v] = await _signMsg(msg, user);
    await _reimbursePairImpl('reimburseForSubtask', amount, [subtaskId, v, r, s], 'ReimburseForSubtask', (ev) => {
      return ev._subtask_id == subtaskId;
    });
  });

  it("reimburseForNoPayment - two subtasks", async () => {
    let limit = new BN(1000);
    await _setDailyReimbursementLimit(limit);
    let amount1 = new BN(124);
    let subtaskId1Bytes = new Array(32);
    subtaskId1Bytes[0] = 34;
    let [msg1, amountBytes1, subtaskId1] = _prepareSubtask(amount1, subtaskId1Bytes);
    let [r1, s1, v1] = await _signMsg(msg1, user);


    let amount2 = new BN(224);
    let subtaskId2Bytes = new Array(32);
    subtaskId2Bytes[3] = 23;
    let [msg2, amountBytes2, subtaskId2] = _prepareSubtask(amount2, subtaskId2Bytes);
    let [r2, s2, v2] = await _signMsg(msg2, user);

    let closureTime = new BN(44431);
    let reimburse_amount = amount1.add(amount2).divn(2);

    // not Concent
    await truffleAssert.reverts(gntdeposit['reimburseForNoPayment'](
      user,
      other,
      [amount1, amount2],
      [subtaskId1, subtaskId2],
      [v1, v2],
      [r1, r2],
      [s1, s2],
      reimburse_amount,
      closureTime,
      {from: other},
    ), "Concent only method");

    // reimburse amount exceeds total amount
    await truffleAssert.reverts(gntdeposit['reimburseForNoPayment'](
      user,
      other,
      [amount1, amount2],
      [subtaskId1, subtaskId2],
      [v1, v2],
      [r1, r2],
      [s1, s2],
      amount1.add(amount2).addn(1),
      closureTime,
      {from: concent},
    ), "Reimburse amount exceeds total");


    let tx = await gntdeposit['reimburseForNoPayment'](
      user,
      other,
      [amount1, amount2],
      [subtaskId1, subtaskId2],
      [v1, v2],
      [r1, r2],
      [s1, s2],
      reimburse_amount,
      closureTime,
      {from: concent},
    );
    assert.isTrue(depositBalance.sub(reimburse_amount).eq(await gntdeposit.balanceOf(user)));
    assert.isTrue(reimburse_amount.eq(await gntb.balanceOf(other)));
    truffleAssert.eventEmitted(tx, 'ReimburseForNoPayment', (ev) => {
      return ev._requestor == user &&
      ev._provider == other &&
      ev._amount.eq(reimburse_amount) &&
      ev._closure_time.eq(closureTime);
    });
  });

  it("reimburseForNoPayment - one subtask", async () => {
    let limit = new BN(1000);
    await _setDailyReimbursementLimit(limit);
    let amount1 = new BN(124);
    let subtaskId1Bytes = new Array(32);
    subtaskId1Bytes[0] = 34;
    let [msg1, amountBytes1, subtaskId1] = _prepareSubtask(amount1, subtaskId1Bytes);
    let [r1, s1, v1] = await _signMsg(msg1, user);

    let closureTime = new BN(44431);
    let reimburse_amount = amount1.divn(2);

    // not Concent
    await truffleAssert.reverts(gntdeposit['reimburseForNoPayment'](
      user,
      other,
      [amount1],
      [subtaskId1],
      [v1],
      [r1],
      [s1],
      reimburse_amount,
      closureTime,
      {from: other},
    ), "Concent only method");

    // reimburse amount exceeds total amount
    await truffleAssert.reverts(gntdeposit['reimburseForNoPayment'](
      user,
      other,
      [amount1],
      [subtaskId1],
      [v1],
      [r1],
      [s1],
      amount1.addn(1),
      closureTime,
      {from: concent},
    ), "Reimburse amount exceeds total");


    let tx = await gntdeposit['reimburseForNoPayment'](
      user,
      other,
      [amount1],
      [subtaskId1],
      [v1],
      [r1],
      [s1],
      reimburse_amount,
      closureTime,
      {from: concent},
    );
    assert.isTrue(depositBalance.sub(reimburse_amount).eq(await gntdeposit.balanceOf(user)));
    assert.isTrue(reimburse_amount.eq(await gntb.balanceOf(other)));
    truffleAssert.eventEmitted(tx, 'ReimburseForNoPayment', (ev) => {
      return ev._requestor == user &&
      ev._provider == other &&
      ev._amount.eq(reimburse_amount) &&
      ev._closure_time.eq(closureTime);
    });
  });

  it("reimburseForVerificationCosts", async () => {
    let amount = new BN(124);
    let subtaskIdBytes = new Array(32);
    subtaskIdBytes[0] = 34;
    let [msg, amountBytes, subtaskId] = _prepareSubtask(amount, subtaskIdBytes, gntdeposit.address);
    let [r, s, v] = await _signMsg(msg, user);
    await _reimburseSingleImpl('reimburseForVerificationCosts', amount, [subtaskId, v, r, s], true, 'ReimburseForVerificationCosts', (ev) => {
      return ev._subtask_id == subtaskId;
    });
  });

  it("reimburseForCommunication", async () => {
    let amount = new BN(124);
    await _reimburseSingleImpl('reimburseForCommunication', amount, [], false, 'ReimburseForCommunication', (ev) => {
      return true;
    });
  });

  it("reimburseForVerificationCosts - worse case", async () => {
    // Set daily limit

    let limit = new BN(1000);
    await _setDailyReimbursementLimit(limit);

    // do test
    let amount1 = new BN(64);
    let subtaskId1Bytes = new Array(32);
    subtaskId1Bytes[0] = 34;
    let [msg1, amountBytes1, subtaskId1] = _prepareSubtask(amount1, subtaskId1Bytes, gntdeposit.address);
    let [r1, s1, v1] = await _signMsg(msg1, user);
    await _reimburseSingleImpl('reimburseForVerificationCosts', amount1, [subtaskId1, v1, r1, s1], true, 'ReimburseForVerificationCosts', (ev) => {
      return ev._subtask_id == subtaskId1;
    });
    let subtaskId2Bytes = new Array(32);
    subtaskId2Bytes[1] = 16;
    let amount2 = amount1.divn(2);
    let [msg2, amountBytes2, subtaskId2] = _prepareSubtask(amount2, subtaskId2Bytes, gntdeposit.address);
    let [r2, s2, v2] = await _signMsg(msg2, user);
    await _reimburseSingleImpl('reimburseForVerificationCosts', amount2, [subtaskId2, v2, r2, s2], true, 'ReimburseForVerificationCosts', (ev) => {
      return ev._subtask_id == subtaskId2;
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
    const limit = new BN(1000);
    await _setDailyReimbursementLimit(limit);

    await truffleAssert.reverts(gntdeposit.reimburseForCommunication(user, limit.addn(1), {from: concent}), "Daily reimbursement limit hit");
    await gntdeposit.reimburseForCommunication(user, limit.subn(1), {from: concent});
    await gntdeposit.reimburseForCommunication(user, new BN(1), {from: concent});
    await truffleAssert.reverts(gntdeposit.reimburseForCommunication(user, new BN(1), {from: concent}), "Daily reimbursement limit hit");
    await helpers.time.increase(24 * 60 * 60 + 1);
    await gntdeposit.reimburseForCommunication(user, new BN(1), {from: concent});
  });

  function _prepareSubtask(amount, subtaskIdBytes, _other = other) {
    let amountBn = new BN(amount);
    let amountBytes = amountBn.toBuffer('big', 32);
    subtaskIdHex = web3.utils.bytesToHex(subtaskIdBytes);
    let msg = '0x' + gntdeposit.address.substr(2) + user.substr(2) + _other.substr(2) + web3.utils.bytesToHex(amountBytes).substr(2) + subtaskIdHex.substr(2);
    return [
      msg,
      amountBytes,
      subtaskIdHex,
    ]
  }

  async function _signMsg(msg, account) {
    let signature = await web3.eth.sign(msg, account);
    signature = signature.substr(2);
    let r = '0x' + signature.substr(0, 64);
    let s = '0x' + signature.substr(64, 64);
    let v = (new BN(signature.substr(128, 2), 16)).addn(27);
    return [r, s, v];
  }

  async function _reimbursePairImpl(fnName, amount, args, eventName, evFunction) {
    // not Concent
    let reimburse_amount = amount.divn(2);
    await truffleAssert.reverts(gntdeposit[fnName](user, other, amount, ...args, reimburse_amount, {from: other}), "Concent only method");
    await truffleAssert.reverts(gntdeposit[fnName](user, other, amount, ...args, amount.addn(1), {from: concent}), "Reimburse amount exceeds allowed");

    let tx = await gntdeposit[fnName](user, other, amount, ...args, reimburse_amount, {from: concent});
    assert.isTrue(depositBalance.sub(reimburse_amount).eq(await gntdeposit.balanceOf(user)));
    assert.isTrue(reimburse_amount.eq(await gntb.balanceOf(other)));
    truffleAssert.eventEmitted(tx, eventName, (ev) => {
      return ev._requestor == user &&
      ev._provider == other &&
      ev._amount.eq(reimburse_amount) &&
      evFunction(ev);
    });
  }

  async function _reimburseSingleImpl(fnName, amount, args, custom_reimburse_amount, eventName, evFunction) {
    // not Concent
    let reimburse_amount = amount;
    if (custom_reimburse_amount) {
      reimburse_amount = amount.addn(1);
      args.push(reimburse_amount);
      await truffleAssert.reverts(gntdeposit[fnName](user, amount, ...args, {from: concent}), "Reimburse amount exceeds allowed");
      reimburse_amount.idivn(2);
    }
    await truffleAssert.reverts(gntdeposit[fnName](user, amount, ...args, {from: other}), "Concent only method");

    let oldConcentBalance = await gntb.balanceOf(concent);
    let tx = await gntdeposit[fnName](user, amount, ...args, {from: concent});
    assert.isTrue(depositBalance.sub(reimburse_amount).eq(await gntdeposit.balanceOf(user)), "balance not subtracted");
    depositBalance = await gntdeposit.balanceOf.call(user);
    assert.isTrue(oldConcentBalance.add(reimburse_amount).eq(await gntb.balanceOf(concent)), "balance not added");
    truffleAssert.eventEmitted(tx, eventName, (ev) => {
      return ev._from == user &&
      ev._amount.eq(reimburse_amount) &&
      evFunction(ev);
    });
  }

  async function _setDailyReimbursementLimit(limit) {
    await truffleAssert.reverts(gntdeposit.setDailyReimbursementLimit(limit, {from: other}), "Owner only method");
    await truffleAssert.reverts(gntdeposit.setDailyReimbursementLimit(limit, {from: concent}), "Owner only method");
    await gntdeposit.setDailyReimbursementLimit(limit, {from: golemfactory});
    assert.isTrue(limit.eq(await gntdeposit.daily_reimbursement_limit.call()));
  }
});
