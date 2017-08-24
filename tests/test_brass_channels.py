from rlp.utils import encode_hex
import ethereum.utils as utils
from ethereum.tester import TransactionFailed
from test_brass_oracle import mysetup, seconds
from eth_utils import (
    encode_hex,
    event_signature_to_log_topic,
)


def a2t(address):
    return encode_hex(utils.zpad(address, 32))


def test_close(chain):
    owner_addr, oracle_addr, gnt, gntw, cdep = mysetup(chain)
    pc = deploy_channels(chain, owner_addr, gntw)
    # pc_cap = 150 * utils.denoms.ether
    rcpt = chain.wait.for_receipt(
        pc.transact({'from': owner_addr}).createChannel(oracle_addr))
    print("rcpt: {}".format(rcpt))
    topics = [a2t(owner_addr), a2t(oracle_addr)]
    logs = get_logs(rcpt, "NewChannel(address, address, bytes32)", topics)
    assert len(logs) == 1
    entries = get_data(logs[0])
    print("entries: {}".format(entries))
    channel, = entries
    assert False
    # # in Solidity: sha3(sha3(secret), bytes32(_value)):
    # msghash = utils.sha3(utils.sha3(secret) + cpack(32, value))
    # assert len(msghash) == 32
    # (V, R, S) = sign_eth(msghash, r_priv)
    # ER = cpack(32, R)
    # ES = cpack(32, S)


def get_logs(rcpt, signature, topics):
    # "LogAnonymous()"
    # "NewChannel(address, address, bytes32)"
    enc_sig = encode_hex(event_signature_to_log_topic(signature))
    topics = topics[:]
    topics.insert(0, enc_sig)
    print("pytopics: {}".format(topics))
    return list(filter(lambda x: x["topics"] == topics, rcpt.logs))


def get_data(eth_log):
    d = eth_log["data"]
    n = 66 # length of hex_encoded string of 32 bytes
    return [d[i:i+66] for i in range(0, len(d), n)]


def deploy_channels(chain, factory_addr, gntw):
    args = [gntw.address, seconds(30)]
    pc, tx = chain.provider.get_or_deploy_contract('GNTPaymentChannels',
                                                   deploy_transaction={
                                                       'from': factory_addr
                                                   },
                                                   deploy_args=args)
    chain.wait.for_receipt(tx)
    return pc


def cpack(n, bts):
    """Packs int into bytesXX"""
    import struct
    fmt = "!{}B".format(n)
    return struct.pack(fmt, *tobyteslist(n, bts))


def tobyteslist(n, bts):
    return [ bts >> i & 0xff for i in reversed(range(0, n*8, 8)) ]
