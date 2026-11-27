import { CHAIN_HEX, RPC_URL } from "./core.js";
export function createRpc({ fetchImpl = globalThis.fetch, url = RPC_URL } = {}) {
  let id = 0;
  async function request(method, params = []) {
    const response = await fetchImpl(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: ++id, method, params })
    });
    if (!response.ok) throw new Error("RPC returned HTTP " + response.status + ".");
    const body = await response.json();
    if (body.error) throw new Error(body.error.message || "SOBYA RPC request failed.");
    if (!Object.prototype.hasOwnProperty.call(body, "result")) throw new Error("Malformed JSON-RPC response.");
    return body.result;
  }
  async function assertNetwork() {
    const chain = await request("eth_chainId");
    if (String(chain).toLowerCase() !== CHAIN_HEX.toLowerCase()) throw new Error("The RPC endpoint is not connected to SOBYA Mainnet.");
    return chain;
  }
  return Object.freeze({ request, assertNetwork });
}
