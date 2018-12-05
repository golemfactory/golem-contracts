import ethereum.tester as tester
import functools
import os
import queue
import random
import time
from rlp.utils import encode_hex
import ethereum.utils as utils
import pytest
from ethereum.tester import TransactionFailed


def deploy_gnt(chain, factory_addr, migration_addr, start, finish):
    args = [factory_addr, migration_addr, start, finish]
    gnt, _ = chain.provider.get_or_deploy_contract('GolemNetworkToken',
                                                   deploy_args=args)
    fund_and_finalize(chain, gnt, chain.web3.eth.coinbase)
    return gnt


def fund_and_finalize(chain, gnt, x):
    tcr = gnt.call().tokenCreationRate()
    minv = int(gnt.call().tokenCreationMin() / 10 / tcr) + 1
    maxv = int(gnt.call().tokenCreationCap() / 10 / tcr)
    for i, addr in enumerate(tester.accounts[:10]):
        v = random.randrange(minv, maxv)
        chain.wait.for_receipt(
            gnt.transact({'value': v, 'from': encode_hex(addr)}).create())
    chain.wait.for_receipt(
        gnt.transact().finalize())
    assert not gnt.call().funding()


def deploy_gntb(chain, factory_addr, gnt):
    args = [gnt.address]
    gntb, tx = chain.provider.get_or_deploy_contract('GolemNetworkTokenBatching',
                                                     deploy_transaction={
                                                         'from': factory_addr
                                                     },
                                                     deploy_args=args)
    gas = chain.wait.for_receipt(tx)
    return gntb, gas


def fund_gntb(chain, gnt, gntb):
    for i, addr in enumerate(tester.accounts[:10]):
        v = 10 * utils.denoms.finney
        assert v < gnt.call().balanceOf(addr)
        chain.wait.for_receipt(
            gntb.transact({'from': addr}).openGate())
        PDA = gntb.call().getGateAddress(addr)
        chain.wait.for_receipt(
            gnt.transact({'from': addr}).transfer(PDA, v))
        assert v == gnt.call().balanceOf(PDA)
        chain.wait.for_receipt(
            gntb.transact({'from': addr}).transferFromGate())
        assert v == gntb.call().balanceOf(addr)


def deploy_oraclized_deposit(chain, factory_addr, concent, token, delay):
    args = [token.address, concent, concent, delay]
    cdep, tx = chain.provider.get_or_deploy_contract('GNTDeposit',
                                                     deploy_transaction={
                                                         'from': factory_addr
                                                     },
                                                     deploy_args=args)
    gas = chain.wait.for_receipt(tx)
    return cdep, gas


def mysetup(chain):
    factory = tester.accounts[9]
    concent = tester.accounts[8]
    bn = chain.web3.eth.blockNumber
    start, finish = bn+2, bn+11
    gnt = deploy_gnt(chain, factory, factory, start, finish)
    gntb, gas = deploy_gntb(chain, factory, gnt)
    print("GNTB deployment cost: {}".format(gas['gasUsed']))
    fund_gntb(chain, gnt, gntb)
    cdep, gas = deploy_oraclized_deposit(chain, factory, concent, gntb, lock_time())
    print("GNTDeposit deployment cost: {}".format(gas['gasUsed']))
    return factory, concent, gnt, gntb, cdep


def do_deposit_223(chain, gnt, gntb, cdep, owner, deposit_size):
    initial_total_deposit = gntb.call().balanceOf(cdep.address)
    initial_dep_size = cdep.call().balanceOf(owner)
    chain.wait.for_receipt(
        gntb.transact({'from': owner}).transferAndCall(
            cdep.address, deposit_size, ""))
    # this one attempts to create GNTB from thin air!
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': owner}).onTokenReceived(owner, 1000, ""))
    total_deposit = gntb.call().balanceOf(cdep.address)
    assert total_deposit == deposit_size + initial_total_deposit
    assert deposit_size == cdep.call().balanceOf(owner) - initial_dep_size


def test_withdrawGNT(chain):
    factory, concent_addr, gnt, gntb, cdep = mysetup(chain)
    user_addr = tester.accounts[0]
    gntb_balance = gntb.call().balanceOf(user_addr)
    assert gntb_balance > 0
    gnt_balance = gnt.call().balanceOf(user_addr)
    chain.wait.for_receipt(
        gntb.transact({'from': user_addr}).withdraw(gntb_balance))
    assert gntb_balance + gnt_balance == gnt.call().balanceOf(user_addr)
    assert 0 == gntb.call().balanceOf(user_addr)


def test_withdrawTo(chain):
    factory, concent_addr, gnt, gntb, cdep = mysetup(chain)
    user_addr = tester.accounts[0]
    recipient = tester.accounts[1]
    assert user_addr != recipient
    gntb_balance = gntb.call().balanceOf(user_addr)
    assert gntb_balance > 0
    gnt_balance = gnt.call().balanceOf(recipient)
    chain.wait.for_receipt(
        gntb.transact({'from': user_addr}).withdrawTo(gntb_balance, recipient))
    assert gntb_balance + gnt_balance == gnt.call().balanceOf(recipient)
    assert 0 == gntb.call().balanceOf(user_addr)


def test_withdraw_burn(chain):
    factory, concent_addr, gnt, gntb, cdep = mysetup(chain)
    user_addr = tester.accounts[0]
    gntb_balance = gntb.call().balanceOf(user_addr)
    assert gntb_balance > 0
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(gntb.transact({'from': user_addr}).withdrawTo(
            gntb_balance, b'\0' * 20))


def test_timelocks(chain):
    attacker = tester.accounts[1]
    factory, _, gnt, gntb, cdep = mysetup(chain)
    user_addr = tester.accounts[0]
    deposit_size = 100000
    do_deposit_223(chain, gnt, gntb, cdep, user_addr, deposit_size)
    amnt = gntb.call().balanceOf(cdep.address)
    owner_deposit = cdep.call().balanceOf(user_addr)
    chain.wait.for_receipt(
        cdep.transact({'from': user_addr}).unlock())
    bt = blockTimestamp(chain)
    locked_until = cdep.call().getTimelock(user_addr)
    assert bt < locked_until
    # this withdraw is too early (blockTimestamp < locked_until)
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': user_addr}).withdraw(user_addr))
    assert amnt == gntb.call().balanceOf(cdep.address)
    # by wrong person
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': attacker}).withdraw(attacker))
    assert amnt == gntb.call().balanceOf(cdep.address)
    # successful withdrawal
    assert owner_deposit <= cdep.call().balanceOf(user_addr)
    while blockTimestamp(chain) < locked_until:
        chain.web3.testing.mine(1)
    assert cdep.call().isUnlocked(user_addr)
    assert user_addr != gntb.address
    assert gntb.call().balanceOf(cdep.address) >= cdep.call().balanceOf(user_addr)
    chain.wait.for_receipt(
        cdep.transact({'from': user_addr}).withdraw(user_addr))
    assert 0 == cdep.call().balanceOf(user_addr)
    assert amnt - owner_deposit == gntb.call().balanceOf(cdep.address)
    # unsuccessful retry
    amnt = gntb.call().balanceOf(cdep.address)
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': user_addr}).withdraw(user_addr))
    assert 0 == cdep.call().balanceOf(user_addr)
    assert amnt == gntb.call().balanceOf(cdep.address)


def test_timelock_on_topup(chain):
    factory, _, gnt, gntb, cdep = mysetup(chain)
    user_addr = tester.accounts[0]
    deposit_size = 100000
    timelock = cdep.call().getTimelock(user_addr)
    assert timelock == 0
    do_deposit_223(chain, gnt, gntb, cdep, user_addr, deposit_size // 2)
    chain.wait.for_receipt(cdep.transact({'from': user_addr}).unlock())
    timelock = cdep.call().getTimelock(user_addr)
    assert timelock != 0
    do_deposit_223(chain, gnt, gntb, cdep, user_addr, deposit_size // 2)
    timelock = cdep.call().getTimelock(user_addr)
    assert timelock == 0


def test_burn(chain):
    factory, concent_addr, gnt, gntb, cdep = mysetup(chain)
    user_addr = tester.accounts[0]
    deposit_size = 100000
    half_dep = int(deposit_size / 2)
    do_deposit_223(chain, gnt, gntb, cdep, user_addr, deposit_size)
    amnt = gntb.call().balanceOf(cdep.address)
    # not concent
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': user_addr}).burn(user_addr, half_dep))
    assert amnt == gntb.call().balanceOf(cdep.address)
    # concent
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).burn(user_addr, half_dep))
    assert amnt-half_dep == cdep.call().balanceOf(user_addr)
    assert amnt-half_dep == gntb.call().balanceOf(cdep.address)


def test_reimburse(chain):
    factory, concent_addr, gnt, gntb, cdep = mysetup(chain)
    user_addr = tester.accounts[0]
    other_addr = tester.accounts[1]
    subtask_id = "subtask_id123".zfill(32)
    closure_time = 2137
    deposit_size = 100000
    half_dep = int(deposit_size / 2)
    do_deposit_223(chain, gnt, gntb, cdep, user_addr, deposit_size)
    amnt = gntb.call().balanceOf(cdep.address)
    assert amnt == gntb.call().balanceOf(cdep.address)

    q = queue.Queue()
    cbk = functools.partial(lambda event, q: q.put(event), q=q)
    cdep.on('ReimburseForSubtask', None, cbk)
    cdep.on('ReimburseForNoPayment', None, cbk)
    cdep.on('ReimburseForVerificationCosts', None, cbk)
    cdep.on('ReimburseForCommunication', None, cbk)
    # not concent
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': other_addr}).reimburseForSubtask(
                user_addr,
                other_addr,
                half_dep,
                subtask_id))
    assert amnt == gntb.call().balanceOf(cdep.address)
    assert q.empty()

    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': other_addr}).reimburseForNoPayment(
                user_addr,
                other_addr,
                half_dep,
                closure_time))
    assert amnt == gntb.call().balanceOf(cdep.address)
    assert q.empty()

    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': other_addr}).reimburseForVerificationCosts(
                user_addr,
                half_dep,
                subtask_id))
    assert amnt == gntb.call().balanceOf(cdep.address)
    assert q.empty()

    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': other_addr}).reimburseForCommunication(
                user_addr,
                half_dep))
    assert amnt == gntb.call().balanceOf(cdep.address)
    assert q.empty()

    # concent
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).reimburseForSubtask(
            user_addr,
            other_addr,
            half_dep,
            subtask_id))
    event = q.get(timeout=60)
    assert 'ReimburseForSubtask' == event['event']
    assert user_addr == utils.decode_hex(event['args']['_requestor'][2:])
    assert other_addr == utils.decode_hex(event['args']['_provider'][2:])
    assert half_dep == event['args']['_amount']
    assert subtask_id == event['args']['_subtask_id']
    assert amnt - half_dep == cdep.call().balanceOf(user_addr)
    assert amnt - half_dep == gntb.call().balanceOf(cdep.address)

    amount = 1
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).reimburseForNoPayment(
            user_addr,
            other_addr,
            amount,
            closure_time))
    event = q.get(timeout=60)
    assert 'ReimburseForNoPayment' == event['event']
    assert user_addr == utils.decode_hex(event['args']['_requestor'][2:])
    assert other_addr == utils.decode_hex(event['args']['_provider'][2:])
    assert amount == event['args']['_amount']
    assert closure_time == event['args']['_closure_time']
    assert amnt - half_dep - amount == cdep.call().balanceOf(user_addr)
    assert amnt - half_dep - amount == gntb.call().balanceOf(cdep.address)

    amount = 2
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).reimburseForVerificationCosts(
            user_addr,
            amount,
            subtask_id))
    event = q.get(timeout=60)
    assert 'ReimburseForVerificationCosts' == event['event']
    assert user_addr == utils.decode_hex(event['args']['_from'][2:])
    assert amount == event['args']['_amount']
    assert amnt - half_dep - 3 == cdep.call().balanceOf(user_addr)
    assert amnt - half_dep - 3 == gntb.call().balanceOf(cdep.address)

    amount = half_dep - 3
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).reimburseForCommunication(
            user_addr,
            amount))
    event = q.get(timeout=60)
    assert 'ReimburseForCommunication' == event['event']
    assert user_addr == utils.decode_hex(event['args']['_from'][2:])
    assert amount == event['args']['_amount']
    assert 0 == cdep.call().balanceOf(user_addr)
    assert 0 == gntb.call().balanceOf(cdep.address)

    assert q.empty()


def test_transfer_concent(chain):
    factory, concent_addr, gnt, gntb, cdep = mysetup(chain)
    user_addr = tester.accounts[0]
    random_addr = tester.accounts[1]

    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).burn(random_addr, 0))

    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': user_addr}).transferConcent(user_addr))

    chain.wait.for_receipt(
        cdep.transact({'from': factory}).transferConcent(user_addr))

    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': concent_addr}).burn(random_addr, 0))

    chain.wait.for_receipt(
        cdep.transact({'from': user_addr}).burn(random_addr, 0))


def test_transfer_coldwallet(chain):
    factory, concent_addr, gnt, gntb, cdep = mysetup(chain)
    user_addr = tester.accounts[0]
    new_coldwallet = tester.accounts[1]
    deposit_size = 100000
    half_dep = int(deposit_size / 2)
    do_deposit_223(chain, gnt, gntb, cdep, user_addr, deposit_size)

    coldwallet_balance = gntb.call().balanceOf(concent_addr)
    assert deposit_size == cdep.call().balanceOf(user_addr)
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).reimburseForCommunication(
            user_addr,
            half_dep))
    assert half_dep == cdep.call().balanceOf(user_addr)
    assert half_dep + coldwallet_balance == gntb.call().balanceOf(concent_addr)

    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': user_addr}).transferColdwallet(user_addr))

    chain.wait.for_receipt(
        cdep.transact({'from': factory}).transferColdwallet(new_coldwallet))

    coldwallet_balance = gntb.call().balanceOf(new_coldwallet)
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).reimburseForCommunication(
            user_addr,
            half_dep))
    assert 0 == cdep.call().balanceOf(user_addr)
    assert half_dep + coldwallet_balance == gntb.call().balanceOf(new_coldwallet)  # noqa


def test_deposit_limit(chain):
    factory, concent_addr, gnt, gntb, cdep = mysetup(chain)
    assert cdep.call().maximum_deposit_amount() == 0
    limit = 1000
    chain.wait.for_receipt(
        cdep.transact({'from': factory}).setMaximumDepositAmount(limit))
    assert cdep.call().maximum_deposit_amount() == limit

    user_addr = tester.accounts[0]
    with pytest.raises(TransactionFailed):
        do_deposit_223(chain, gnt, gntb, cdep, user_addr, limit + 1)
    do_deposit_223(chain, gnt, gntb, cdep, user_addr, limit)
    with pytest.raises(TransactionFailed):
        do_deposit_223(chain, gnt, gntb, cdep, user_addr, 1)
    assert cdep.call().balanceOf(user_addr) == limit
    chain.wait.for_receipt(
        cdep.transact({'from': user_addr}).unlock())
    locked_until = cdep.call().getTimelock(user_addr)
    while blockTimestamp(chain) < locked_until:
        chain.web3.testing.mine(1)
    chain.wait.for_receipt(
        cdep.transact({'from': user_addr}).withdraw(user_addr))
    do_deposit_223(chain, gnt, gntb, cdep, user_addr, limit)


def test_total_deposits_limit(chain):
    factory, concent_addr, gnt, gntb, cdep = mysetup(chain)
    assert cdep.call().maximum_deposits_total() == 0
    limit = 1000
    half_limit = limit // 2
    chain.wait.for_receipt(
        cdep.transact({'from': factory}).setMaximumDepositsTotal(limit))
    assert cdep.call().maximum_deposits_total() == limit

    user_addr1 = tester.accounts[0]
    assert cdep.call().isDepositPossible(user_addr1, half_limit)
    do_deposit_223(chain, gnt, gntb, cdep, user_addr1, half_limit)
    assert cdep.call().maximum_deposits_total() == limit

    user_addr2 = tester.accounts[1]
    assert cdep.call().isDepositPossible(user_addr2, half_limit)
    do_deposit_223(chain, gnt, gntb, cdep, user_addr2, half_limit)

    user_addr3 = tester.accounts[2]
    assert not cdep.call().isDepositPossible(user_addr3, 1)
    with pytest.raises(TransactionFailed):
        do_deposit_223(chain, gnt, gntb, cdep, user_addr3, 1)


def test_reimburse_limit(chain):
    factory, concent_addr, gnt, gntb, cdep = mysetup(chain)
    assert cdep.call().daily_reimbursement_limit() == 0
    limit = 1000
    chain.wait.for_receipt(
        cdep.transact({'from': factory}).setDailyReimbursementLimit(limit))
    assert cdep.call().daily_reimbursement_limit() == limit

    user_addr = tester.accounts[0]
    do_deposit_223(chain, gnt, gntb, cdep, user_addr, 2 * limit)
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).reimburseForCommunication(
            user_addr,
            limit))
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': concent_addr}).reimburseForCommunication(
                user_addr,
                1))

    current_day = blockTimestamp(chain) // days(1)
    while blockTimestamp(chain) // days(1) == current_day:
        chain.web3.testing.mine(1)
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).reimburseForCommunication(
            user_addr,
            limit))


def blockTimestamp(chain):
    height = chain.web3.eth.blockNumber
    block = chain.web3.eth.getBlock(height)
    return block['timestamp']


def lock_time():
    return seconds(60)


def weeks(n):
    return n*days(7)


def days(n):
    return n*hours(24)


def hours(n):
    return n*minutes(60)


def minutes(n):
    return n*seconds(60)


def seconds(n):
    return n
