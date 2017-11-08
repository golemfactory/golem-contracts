from test_brass_oracle import mysetup
import ethereum
from ethereum.utils import to_string, sha3, privtoaddr, encode_hex
import rlp
from ethereum.transactions import Transaction

def test_create_gnt(chain):
    owner_addr, receiver_addr, gnt, gntw, cdep = mysetup(chain)
    faucet, _ = chain.provider.get_or_deploy_contract('Faucet',
                                                   deploy_args=[gnt.address])

    key = sha3(to_string(11))
    account = privtoaddr(key)

    ethereum.tester.accounts.append(account)
    ethereum.tester.keys.append(key)

    print("Balance of ", chain.web3.eth.getBalance(encode_hex(account)))

    tx = Transaction(
        nonce=chain.web3.eth.getTransactionCount(chain.web3.eth.coinbase),
        gasprice=chain.web3.eth.gasPrice,
        startgas=100000,
        to=encode_hex(account),
        value=4000000,
        data=b'',
    )

    tx.sign(ethereum.tester.k0)
    raw_tx = rlp.encode(tx)
    raw_tx_hex = chain.web3.toHex(raw_tx)
    chain.web3.eth.sendRawTransaction(raw_tx_hex)

    print("GNT Balance of ",gnt.call().balanceOf(encode_hex(account)))
    print("Balance of ",chain.web3.eth.getBalance(encode_hex(account)))
    faucet.transact({'from': account}).create()