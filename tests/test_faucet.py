from test_brass_oracle import mysetup
import ethereum
from ethereum.utils import to_string, sha3, privtoaddr, encode_hex
import ethereum.utils as utils
import rlp
from ethereum.transactions import Transaction

def test_create_gnt(chain):
    owner_addr, receiver_addr, gnt, gntw, cdep = mysetup(chain)
    faucet, _ = chain.provider.get_or_deploy_contract('Faucet',
                                                      deploy_args=[gnt.address])

    assert gnt.call().balanceOf(faucet.address) == 0
    chain.wait.for_receipt(gnt.transact({'from': encode_hex(ethereum.tester.a0)}).transfer(
        faucet.address, 1000 * utils.denoms.ether ))
    assert gnt.call().balanceOf(faucet.address) == 1000 * utils.denoms.ether
    key = sha3(to_string(11))
    account = privtoaddr(key)

    ethereum.tester.accounts.append(account)
    ethereum.tester.keys.append(key)

    assert chain.web3.eth.getBalance(encode_hex(account)) == 0
    previousA0 = chain.web3.eth.getBalance(encode_hex(ethereum.tester.a0))
    assert previousA0 > utils.denoms.ether

    tx = Transaction(
        nonce=chain.web3.eth.getTransactionCount(ethereum.tester.a0),
        gasprice=chain.web3.eth.gasPrice,
        startgas=100000,
        to=encode_hex(account),
        value=utils.denoms.ether,
        data=b'',
    )

    tx.sign(ethereum.tester.k0)
    raw_tx = rlp.encode(tx)
    raw_tx_hex = chain.web3.toHex(raw_tx)
    chain.web3.eth.sendRawTransaction(raw_tx_hex)

    assert gnt.call().balanceOf(faucet.address) == 1000 * utils.denoms.ether

    assert chain.web3.eth.getBalance(encode_hex(account)) == utils.denoms.ether

    assert gnt.call().decimals() == 18
    assert gnt.call().balanceOf(encode_hex(account)) == 0
    tx = chain.wait.for_receipt(
        faucet.transact({'from': encode_hex(account)}).create())
    assert gnt.call().balanceOf(encode_hex(account)) == 1000 * utils.denoms.ether
    assert gnt.call().balanceOf(faucet.address) == 0
