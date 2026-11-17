import test from "node:test";
import assert from "node:assert/strict";
import { verifyEvmPayment, verifySolPayment, verifyNativeSobyPayout, paymentNetworkConfig } from "../src/payment-verification.js";

const hash = "0x" + "a".repeat(64);
const sender = "0x1111111111111111111111111111111111111111";
const recipient = "0x15f94a243Ed60536Db51aA993A67d3F2Ea03f60f";
const topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef";
const word = value => "0x" + BigInt(value).toString(16).padStart(64, "0");
const addrTopic = value => "0x" + value.slice(2).toLowerCase().padStart(64, "0");

function mockFetch(responses) {
  let i = 0;
  return async () => new Response(JSON.stringify({ result: responses[i++] }), {
    status: 200, headers: { "content-type": "application/json" },
  });
}

test("network configuration requires the agreed confirmation depths", () => {
  assert.equal(paymentNetworkConfig.ETH_ETHEREUM.confirmations, 12);
  assert.equal(paymentNetworkConfig.USDT_ETHEREUM.decimals, 6);
  assert.equal(paymentNetworkConfig.BNB_BSC.confirmations, 15);
  assert.equal(paymentNetworkConfig.SOL_SOLANA.commitment, "finalized");
});

test("verifies an exact confirmed native ETH transfer", async () => {
  const receipt = { status: "0x1", blockNumber: "0x64", logs: [] };
  const tx = { chainId: "0x1", from: sender, to: recipient, value: "0xde0b6b3a7640000" };
  const result = await verifyEvmPayment({
    asset: "ETH_ETHEREUM", txHash: hash, expectedAmount: "1000000000000000000",
    expectedSender: sender, fetchImpl: mockFetch([receipt, tx, "0x6f", { timestamp: "0x6553f100" }]),
  });
  assert.equal(result.verified, true);
  assert.equal(result.confirmations, 12);
});

test("rejects an EVM payment with insufficient confirmations", async () => {
  const receipt = { status: "0x1", blockNumber: "0x64", logs: [] };
  const tx = { chainId: "0x1", from: sender, to: recipient, value: "0xde0b6b3a7640000" };
  await assert.rejects(() => verifyEvmPayment({
    asset: "ETH_ETHEREUM", txHash: hash, expectedAmount: "1000000000000000000",
    expectedSender: sender, fetchImpl: mockFetch([receipt, tx, "0x6e", { timestamp: "0x6553f100" }]),
  }), /payment_not_final/);
});

test("rejects an EVM payment to a different recipient", async () => {
  const receipt = { status: "0x1", blockNumber: "0x64", logs: [] };
  const tx = { chainId: "0x1", from: sender, to: "0x2222222222222222222222222222222222222222", value: "0xde0b6b3a7640000" };
  await assert.rejects(() => verifyEvmPayment({
    asset: "ETH_ETHEREUM", txHash: hash, expectedAmount: "1000000000000000000",
    expectedSender: sender, fetchImpl: mockFetch([receipt, tx, "0x80", { timestamp: "0x6553f100" }]),
  }), /wrong_payment_recipient/);
});

test("verifies the exact USDT Transfer log and token contract", async () => {
  const token = "0xdAC17F958D2ee523a2206206994597C13D831ec7";
  const receipt = { status: "0x1", blockNumber: "0x64", logs: [{
    address: token, topics: [topic, addrTopic(sender), addrTopic(recipient)], data: word(2500000),
  }] };
  const tx = { chainId: "0x1", from: sender, to: token, value: "0x0" };
  const result = await verifyEvmPayment({
    asset: "USDT_ETHEREUM", txHash: hash, expectedAmount: "2500000",
    expectedSender: sender, fetchImpl: mockFetch([receipt, tx, "0x80", { timestamp: "0x6553f100" }]),
  });
  assert.equal(result.verified, true);
  assert.equal(result.amountBaseUnits, "2500000");
});

test("verifies the exact finalized native SOL transfer", async () => {
  const fetchImpl = async () => new Response(JSON.stringify({ result: {
    slot: 99, meta: { err: null, confirmationStatus: "finalized" },
    transaction: { message: { instructions: [{
      program: "system", parsed: { type: "transfer", info: {
        source: "11111111111111111111111111111111",
        destination: "ACTkwKD9ZhHYgRSEoM7QWvp5ig1cUxDo3gMzB55rocdk",
        lamports: 1000000000,
      }},
    }] }},
  }}), { status: 200 });
  const result = await verifySolPayment({
    signature: "5".repeat(88), expectedAmount: "1000000000",
    expectedSender: "11111111111111111111111111111111", fetchImpl,
  });
  assert.equal(result.verified, true);
  assert.equal(result.commitment, "finalized");
});


test("verifies exact native SOBY payout from the inventory wallet on SOBYA Mainnet", async () => {
  const inventory = "0xebdb899fFE84a89e1d576964b640491c135651AD";
  const buyer = "0x2222222222222222222222222222222222222222";
  const receipt = { status: "0x1", blockNumber: "0x64", logs: [] };
  const tx = {
    chainId: "0x534f425941", from: inventory, to: buyer,
    value: "0xde0b6b3a7640000",
  };
  const result = await verifyNativeSobyPayout({
    txHash: hash, expectedAmount: "1000000000000000000",
    expectedBuyer: buyer, fetchImpl: mockFetch([receipt, tx, "0x6f"]),
  });
  assert.equal(result.verified, true);
  assert.equal(result.confirmations, 12);
  assert.equal(result.amountBaseUnits, "1000000000000000000");
});

test("rejects native SOBY payout signed by a wallet other than the inventory wallet", async () => {
  const receipt = { status: "0x1", blockNumber: "0x64", logs: [] };
  const tx = {
    chainId: "0x534f425941", from: sender,
    to: "0x2222222222222222222222222222222222222222",
    value: "0xde0b6b3a7640000",
  };
  await assert.rejects(() => verifyNativeSobyPayout({
    txHash: hash, expectedAmount: "1000000000000000000",
    expectedBuyer: tx.to, fetchImpl: mockFetch([receipt, tx, "0x80", { timestamp: "0x6553f100" }]),
  }), /wrong_payout_sender/);
});
