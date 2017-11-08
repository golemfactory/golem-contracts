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

    print("faucet GNT Balance ", gnt.call().balanceOf(faucet.address))
    chain.wait.for_receipt(gnt.transact({'from': encode_hex(ethereum.tester.a0)}).transfer(
        faucet.address, 10**18 ))
    print("faucet GNT Balance ",
          gnt.call().balanceOf(faucet.address))
    key = sha3(to_string(11))
    account = privtoaddr(key)

    ethereum.tester.accounts.append(account)
    ethereum.tester.keys.append(key)

    print("ETH Balance of account : ", chain.web3.eth.getBalance(encode_hex(account)))
    print("ETH Balance of a0 : ", chain.web3.eth.getBalance(encode_hex(ethereum.tester.a0)))

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

    print("ETH Balance of account ", chain.web3.eth.getBalance(encode_hex(account)))
    print("ETH Balance of a0 : ", chain.web3.eth.getBalance(encode_hex(ethereum.tester.a0)))

    print("decimals: ", gnt.call().decimals())

    print("GNT Balance of account", gnt.call().balanceOf(encode_hex(account)))
    print("GNT Balance of account", faucet.call().mybalance(encode_hex(account)))
    print("GNT Balance of faucet", faucet.call().mybalance(faucet.address))
    print("GNT goal", faucet.call().goal())
    tx = chain.wait.for_receipt(
        faucet.transact({'from': account}).create())
    print("tx: {}".format(tx))
    print("GNT Balance of account", gnt.call().balanceOf(encode_hex(account)))
