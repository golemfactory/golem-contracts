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
`$ python3 utils/deploy.py`
