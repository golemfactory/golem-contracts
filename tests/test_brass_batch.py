import ethereum
from ethereum import tester
from ethereum.tester import TransactionFailed
from ethereum.utils import int_to_big_endian, zpad
from eth_utils import (
    encode_hex,
)
import functools
import pytest
import queue
from test_brass_concent import mysetup


def encode_payments(payments):
    args = []
    value_sum = 0
    for idx, v in payments:
        addr = ethereum.tester.accounts[idx]
        value_sum += v
        v = int(v)
        assert v < 2**96
        vv = zpad(int_to_big_endian(v), 12)
        mix = vv + addr
        assert len(mix) == 32
        print(encode_hex(mix), "v: ", v, "addr", encode_hex(addr))
        args.append(mix)
    return args, value_sum


def test_batch_transfer(chain):
    _, receiver_addr, gnt, gntb, cdep = mysetup(chain)
    eba0 = gntb.call().balanceOf(ethereum.tester.a0)
    eba1 = gntb.call().balanceOf(ethereum.tester.a1)
    eba2 = gntb.call().balanceOf(ethereum.tester.a2)
    eba3 = gntb.call().balanceOf(ethereum.tester.a3)
    eba4 = gntb.call().balanceOf(ethereum.tester.a4)
    payments, v = encode_payments([(1, 1), (2, 2), (3, 3), (4, 4)])

    # This dict is used to count events for given block hash
    # There is a quirk that same events can appear many times during
    # "blockchain reorganization" they will have different block hash though.
    eventNoForHash = {}
    q = queue.Queue()

    # Callback is called on separate thread so one need a queue to collect data
    def onBatchEvent(arg, eventsQueue):
        eventsQueue.put(arg)

    cbk = functools.partial(onBatchEvent, eventsQueue=q)
    gntb.on('BatchTransfer', None, cbk)

    # Closure time has to be in past, requestor is making payments for
    # already made obligations
    closure_time = chain.web3.eth.getBlock('latest')['timestamp']

    tx = chain.wait.for_receipt(gntb.transact({'from': ethereum.tester.a0}).batchTransfer(payments, closure_time))
    assert gntb.call().balanceOf(ethereum.tester.a1) == 1 + eba1
    assert gntb.call().balanceOf(ethereum.tester.a2) == 2 + eba2
    assert gntb.call().balanceOf(ethereum.tester.a3) == 3 + eba3
    assert gntb.call().balanceOf(ethereum.tester.a4) == 4 + eba4
    assert gntb.call().balanceOf(ethereum.tester.a0) == eba0 - v

    while not q.empty():
        try:
            batchEvent = q.get()
            assert chain.web3.eth.getBlock(batchEvent['blockNumber'])['timestamp'] >= batchEvent['args']['closureTime']
            if batchEvent['blockHash'] in eventNoForHash.keys():
                eventNoForHash[batchEvent['blockHash']] += 1
            else:
                eventNoForHash = {batchEvent['blockHash']: 0}
        except:
            assert False

    for entry in eventNoForHash:
        assert eventNoForHash[entry] == 3


def test_approve(chain):
    _, receiver_addr, gnt, gntb, cdep = mysetup(chain)
    user_addr = tester.accounts[0]
    chain.wait.for_receipt(
        gntb.transact({'from': user_addr}).approve(receiver_addr, 100))
    with pytest.raises(TransactionFailed):
        gntb.transact({'from': user_addr}).approve(receiver_addr, 200)


def test_batch_transfer_to_self(chain):
    _, receiver_addr, gnt, gntb, cdep = mysetup(chain)
    addr = ethereum.tester.a1
    payments, _ = encode_payments([(1, 1)])
    with pytest.raises(TransactionFailed):
        gntb.transact({'from': addr}).batchTransfer(payments, 123)


def test_batch_transfer_to_zero(chain):
    _, receiver_addr, gnt, gntb, cdep = mysetup(chain)
    user_addr = tester.accounts[0]
    addr = b'\0' * 20
    vv = zpad(int_to_big_endian(1), 12)
    mix = vv + addr
    payments = [mix]
    assert len(mix) == 32
    with pytest.raises(TransactionFailed):
        gntb.transact({'from': user_addr}).batchTransfer(payments, 123)


def test_empty_gntb_conversions(chain):
    _, receiver_addr, gnt, gntb, cdep = mysetup(chain)
    user_addr = tester.accounts[0]
    gate_address = gntb.call().getGateAddress(user_addr)
    assert gate_address
    gate_gnt_balance = gnt.call().balanceOf(gate_address)
    assert gate_gnt_balance == 0
    with pytest.raises(TransactionFailed):
        gntb.transact({'from': user_addr}).transferFromGate()

    gntb_balance = gntb.call().balanceOf(user_addr)
    assert gntb_balance > 0
    with pytest.raises(TransactionFailed):
        gntb.transact({'from': user_addr}).withdraw(0)
