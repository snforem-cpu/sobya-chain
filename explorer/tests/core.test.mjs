import test from "node:test";
import assert from "node:assert/strict";
import { ADDRESS_RE, CHAIN_ID, CHAIN_HEX, HASH_RE, classifySearch, formatSoby, shortHash, toDecimal } from "../core.js";

test("SOBYA network constants are exact", () => {
  assert.equal(CHAIN_ID, 357812033857n);
  assert.equal(CHAIN_HEX, "0x534f425941");
});
test("classifies transaction hashes, addresses and block heights", () => {
  const hash = "0x" + "a".repeat(64);
  const address = "0x" + "b".repeat(40);
  assert.match(hash, HASH_RE);
  assert.match(address, ADDRESS_RE);
  assert.equal(classifySearch(hash).type, "transaction");
  assert.equal(classifySearch(address).type, "address");
  assert.deepEqual(classifySearch("12345"), { type: "block", value: "12345" });
});
test("rejects malformed search values", () => {
  assert.throws(() => classifySearch("0x1234"), /valid transaction hash/);
  assert.throws(() => classifySearch("-1"), /valid transaction hash/);
  assert.throws(() => classifySearch("1.2"), /valid transaction hash/);
});
test("formats native currency without floating point loss", () => {
  assert.equal(formatSoby("1000000000000000000"), "1 SOBY");
  assert.equal(formatSoby("1234567890123456789"), "1.234567 SOBY");
  assert.equal(formatSoby("0"), "0 SOBY");
});
test("formats hex quantities and abbreviates long hashes", () => {
  assert.equal(toDecimal("0x2a"), "42");
  assert.equal(shortHash("0x" + "a".repeat(64)), "0xaaaaaaaaaa…aaaaaaaaaa");
});
