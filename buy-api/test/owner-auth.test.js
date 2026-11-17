import test from "node:test";
import assert from "node:assert/strict";
import { issueOwnerChallenge, consumeOwnerChallenge, OWNER_WALLET } from "../src/owner-auth.js";

test("owner challenge is issued only to the configured inventory wallet", async () => {
  const writes=[];
  const db={prepare(sql){return {bind(...args){return {run:async()=>{writes.push({sql,args});return {meta:{changes:1}}}}}}}};
  await assert.rejects(()=>issueOwnerChallenge(db,"0x1111111111111111111111111111111111111111"),/owner_wallet_required/);
  const challenge=await issueOwnerChallenge(db,OWNER_WALLET,"orders:list","verified-orders");
  assert.ok(challenge.nonce);
  assert.ok(challenge.expiresAt>Date.now()/1000);
  assert.match(challenge.message,/SOBYA BUY OWNER AUTHORIZATION/);
  assert.equal(writes.length,1);
});

test("owner authorization fails closed for missing or invalid signatures", async () => {
  const db={prepare(sql){return {bind(){return {first:async()=>({
    nonce:"test-nonce",owner_address:OWNER_WALLET.toLowerCase(),action:"orders:list",context:"verified-orders",
    message:"SOBYA BUY OWNER AUTHORIZATION",expires_at:Math.floor(Date.now()/1000)+60
  }),run:async()=>({meta:{changes:1}})}}}}};
  await assert.rejects(()=>consumeOwnerChallenge(db,null,"orders:list","verified-orders"),/owner_auth_required/);
  await assert.rejects(()=>consumeOwnerChallenge(db,{
    address:OWNER_WALLET,nonce:"test-nonce",action:"orders:list",context:"verified-orders",signature:"0x"+"00".repeat(65)
  },"orders:list","verified-orders"),/owner_signature_invalid/);
});
