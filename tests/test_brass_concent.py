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
    concent = tester.accounts[8]
    user = tester.accounts[7]
    bn = chain.web3.eth.blockNumber
    start, finish = bn+2, bn+11
    gnt = deploy_gnt(chain, factory, factory, start, finish)
    gntb, gas = deploy_gntb(chain, factory, gnt)
    print("GNTB deployment cost: {}".format(gas['gasUsed']))
    fund_gntb(chain, gnt, gntb)
    cdep, gas = deploy_oraclized_deposit(chain, concent, gntb, lock_time())
    print("GNTDeposit deployment cost: {}".format(gas['gasUsed']))
    return user, concent, gnt, gntb, cdep


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
    assert cdep.call().isLocked(owner)


def test_withdrawGNT(chain):
    owner_addr, concent_addr, gnt, gntb, cdep = mysetup(chain)
    gntb_balance = gntb.call().balanceOf(owner_addr)
    assert gntb_balance > 0
    gnt_balance = gnt.call().balanceOf(owner_addr)
    chain.wait.for_receipt(
        gntb.transact({'from': owner_addr}).withdraw(gntb_balance))
    assert gntb_balance + gnt_balance == gnt.call().balanceOf(owner_addr)
    assert 0 == gntb.call().balanceOf(owner_addr)


def test_withdrawTo(chain):
    owner_addr, concent_addr, gnt, gntb, cdep = mysetup(chain)
    recipient = tester.accounts[0]
    assert owner_addr != recipient
    gntb_balance = gntb.call().balanceOf(owner_addr)
    assert gntb_balance > 0
    gnt_balance = gnt.call().balanceOf(recipient)
    chain.wait.for_receipt(
        gntb.transact({'from': owner_addr}).withdrawTo(gntb_balance, recipient))
    assert gntb_balance + gnt_balance == gnt.call().balanceOf(recipient)
    assert 0 == gntb.call().balanceOf(owner_addr)


def test_withdraw_burn(chain):
    owner_addr, concent_addr, gnt, gntb, cdep = mysetup(chain)
    gntb_balance = gntb.call().balanceOf(owner_addr)
    assert gntb_balance > 0
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(gntb.transact({'from': owner_addr}).withdrawTo(
            gntb_balance, b'\0' * 20))


def test_timelocks(chain):
    attacker = tester.accounts[1]
    owner, _, gnt, gntb, cdep = mysetup(chain)
    deposit_size = 100000
    do_deposit_223(chain, gnt, gntb, cdep, owner, deposit_size)
    amnt = gntb.call().balanceOf(cdep.address)
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
    assert amnt == gntb.call().balanceOf(cdep.address)
    # by wrong person
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': attacker}).withdraw(attacker))
    assert amnt == gntb.call().balanceOf(cdep.address)
    # successful withdrawal
    assert owner_deposit <= cdep.call().balanceOf(owner)
    while blockTimestamp(chain) < locked_until:
        chain.web3.testing.mine(1)
    assert cdep.call().isUnlocked(owner)
    assert owner != gntb.address
    assert gntb.call().balanceOf(cdep.address) >= cdep.call().balanceOf(owner)
    chain.wait.for_receipt(
        cdep.transact({'from': owner}).withdraw(owner))
    assert 0 == cdep.call().balanceOf(owner)
    assert amnt - owner_deposit == gntb.call().balanceOf(cdep.address)
    # unsuccessful retry
    amnt = gntb.call().balanceOf(cdep.address)
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': owner}).withdraw(owner))
    assert 0 == cdep.call().balanceOf(owner)
    assert amnt == gntb.call().balanceOf(cdep.address)


def test_burn(chain):
    owner_addr, concent_addr, gnt, gntb, cdep = mysetup(chain)
    deposit_size = 100000
    half_dep = int(deposit_size / 2)
    do_deposit_223(chain, gnt, gntb, cdep, owner_addr, deposit_size)
    amnt = gntb.call().balanceOf(cdep.address)
    # not concent
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': owner_addr}).burn(owner_addr, half_dep))
    assert amnt == gntb.call().balanceOf(cdep.address)
    # concent
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).burn(owner_addr, half_dep))
    assert amnt-half_dep == cdep.call().balanceOf(owner_addr)
    assert amnt-half_dep == gntb.call().balanceOf(cdep.address)


def test_reimburse(chain):
    owner_addr, concent_addr, gnt, gntb, cdep = mysetup(chain)
    other_addr = tester.accounts[1]
    subtask_id = "subtask_id123".zfill(32)
    closure_time = 2137
    deposit_size = 100000
    half_dep = int(deposit_size / 2)
    do_deposit_223(chain, gnt, gntb, cdep, owner_addr, deposit_size)
    amnt = gntb.call().balanceOf(cdep.address)
    assert amnt == gntb.call().balanceOf(cdep.address)

    q = queue.Queue()
    cbk = functools.partial(lambda event, q: q.put(event), q=q)
    cdep.on('ReimburseForSubtask', None, cbk)
    cdep.on('ReimburseForNoPayment', None, cbk)
    cdep.on('ReimburseForVerificationCosts', None, cbk)
    # not concent
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': other_addr}).reimburseForSubtask(
                owner_addr,
                other_addr,
                half_dep,
                subtask_id))
    assert amnt == gntb.call().balanceOf(cdep.address)
    assert q.empty()

    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': other_addr}).reimburseForNoPayment(
                owner_addr,
                other_addr,
                half_dep,
                closure_time))
    assert amnt == gntb.call().balanceOf(cdep.address)
    assert q.empty()

    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': other_addr}).reimburseForVerificationCosts(
                owner_addr,
                half_dep,
                subtask_id))
    assert amnt == gntb.call().balanceOf(cdep.address)
    assert q.empty()

    # concent
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).reimburseForSubtask(
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
    assert amnt - half_dep == gntb.call().balanceOf(cdep.address)

    amount = 1
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).reimburseForNoPayment(
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
    assert amnt - half_dep - amount == gntb.call().balanceOf(cdep.address)

    amount = half_dep - 1
    chain.wait.for_receipt(
        cdep.transact({'from': concent_addr}).reimburseForVerificationCosts(
            owner_addr,
            amount,
            subtask_id))
    event = q.get()
    assert 'ReimburseForVerificationCosts' == event['event']
    assert owner_addr == utils.decode_hex(event['args']['_from'][2:])
    assert amount == event['args']['_amount']
    assert 0 == cdep.call().balanceOf(owner_addr)
    assert 0 == gntb.call().balanceOf(cdep.address)

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
