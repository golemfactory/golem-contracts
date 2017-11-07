import ethereum
from ethereum.utils import int_to_big_endian, zpad
from eth_utils import (
    encode_hex,
)
import time
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
    closure_time = int(time.time())
    gntw.transact({'from': ethereum.tester.a0}).batchTransfer(payments,
                                                              closure_time)
    assert gntw.call().balanceOf(ethereum.tester.a1) == 1 + eba1
    assert gntw.call().balanceOf(ethereum.tester.a2) == 2 + eba2
    assert gntw.call().balanceOf(ethereum.tester.a3) == 3 + eba3
    assert gntw.call().balanceOf(ethereum.tester.a4) == 4 + eba4
    assert gntw.call().balanceOf(ethereum.tester.a0) == eba0 - v
