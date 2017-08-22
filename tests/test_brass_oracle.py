import ethereum.tester as tester
import random
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
    for i, addr in enumerate(tester.accounts[:10]):
        v = random.randrange(15000 * utils.denoms.ether,
                             82000 * utils.denoms.ether)
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
        v = 100 * utils.denoms.ether
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


def deploy_oraclized_deposit(chain, factory_addr, token):
    args = [token.address, factory_addr, "brass-oracle.eth"]
    cdep, tx = chain.provider.get_or_deploy_contract('GNTDeposit',
                                                     deploy_transaction={
                                                         'from': factory_addr
                                                     },
                                                     deploy_args=args)
    gas = chain.wait.for_receipt(tx)
    return cdep, gas


def mysetup(chain):
    # r_priv = tester.keys[9]
    # r_pub = bitcoin.privtopub(r_priv)
    r_addr = tester.accounts[9]
    oracle_addr = tester.accounts[8]
    bn = chain.web3.eth.blockNumber
    start, finish = bn+2, bn+11
    gnt = deploy_gnt(chain, r_addr, r_addr, start, finish)
    gntw, gas = deploy_gntw(chain, r_addr, gnt)
    print("GNTW deployment cost: {}".format(gas['gasUsed']))
    fund_gntw(chain, gnt, gntw)
    cdep, gas = deploy_oraclized_deposit(chain, oracle_addr, gntw)
    print("GNTDeposit deployment cost: {}".format(gas['gasUsed']))
    return r_addr, oracle_addr, gnt, gntw, cdep


def do_deposit(chain, gnt, gntw, cdep, owner, deposit_size, lockUntil):
    chain.wait.for_receipt(
        gntw.transact({'from': owner}).approve(cdep.address, deposit_size))
    assert deposit_size == gntw.call().allowance(owner, cdep.address)
    assert deposit_size < gntw.call().balanceOf(owner)
    chain.wait.for_receipt(
        cdep.transact({'from': owner}).deposit(deposit_size, lockUntil))
    assert deposit_size != gntw.call().allowance(owner, cdep.address)
    total_deposit = gntw.call().balanceOf(cdep.address)
    assert total_deposit == deposit_size
    assert deposit_size == cdep.call().balanceOf(owner)


def test_windrawGNT(chain):
    owner_addr, oracle_addr, gnt, gntw, cdep = mysetup(chain)
    gntw_balance = gntw.call().balanceOf(owner_addr)
    assert gntw_balance > 0
    gnt_balance = gnt.call().balanceOf(owner_addr)
    chain.wait.for_receipt(
        gntw.transact({'from': owner_addr}).transfer(gntw.address,
                                                     gntw_balance))
    assert gntw_balance + gnt_balance == gnt.call().balanceOf(owner_addr)
    assert 0 == gntw.call().balanceOf(owner_addr)


def test_timelocks(chain):
    bn = chain.web3.eth.blockNumber
    lockUntil = bn+100
    attacker_addr = tester.accounts[1]
    owner_addr, oracle_addr, gnt, gntw, cdep = mysetup(chain)
    deposit_size = 100000
    do_deposit(chain, gnt, gntw, cdep, owner_addr, deposit_size, lockUntil)
    assert chain.web3.eth.blockNumber < lockUntil
    amnt = gntw.call().balanceOf(cdep.address)
    # this withdraw is too early (blockNumber < lockUntil)
    chain.wait.for_receipt(
        cdep.transact({'from': owner_addr}).withdraw(owner_addr))
    assert amnt == gntw.call().balanceOf(cdep.address)
    # by wrong person
    chain.wait.for_receipt(
        cdep.transact({'from': attacker_addr}).withdraw(attacker_addr))
    assert amnt == gntw.call().balanceOf(cdep.address)
    # successful withdrawal
    chain.web3.testing.mine(100)
    assert chain.web3.eth.blockNumber > lockUntil
    chain.wait.for_receipt(
        cdep.transact({'from': owner_addr}).withdraw(owner_addr))
    assert 0 == cdep.call().balanceOf(owner_addr)
    # unsuccessful retry
    amnt = gntw.call().balanceOf(cdep.address)
    chain.wait.for_receipt(
        cdep.transact({'from': owner_addr}).withdraw(owner_addr))
    assert 0 == cdep.call().balanceOf(owner_addr)
    assert amnt == gntw.call().balanceOf(cdep.address)


def test_burn(chain):
    bn = chain.web3.eth.blockNumber
    lockUntil = bn+100
    owner_addr, oracle_addr, gnt, gntw, cdep = mysetup(chain)
    deposit_size = 100000
    burn_size = int(deposit_size / 2)
    do_deposit(chain, gnt, gntw, cdep, owner_addr, deposit_size, lockUntil)
    amnt = gntw.call().balanceOf(cdep.address)
    # not oracle
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': owner_addr}).burn(owner_addr, burn_size))
    assert amnt == gntw.call().balanceOf(cdep.address)
    # oracle
    chain.wait.for_receipt(
        cdep.transact({'from': oracle_addr}).burn(owner_addr, burn_size))
    assert amnt-burn_size == cdep.call().balanceOf(owner_addr)
    assert amnt-burn_size == gntw.call().balanceOf(cdep.address)


def test_reimburse(chain):
    bn = chain.web3.eth.blockNumber
    lockUntil = bn+100
    owner_addr, oracle_addr, gnt, gntw, cdep = mysetup(chain)
    other_addr = tester.accounts[1]
    deposit_size = 100000
    reimb_size = int(deposit_size / 2)
    do_deposit(chain, gnt, gntw, cdep, owner_addr, deposit_size, lockUntil)
    amnt = gntw.call().balanceOf(cdep.address)
    # not oracle
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            cdep.transact({'from': other_addr}).reimburse(owner_addr,
                                                          other_addr,
                                                          reimb_size))
    assert amnt == gntw.call().balanceOf(cdep.address)
    # oracle
    chain.wait.for_receipt(
        cdep.transact({'from': oracle_addr}).reimburse(owner_addr, other_addr,
                                                       reimb_size))
    assert amnt-reimb_size == cdep.call().balanceOf(owner_addr)
    assert amnt-reimb_size == gntw.call().balanceOf(cdep.address)
