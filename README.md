[![CircleCI](https://circleci.com/gh/golemfactory/golem-contracts.svg?style=shield)](https://circleci.com/gh/golemfactory/golem-contracts)

# PoC contents
* *GNT* token  
* *GNTW* for missing parts of ERC20 interface and ERC223 implementation  
* *GNTDeposit* that implements timelocked deposits and deposit burning
* *GNTPaymentChannels* for small payments to Consent

All with basic smoke tests.

# Requirements
* python3 (for tests)

# Compiling and running tests
`$ virtualenv --python=$(which python3) venv`  
`$ . venv/bin/activate`  
`$ pip install -r requirements.txt`  
`$ populus compile`  
`$ pytest`  

# Deployment
Activate venv
source venv/bin/activate

First test on populus test block chain

`python deploy.py --chain tester`

It there are no errors you may proceed with deployment on testnet.

But first run and synchronize full ethereum node
`geth --datadir \path\to\datadir --rinkeby`

Connect to geth with node console

`geth attach ipc://path/to/datadir/geth.ipc

On node console create account

`personal.newAccount("somePassword")`

This will return your eth address you it.

`eth.getBalance("yourEthAddress")`

It will yield 0, so you have to fund it, otherwise you want be able to deploy since gas is needed for contract deployment.
Luckly this is a rinkeby testnet and it has automated faucet. Go to:
https://www.rinkeby.io/#faucet
Follow instructions, use your just created eth address and watch how ethers are filling your account ;)

Now unlock your account to make some transactions.
This assume that you want to unlock first account from list, you can list accounts with:
`web3.personal.listAccounts`

`web3.personal.unlockAccount(web3.personal.listAccounts[0],"somePassword", 15000)`

Now you are ready to deploy on Rinkeby testnet

One small thing, update `populus.json` to show populus how you are connected to ethereum testnet:
In mentioned json file find key `rinkeby`, follow its values and find web3 -> eth -> `default_account` change it
to `yourEthAddress` just below there is provider -> settings -> `ipc_path` update path to point to your current geth socket
(same that you used to connect node console)

`python deploy.py --chain rinkeby --owner "yourEthAddress" --consent "yourEthAddress" --coldwallet "yourEthAddress"`

Note that consent address and cold wallet addres are to be discussed, for now pointing them to your deployment addres is all right. 
