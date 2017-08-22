# PoC contents
* *GNT* token  
* *GNTW* for missing parts of ERC-20 interface  
* *GNTDeposit* that implements timelocked deposits and deposit burning

All with basic smoke tests.

# Requirements
* python3 (for tests)

# Compiling and running tests
`$ virtualenv --python=$(which python3) venv`  
`$ . venv/bin/activate`  
`$ pip install -r requirements.txt`  
`$ populus compile`  
`$ pytest`  
