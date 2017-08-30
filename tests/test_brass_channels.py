import pytest
import ethereum.utils as utils
from ethereum.tester import TransactionFailed
from test_brass_oracle import mysetup, seconds
import eth_utils
from eth_utils import (
    event_signature_to_log_topic,
)


def test_close(chain):
    owner_addr, oracle_addr, gnt, gntw, cdep = mysetup(chain)
    pc = deploy_channels(chain, owner_addr, gntw)
    channel = prep_a_channel(chain, owner_addr, oracle_addr, gntw, pc)
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({'from': owner_addr}).close(channel))
    topics = [owner_addr, oracle_addr]
    f_id = log_filter(chain, pc.address,
                      "Unlock(address, address, bytes32)", topics)
    chain.wait.for_receipt(
        pc.transact({'from': owner_addr}).unlock(channel))
    logs = chain.web3.eth.getFilterLogs(f_id)
    assert len(logs) == 1
    achannel = logs[0]["data"]
    assert achannel == eth_utils.encode_hex(channel)

# def test_withdraw(chain):
#     pass
# # in Solidity: sha3(sha3(secret), bytes32(_value)):
# msghash = utils.sha3(utils.sha3(secret) + cpack(32, value))
# assert len(msghash) == 32
# (V, R, S) = sign_eth(msghash, r_priv)
# ER = cpack(32, R)
# ES = cpack(32, S)


# def test_create(chain):
#     owner_addr, oracle_addr, gnt, gntw, cdep = mysetup(chain)
#     pc = deploy_channels(chain, owner_addr, gntw)
#     prep_a_channel(chain, owner_addr, oracle_addr, gntw, pc)


# HELPERS
def a2t(address):
    return eth_utils.encode_hex(utils.zpad(address, 32))


def prep_a_channel(chain, owner_addr, payee_addr, gntw, pc):
    topics = [owner_addr, payee_addr]
    f_id = log_filter(chain, pc.address,
                      "NewChannel(address, address, bytes32)", topics)
    chain.wait.for_receipt(
        pc.transact({'from': owner_addr}).createChannel(payee_addr))
    logs = chain.web3.eth.getFilterLogs(f_id)
    channel = logs[0]["data"]
    print("channel: {}".format(channel))
    channel = eth_utils.decode_hex(channel[2:])

    chain.web3.testing.mine(1)
    isValid = pc.call().isValid(channel)
    assert isValid

    thevalue = pc.call().value(channel)
    assert thevalue == 0

    thepayee = pc.call().getPayee(channel)
    assert thepayee == eth_utils.encode_hex(payee_addr)

    theowner = pc.call().getOwner(channel)
    assert theowner == eth_utils.encode_hex(owner_addr)

    assert 0 == pc.call().value(channel)
    deposit_size = 1234567
    chain.wait.for_receipt(
        gntw.transact({'from': owner_addr}).approve(pc.address, deposit_size))
    chain.wait.for_receipt(
        pc.transact({'from': owner_addr}).fund(channel, deposit_size))
    assert deposit_size == pc.call().value(channel)
    assert pc.call().isValid(channel)
    assert pc.call({'from': owner_addr}).isMine(channel)
    return channel


def log_filter(chain, address, signature, topics):
    bn = chain.web3.eth.blockNumber
    if topics is not None:
        for i in range(len(topics)):
            topics[i] = a2t(topics[i])
    # "LogAnonymous()"
    # "NewChannel(address, address, bytes32)"
    enc_sig = eth_utils.encode_hex(event_signature_to_log_topic(signature))
    # enc_sig2 = rlp.utils.encode_hex(event_signature_to_log_topic(signature))
    # assert enc_sig == enc_sig2
    print("{} -> {}".format(signature, enc_sig))
    topics = topics[:]
    topics.insert(0, enc_sig)
    obj = {
        'fromBlock': bn,
        'toBlock': "latest",
        'address': address,
        'topics': topics
    }
    return chain.web3.eth.filter(obj).filter_id


# def get_logs(rcpt, signature, topics):
#     print("pytopics: {}".format(topics))
#     return list(filter(lambda x: x["topics"] == topics, rcpt.logs))


# def get_data(eth_log):
#     d = eth_log["data"]
#     n = 66 # length of hex_encoded string of 32 bytes
#     return [d[i:i+66] for i in range(0, len(d), n)]


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
