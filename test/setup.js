const GolemNetworkToken = artifacts.require("GolemNetworkToken");
const GolemNetworkTokenBatching = artifacts.require("GolemNetworkTokenBatching");
const GNTDeposit = artifacts.require("GNTDeposit");
const Faucet = artifacts.require("Faucet");

async function deployGntAndFaucet(golemfactory) {
  let currentBlock = await web3.eth.getBlockNumber();
  let gnt = await GolemNetworkToken.new(
    golemfactory,
    golemfactory,
    currentBlock + 2,
    currentBlock + 3,
  );

  let tcr = await gnt.tokenCreationRate.call();
  let tcc = await gnt.tokenCreationCap.call();
  let requiredEth = tcc / tcr;
  await gnt.create({from: golemfactory, value: requiredEth});
  await gnt.finalize();

  assert.isFalse(await gnt.funding.call());

  faucet = await Faucet.new(gnt.address);
  await gnt.transfer(faucet.address, tcc, {from: golemfactory});

  return [gnt, faucet];
}

async function deployGntb(gntAddress) {
  return await GolemNetworkTokenBatching.new(gntAddress);
}

async function convertGnt(address, amount, gnt, gntb) {
  let gateAddress = await gntb.getGateAddress(address);
  if (gateAddress == '0x' + '0'.repeat(40)) {
    await gntb.openGate({from: address});
    gateAddress = await gntb.getGateAddress(address);
  }
  await gnt.transfer(gateAddress, amount, {from: address});
  await gntb.transferFromGate({from: address});
}

async function createGntb(address, gnt, gntb, faucet) {
  await faucet.create({from: address});
  let amount = await gnt.balanceOf(address);
  await convertGnt(address, amount, gnt, gntb);
}

async function deployAll(golemfactory, concent, withdrawalDelay) {
  let [gnt, faucet] = await deployGntAndFaucet(golemfactory);
  let gntb = await deployGntb(gnt.address);
  let gntdeposit = await GNTDeposit.new(
    gntb.address,
    concent,
    concent,
    withdrawalDelay,
    {from: golemfactory},
  );
  return [gnt, faucet, gntb, gntdeposit];
}

module.exports = {
  deployGntAndFaucet,
  deployGntb,
  deployAll,
  convertGnt,
  createGntb,
}
