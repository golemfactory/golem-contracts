const HelloWorld = artifacts.require("HelloWorld");

contract("HelloWorld", async accounts => {
  it("basic", async () => {
    let instance = await HelloWorld.deployed();
    let result = await instance.hi.call(42);
    assert.equal(43, result);
  });
});
