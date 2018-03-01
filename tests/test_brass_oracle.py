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


def deploy_gntw(chain, factory_addr, gnt):
    args = [gnt.address]
    gntw, tx = chain.provider.get_or_deploy_contract('GolemNetworkTokenWrapped',
                                                     deploy_transaction={
                                                         'from': factory_addr
                                                     },
                                                     deploy_args=args)
    gas = chain.wait.for_receipt(tx)
    return gntw, gas


def fund_gntw(chain, gnt, gntw):
    for i, addr in enumerate(tester.accounts[:10]):
        v = 10 * utils.denoms.finney
        assert v < gnt.call().balanceOf(addr)
        chain.wait.for_receipt(
            gntw.transact({'from': addr}).createPersonalDepositAddress())
        PDA = gntw.call().getPersonalDepositAddress(addr)
        chain.wait.for_receipt(
            gnt.transact({'from': addr}).transfer(PDA, v))
        assert v == gnt.call().balanceOf(PDA)
        chain.wait.for_receipt(
            gntw.transact({'from': addr}).processDeposit())
        assert v == gntw.call().balanceOf(addr)


def deploy_oraclized_deposit(chain, factory_addr, token, delay):
    args = [token.address, factory_addr, factory_addr, delay]
    cdep, tx = chain.provider.get_or_deploy_contract('GNTDeposit',
                                                     deploy_transaction={
                                                         'from': factory_addr
                                                     },
                                                     deploy_args=args)
    gas = chain.wait.for_receipt(tx)
    return cdep, gas


def mysetup(chain):
    factory = tester.accounts[9]
    oracle = tester.accounts[8]
    user = tester.accounts[7]
    bn = chain.web3.eth.blockNumber
    start, finish = bn+2, bn+11
    gnt = deploy_gnt(chain, factory, factory, start, finish)
    gntw, gas = deploy_gntw(chain, factory, gnt)
    print("GNTW deployment cost: {}".format(gas['gasUsed']))
    fund_gntw(chain, gnt, gntw)
    cdep, gas = deploy_oraclized_deposit(chain, oracle, gntw, lock_time())
    print("GNTDeposit deployment cost: {}".format(gas['gasUsed']))
    return user, oracle, gnt, gntw, cdep


def do_deposit_20(chain, gnt, gntw, cdep, owner, deposit_size):
    initial_total_deposit = gntw.call().balanceOf(cdep.address)
    initial_dep_size = cdep.call().balanceOf(owner)
    chain.wait.for_receipt(
        gntw.transact({'from': owner}).approve(cdep.address, deposit_size))
    assert deposit_size == gntw.call().allowance(owner, cdep.address)
    assert deposit_size < gntw.call().balanceOf(owner)
    chain.wait.for_receipt(
        cdep.transact({'from': owner}).deposit(deposit_size))
    assert deposit_size != gntw.call().allowance(owner, cdep.address)
    total_deposit = gntw.call().balanceOf(cdep.address)
    assert total_deposit == deposit_size + initial_total_deposit
    assert deposit_size == cdep.call().balanceOf(owner) - initial_dep_size
    assert cdep.call().isLocked(owner)


def do_deposit_223(chain, gnt, gntw, cdep, owner, deposit_size):
    initial_total_deposit = gntw.call().balanceOf(cdep.address)
    initial_dep_size = cdep.call().balanceOf(owner)
    chain.wait.for_receipt(
        gntw.transact({'from': owner}).transferAndCall(
            cdep.address, deposit_size, ""))
    # this one attempts to create GNTW from thin air!
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': owner}).onTokenReceived(owner, 1000, ""))
    total_deposit = gntw.call().balanceOf(cdep.address)
    assert total_deposit == deposit_size + initial_total_deposit
    assert deposit_size == cdep.call().balanceOf(owner) - initial_dep_size
    assert cdep.call().isLocked(owner)


def test_windrawGNT(chain):
    owner_addr, oracle_addr, gnt, gntw, cdep = mysetup(chain)
    gntw_balance = gntw.call().balanceOf(owner_addr)
    assert gntw_balance > 0
    gnt_balance = gnt.call().balanceOf(owner_addr)
    chain.wait.for_receipt(
        gntw.transact({'from': owner_addr}).withdrawGNT(gntw_balance))
    assert gntw_balance + gnt_balance == gnt.call().balanceOf(owner_addr)
    assert 0 == gntw.call().balanceOf(owner_addr)


def test_timelocks(chain):
    attacker = tester.accounts[1]
    owner, _, gnt, gntw, cdep = mysetup(chain)
    deposit_size = 100000
    do_deposit_20(chain, gnt, gntw, cdep, owner, int(deposit_size / 2))
    do_deposit_223(chain, gnt, gntw, cdep, owner, int(deposit_size / 2))
    amnt = gntw.call().balanceOf(cdep.address)
    owner_deposit = cdep.call().balanceOf(owner)
    chain.wait.for_receipt(
        cdep.transact({'from': owner}).unlock())
    bt = blockTimestamp(chain)
    locked_until = cdep.call().getTimelock(owner)
    assert bt < locked_until
    # this withdraw is too early (blockTimestamp < locked_until)
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': owner}).withdraw(owner))
    assert amnt == gntw.call().balanceOf(cdep.address)
    # by wrong person
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': attacker}).withdraw(attacker))
    assert amnt == gntw.call().balanceOf(cdep.address)
    # successful withdrawal
    assert owner_deposit <= cdep.call().balanceOf(owner)
    while blockTimestamp(chain) < locked_until:
        chain.web3.testing.mine(1)
    assert cdep.call().isUnlocked(owner)
    assert owner != gntw.address
    assert gntw.call().balanceOf(cdep.address) >= cdep.call().balanceOf(owner)
    chain.wait.for_receipt(
        cdep.transact({'from': owner}).withdraw(owner))
    assert 0 == cdep.call().balanceOf(owner)
    assert amnt - owner_deposit == gntw.call().balanceOf(cdep.address)
    # unsuccessful retry
    amnt = gntw.call().balanceOf(cdep.address)
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': owner}).withdraw(owner))
    assert 0 == cdep.call().balanceOf(owner)
    assert amnt == gntw.call().balanceOf(cdep.address)


def test_burn(chain):
    owner_addr, oracle_addr, gnt, gntw, cdep = mysetup(chain)
    deposit_size = 100000
    half_dep = int(deposit_size / 2)
    do_deposit_20(chain, gnt, gntw, cdep, owner_addr, half_dep)
    do_deposit_223(chain, gnt, gntw, cdep, owner_addr, half_dep)
    amnt = gntw.call().balanceOf(cdep.address)
    # not oracle
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': owner_addr}).burn(owner_addr, half_dep))
    assert amnt == gntw.call().balanceOf(cdep.address)
    # oracle
    chain.wait.for_receipt(
        cdep.transact({'from': oracle_addr}).burn(owner_addr, half_dep))
    assert amnt-half_dep == cdep.call().balanceOf(owner_addr)
    assert amnt-half_dep == gntw.call().balanceOf(cdep.address)


def test_reimburse(chain):
    owner_addr, oracle_addr, gnt, gntw, cdep = mysetup(chain)
    other_addr = tester.accounts[1]
    subtask_id = "subtask_id123".zfill(32)
    closure_time = 2137
    deposit_size = 100000
    half_dep = int(deposit_size / 2)
    do_deposit_20(chain, gnt, gntw, cdep, owner_addr, half_dep)
    do_deposit_223(chain, gnt, gntw, cdep, owner_addr, half_dep)
    amnt = gntw.call().balanceOf(cdep.address)
    assert amnt == gntw.call().balanceOf(cdep.address)

    q = queue.Queue()
    cbk = functools.partial(lambda event, q: q.put(event), q=q)
    cdep.on('ReimburseForSubtask', None, cbk)
    cdep.on('ReimburseForNoPayment', None, cbk)
    cdep.on('ReimburseForVerificationCosts', None, cbk)
    # not oracle
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': other_addr}).reimburseForSubtask(
                owner_addr,
                other_addr,
                half_dep,
                subtask_id))
    assert amnt == gntw.call().balanceOf(cdep.address)
    assert q.empty()

    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': other_addr}).reimburseForNoPayment(
                owner_addr,
                other_addr,
                half_dep,
                closure_time))
    assert amnt == gntw.call().balanceOf(cdep.address)
    assert q.empty()

    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': other_addr}).reimburseForVerificationCosts(
                owner_addr,
                half_dep,
                subtask_id))
    assert amnt == gntw.call().balanceOf(cdep.address)
    assert q.empty()

    # oracle
    chain.wait.for_receipt(
        cdep.transact({'from': oracle_addr}).reimburseForSubtask(
            owner_addr,
            other_addr,
            half_dep,
            subtask_id))
    time.sleep(1)
    event = q.get()
    assert 'ReimburseForSubtask' == event['event']
    assert owner_addr == utils.decode_hex(event['args']['_requestor'][2:])
    assert other_addr == utils.decode_hex(event['args']['_provider'][2:])
    assert half_dep == event['args']['_amount']
    assert subtask_id == event['args']['_subtask_id']
    assert amnt - half_dep == cdep.call().balanceOf(owner_addr)
    assert amnt - half_dep == gntw.call().balanceOf(cdep.address)

    amount = 1
    chain.wait.for_receipt(
        cdep.transact({'from': oracle_addr}).reimburseForNoPayment(
            owner_addr,
            other_addr,
            amount,
            closure_time))
    event = q.get()
    assert 'ReimburseForNoPayment' == event['event']
    assert owner_addr == utils.decode_hex(event['args']['_requestor'][2:])
    assert other_addr == utils.decode_hex(event['args']['_provider'][2:])
    assert amount == event['args']['_amount']
    assert closure_time == event['args']['_closure_time']
    assert amnt - half_dep - amount == cdep.call().balanceOf(owner_addr)
    assert amnt - half_dep - amount == gntw.call().balanceOf(cdep.address)

    amount = half_dep - 1
    chain.wait.for_receipt(
        cdep.transact({'from': oracle_addr}).reimburseForVerificationCosts(
            owner_addr,
            amount,
            subtask_id))
    event = q.get()
    assert 'ReimburseForVerificationCosts' == event['event']
    assert owner_addr == utils.decode_hex(event['args']['_from'][2:])
    assert amount == event['args']['_amount']
    assert 0 == cdep.call().balanceOf(owner_addr)
    assert 0 == gntw.call().balanceOf(cdep.address)

    assert q.empty()


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
