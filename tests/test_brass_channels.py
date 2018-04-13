import pytest
import ethereum.tester as tester
import ethereum
import ethereum.utils as utils
from ethereum.tester import TransactionFailed
from secp256k1 import PrivateKey
from test_brass_concent import mysetup, seconds
import eth_utils
from eth_utils import (
    event_signature_to_log_topic,
)


def test_close(chain):
    owner_addr, receiver_addr, gnt, gntb, cdep = mysetup(chain)
    pc = deploy_channels(chain, owner_addr, gntb)
    channel = prep_a_channel(chain, owner_addr, receiver_addr, gntb, pc)
    prep_a_channel(chain, owner_addr, receiver_addr, gntb, pc)
    # bad caller
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({'from': receiver_addr}).close(channel))
    assert pc.call().isLocked(channel)
    # unlock needed first
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({'from': owner_addr}).close(channel))
    topics = [owner_addr, receiver_addr]
    f_id = log_filter(chain, pc.address,
                      "TimeLocked(address, address, bytes32)", topics)
    chain.wait.for_receipt(
        pc.transact({'from': owner_addr}).unlock(channel))
    logs = get_logs(f_id)
    assert len(logs) == 1
    achannel = logs[0]["data"]
    assert achannel == eth_utils.encode_hex(channel)
    # bad caller
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({'from': receiver_addr}).close(channel))
    f_id = log_filter(chain, pc.address,
                      "Close(address, address, bytes32)", topics)
    # too early, still in close_delay period
    assert pc.call().isTimeLocked(channel)
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({'from': owner_addr}).close(channel))
    while pc.call().isTimeLocked(channel):
        chain.web3.testing.mine(1)
    # proper close
    chain.wait.for_receipt(
        pc.transact({'from': owner_addr}).close(channel))
    logs = get_logs(f_id)
    assert len(logs) == 1
    achannel = logs[0]["data"]
    assert achannel == eth_utils.encode_hex(channel)
    # can't withdraw from closed channel
    owner_priv = ethereum.tester.keys[9]
    V, ER, ES = sign_transfer(channel, owner_priv, receiver_addr, 10)
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({'from': receiver_addr}).withdraw(channel, 10,
                                                          V, ER, ES))


def test_withdraw(chain):
    owner_addr, _, gnt, gntb, cdep = mysetup(chain)
    owner_priv = ethereum.tester.keys[7]
    receiver_addr = tester.accounts[1]
    pc = deploy_channels(chain, owner_addr, gntb)
    channel = prep_a_channel(chain, owner_addr, receiver_addr, gntb, pc)

    def capacity():
        dep = pc.call().getDeposited(channel)
        wit = pc.call().getWithdrawn(channel)
        return dep - wit

    def shared_capacity():
        return gntb.call().balanceOf(pc.address)

    c_cap = capacity()
    sh_cap = shared_capacity()

    V, ER, ES = sign_transfer(channel, owner_priv, receiver_addr, 10)
    assert pc.call().isValidSig(channel, 10, V, ER, ES)
    # withdraw wrong amount
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({"from": receiver_addr}).withdraw(channel, 1000,
                                                          V, ER, ES))
    # withdraw wrong amount
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({"from": receiver_addr}).withdraw(channel, 5,
                                                          V, ER, ES))

    # use damaged signature
    ES1 = bytearray(ES)
    ES1[3] = (~ES1[3]) % 256  # bitwise not
    ES1 = bytes(ES1)
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({"from": receiver_addr}).withdraw(channel, 10,
                                                          V, ER, ES1))
    # successful withdrawal
    assert 10 <= shared_capacity()
    assert 10 <= capacity()
    assert pc.call().isValidSig(channel, 10, V, ER, ES)
    chain.wait.for_receipt(
        pc.transact({"from": receiver_addr}).withdraw(channel, 10, V, ER, ES))
    assert capacity() == c_cap - 10
    assert shared_capacity() == sh_cap - 10

    # reuse correctly signed cheque
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({"from": receiver_addr}).withdraw(channel, 10,
                                                          V, ER, ES))
    # try to double-spend by reversing order of applying cheques
    V, ER, ES = sign_transfer(channel, owner_priv, receiver_addr, 5)
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({"from": receiver_addr}).withdraw(channel, 5,
                                                          V, ER, ES))
    # get 10 more
    V, ER, ES = sign_transfer(channel, owner_priv, receiver_addr, 20)
    chain.wait.for_receipt(
        pc.transact({"from": receiver_addr}).withdraw(channel, 20,
                                                      V, ER, ES))
    assert capacity() == c_cap - 20
    assert shared_capacity() == sh_cap - 20


def test_forceClose(chain):
    owner_addr, receiver_addr, gnt, gntb, cdep = mysetup(chain)
    pc = deploy_channels(chain, owner_addr, gntb)
    channel = prep_a_channel(chain, owner_addr, receiver_addr, gntb, pc)
    # bad caller
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({'from': owner_addr}).forceClose(channel))
    topics = [owner_addr, receiver_addr]
    f_id = log_filter(chain, pc.address,
                      "ForceClose(address, address, bytes32)", topics)
    # proper caller
    chain.wait.for_receipt(
        pc.transact({'from': receiver_addr}).forceClose(channel))
    logs = get_logs(f_id)
    assert len(logs) == 1
    achannel = logs[0]["data"]
    assert achannel == eth_utils.encode_hex(channel)
    # duplicate call
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({'from': receiver_addr}).forceClose(channel))
    # can't withdraw from closed channel
    owner_priv = ethereum.tester.keys[9]
    V, ER, ES = sign_transfer(channel, owner_priv, receiver_addr, 10)
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({'from': receiver_addr}).withdraw(channel, 10,
                                                          V, ER, ES))


def test_onTokenReceived(chain):
    owner_addr, receiver_addr, gnt, gntb, cdep = mysetup(chain)
    pc = deploy_channels(chain, owner_addr, gntb)
    channel = prep_a_channel(chain, owner_addr, receiver_addr, gntb, pc)
    with pytest.raises(TransactionFailed):
        chain.wait.for_receipt(
            pc.transact({'from': owner_addr}).onTokenReceived(owner_addr,
                                                              123,
                                                              channel))


def sign_transfer(channel, owner_priv, receiver_addr, amount):
    # in Solidity: sha3(channel, bytes32(_value)):
    msghash = utils.sha3(channel + cpack(32, amount))
    assert len(msghash) == 32
    (V, R, S) = sign_eth(msghash, owner_priv)
    ER = cpack(32, R)
    ES = cpack(32, S)
    return V, ER, ES


# HELPERS
def a2t(address):
    return eth_utils.encode_hex(utils.zpad(address, 32))


def prep_a_channel(chain, owner_addr, receiver_addr, gntb, pc):
    topics = [owner_addr, receiver_addr]
    f_id = log_filter(chain, pc.address,
                      "NewChannel(address, address, bytes32)", topics)
    chain.wait.for_receipt(
        pc.transact({'from': owner_addr}).createChannel(receiver_addr))
    logs = get_logs(f_id)
    channel = logs[0]["data"]
    channel = eth_utils.decode_hex(channel[2:])

    thevalue = pc.call().getDeposited(channel)
    assert thevalue == 0

    thereceiver = pc.call().getReceiver(channel).lower()
    assert thereceiver == eth_utils.encode_hex(receiver_addr)

    theowner = pc.call().getOwner(channel).lower()
    assert theowner == eth_utils.encode_hex(owner_addr)

    assert 0 == pc.call().getDeposited(channel)
    deposit_size = 100000
    assert eth_utils.encode_hex(owner_addr) == \
        pc.call().getOwner(channel).lower()
    chain.wait.for_receipt(
        gntb.transact({'from': owner_addr}).transferAndCall(
            pc.address, deposit_size, channel))
    assert deposit_size == pc.call().getDeposited(channel)
    return channel


def log_filter(chain, address, signature, topics):
    bn = chain.web3.eth.blockNumber
    topics = topics[:]
    if topics is not None:
        for i in range(len(topics)):
            topics[i] = a2t(topics[i])
    # "LogAnonymous()"
    # "NewChannel(address, address, bytes32)"
    enc_sig = eth_utils.encode_hex(event_signature_to_log_topic(signature))
    topics.insert(0, enc_sig)
    obj = {
        'fromBlock': bn,
        'toBlock': "latest",
        'address': address,
        'topics': topics
    }
    return (chain, chain.web3.eth.filter(obj).filter_id, enc_sig)


def get_logs(f_id):
    chain, id, enc_sig = f_id
    logs = chain.web3.eth.getFilterLogs(id)

    def l(x):
        return (x["topics"][0]) == enc_sig

    lf = list(filter(l, logs))
    return lf


def deploy_channels(chain, factory_addr, gntb):
    args = [gntb.address, seconds(600)]
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
    return [bts >> i & 0xff for i in reversed(range(0, n*8, 8))]


def sign_eth(rawhash, priv):
    pk = PrivateKey(priv, raw=True)
    signature = pk.ecdsa_recoverable_serialize(
        pk.ecdsa_sign_recoverable(rawhash, raw=True)
    )
    signature = signature[0] + utils.bytearray_to_bytestr([signature[1]])
    v = utils.safe_ord(signature[64]) + 27
    r = utils.big_endian_to_int(signature[0:32])
    s = utils.big_endian_to_int(signature[32:64])
    return (v, r, s)
