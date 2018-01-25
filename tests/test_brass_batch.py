import ethereum
from ethereum.utils import int_to_big_endian, zpad
from eth_utils import (
    encode_hex,
)
import functools
import queue
from test_brass_oracle import mysetup


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
    owner_addr, receiver_addr, gnt, gntw, cdep = mysetup(chain)
    eba0 = gntw.call().balanceOf(ethereum.tester.a0)
    eba1 = gntw.call().balanceOf(ethereum.tester.a1)
    eba2 = gntw.call().balanceOf(ethereum.tester.a2)
    eba3 = gntw.call().balanceOf(ethereum.tester.a3)
    eba4 = gntw.call().balanceOf(ethereum.tester.a4)
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
    gntw.on('BatchTransfer', None, cbk)

    # Closure time has to be in past, requestor is making payments for
    # already made obligations
    closure_time = chain.web3.eth.getBlock('latest')['timestamp']

    tx = chain.wait.for_receipt(gntw.transact({'from': ethereum.tester.a0}).batchTransfer(payments, closure_time))
    assert gntw.call().balanceOf(ethereum.tester.a1) == 1 + eba1
    assert gntw.call().balanceOf(ethereum.tester.a2) == 2 + eba2
    assert gntw.call().balanceOf(ethereum.tester.a3) == 3 + eba3
    assert gntw.call().balanceOf(ethereum.tester.a4) == 4 + eba4
    assert gntw.call().balanceOf(ethereum.tester.a0) == eba0 - v

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
