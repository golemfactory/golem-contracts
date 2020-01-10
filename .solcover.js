module.exports = {
  skipFiles: [
    'BasicToken.sol',
    'BurnableToken.sol',
    'ERC20.sol',
    'ERC20Basic.sol',
    'Migrations.sol',
    'Ownable.sol',
    'SafeMath.sol',
    'StandardToken.sol',
  ],
  providerOptions: {
    '-k': 'istanbul'
  },
};
