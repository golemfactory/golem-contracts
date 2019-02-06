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
