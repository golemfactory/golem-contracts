"""Deploy Golem/Consent contracts on Mainnet/Rinkeby/Tester

A simple Python script to deploy contracts and then do a smoke test for them.
"""
import click
from populus import Project
from populus.utils.wait import wait_for_transaction_receipt
import ethereum.utils as utils


def deploy_or_get_gnt(chain_name, chain, owner):
    if chain_name == "mainnet":
        raise Exception("not handled yet")
        # addr = "0xa74476443119A942dE498590Fe1f2454d7D4aC0d"
        # return chain.web3.eth.getCode(addr)
    if chain_name == "rinkeby":
        Token = chain.provider.get_contract_factory('GolemNetworkToken')
        token_address = "0x144B536A3314ff95D89e0939Cd2D1ae4e710933E"
        tgnt = Token(address=token_address)
        assert "tGNT" == tgnt.call().symbol()
        print("tGNT already deployed")
        return tgnt
    bn = chain.web3.eth.blockNumber
    start, finish = bn+20, bn+10000
    # not on mainnet, deploy gnt with junk migration address
    gnt = deploy_tgnt(chain, owner, owner, start, finish)
    return gnt


def deploy_tgnt(chain, factory_addr, migration_addr, start, finish):
    args = [factory_addr, migration_addr, start, finish]
    print("GolemNetworkToken deployment args: {}".format(args))
    Token = chain.provider.get_contract_factory('GolemNetworkToken')
    txhash = Token.deploy(transaction={'from': factory_addr}, args=args)
    receipt = check_succesful_tx(chain.web3, txhash, timeout=300)
    token_address = receipt['contractAddress']
    tgnt = Token(address=token_address)
    chain.wait.for_block(block_number=start+1)
    return tgnt


def rinkeby_fund_and_finalize(chain, tgnt, factory_addr):
    current = tgnt.call().totalTokens()
    tcr = tgnt.call().tokenCreationRate()
    target = tgnt.call().tokenCreationCap()
    v = int((target - current) / tcr)
    if v > 0:
        bn = chain.web3.eth.blockNumber
        assert bn >= tgnt.call().fundingStartBlock()
        print("Funding not yet done: {}".format(v))
        assert tgnt.call().funding()
        assert tgnt.call().tokenCreationRate() == 10000000000
        assert v < chain.web3.eth.getBalance(factory_addr)
        chain.wait.for_receipt(
            tgnt.transact({'value': v, 'from': factory_addr}).create())
    else:
        print("tGNT already funded")
    if(tgnt.call().funding()):
        chain.wait.for_receipt(
            tgnt.transact().finalize())
        print("Funding finalized")
    else:
        print("Funding already finalized")


def deploy_gntw(chain_name, chain, gnt, owner):
    GNTW = chain.provider.get_contract_factory('GolemNetworkTokenWrapped')
    if chain_name == "rinkeby":
        gntw_address = "0xF3140A97820fB0f9670eF32875E6E6a75F6e16e4"
        gntw = GNTW(address=gntw_address)
        assert "GNTW" == gntw.call().symbol()
        assert gnt.address == gntw.call().GNT()
        print("GNTW already deployed")
        return gntw
    args = [gnt.address]
    print("GNTW deployment args: {}".format(args))
    txhash = GNTW.deploy(transaction={'from': owner}, args=args)
    receipt = check_succesful_tx(chain.web3, txhash, timeout=300)
    token_address = receipt['contractAddress']
    gntw = GNTW(address=token_address)
    assert "GNTW" == gntw.call().symbol()
    print("GNTW deployed")
    return gntw


def fund_gntw(chain, addr, gnt, gntw):
    v = 10 * utils.denoms.finney
    assert v < gnt.call().balanceOf(addr)
    chain.wait.for_receipt(
        gntw.transact({'from': addr}).createPersonalDepositAddress())
    PDA = gntw.call().getPersonalDepositAddress(addr)
    chain.wait.for_receipt(
        gnt.transact({'from': addr}).transfer(PDA, v))
    assert v == gnt.call().balanceOf(PDA)
    chain.wait.for_receipt(
        gntw.transact({'from': addr}).processDeposit())
    assert v == gntw.call().balanceOf(addr)


def oraclized_deposit(chain_name, chain, factory_addr, consent, coldwallet, token, delay):
    cdep = deploy_oraclized_deposit(chain_name, chain, factory_addr, consent,
                                    coldwallet, token, delay)
    check_oraclized_deposit(cdep, token, consent, coldwallet, delay)
    return cdep


def check_oraclized_deposit(cdep, gntw, consent, coldwallet, delay):
    assert gntw.address == cdep.call().token()
    assert consent == cdep.call().oracle()
    assert coldwallet == cdep.call().coldwallet()
    assert delay == cdep.call().withdrawal_delay()


def deploy_oraclized_deposit(chain_name, chain, factory_addr, consent, coldwallet, token, delay):
    CDEP = chain.provider.get_contract_factory('GNTDeposit')
    if (chain_name == "rinkeby"):
        cdep_address = "0x44700ACFDf6EE9BC69698E3E818876cC7c05C4A1"
        cdep = CDEP(address=cdep_address)
        print("GNTDeposit already deployed!")
        return cdep
    args = [token.address, consent, coldwallet, delay]
    print("deploying GNTDeposit: {}".format(args))
    txhash = CDEP.deploy(transaction={'from': factory_addr}, args=args)
    receipt = check_succesful_tx(chain.web3, txhash, timeout=300)
    token_address = receipt['contractAddress']
    cdep = CDEP(address=token_address)
    return cdep


def deploy_all_the_things(chain_name, chain, gnt, owner, consent, coldwallet):
    gntw = deploy_gntw(chain_name, chain, gnt, owner)
    # fund_gntw(chain, owner, gnt, gntw)
    cdep = oraclized_deposit(chain_name, chain, owner, consent,
                             coldwallet, gntw, lock_time())
    return gntw, cdep


def lock_time():
    return 7 * 24 * 60 * 60


def get_default_account(chain_name, chain):
    if chain_name == "tester":
        print("accs: {}".format(chain.web3.eth.accounts))
        defacc = chain.web3.eth.accounts[0]
        return (defacc, defacc, defacc)
    if chain_name == "temp":
        defacc = chain.web3.eth.accounts[0]
        print("accs: {}".format(defacc))
        return (defacc, defacc, defacc)
    defacc = chain.web3.eth.defaultAccount
    return (defacc, defacc, defacc)


def params_check(accs):
    all_none = all(v is None for v in accs)
    all_set = all(v is not None for v in accs)
    msg = "Owner, consent and coldwallet should all be set or all be omitted"
    assert all_none or all_set, msg


def check_succesful_tx(web3, txid, timeout=180):
    """See if transaction went through (Solidity code did not throw).

    :return: Transaction receipt
    """
    # http://ethereum.stackexchange.com/q/6007/620
    receipt = wait_for_transaction_receipt(web3, txid, timeout=timeout)
    txinfo = web3.eth.getTransaction(txid)

    # EVM has only one error mode and it's consume all gas
    print("txgas: {}, gasUsed: {}".format(txinfo["gas"], receipt["gasUsed"]))
    assert txinfo["gas"] != receipt["gasUsed"]
    return receipt


@click.command()
@click.option('--chain', "chain_name", default="tester",
              type=click.Choice(["tester", "temp", "rinkeby", "mainnet"]),
              help='Chain to deploy to.')
@click.option('--owner', help="Account that will deploy contracts.")
@click.option('--consent',
              help="Consent operational account, holds small amounts of ETH/GNT.")
@click.option('--coldwallet',
              help="Consent account that will receive payments.")
def main(chain_name, owner, consent, coldwallet):
    project = Project()
    params_check([owner, consent, coldwallet])
    # This is configured in populus.json
    if (chain_name != "testnet"):
        msg = "Make sure {} chain is running, you can connect to it, \
        or you'll get timeout"
        print(msg.format(chain_name))
    with project.get_chain(chain_name) as chain:
        if (owner is None):
            owner, consent, coldwallet = get_default_account(chain_name, chain)
        # deploy_greeter(chain_name, chain, owner)
        gnt = deploy_or_get_gnt(chain_name, chain, owner)
        rinkeby_fund_and_finalize(chain, gnt, owner)
        deploy_all_the_things(chain_name, chain, gnt, owner, consent, coldwallet)
        print("All done! Enjoy your decentralized future.")


if __name__ == "__main__":
    main()
