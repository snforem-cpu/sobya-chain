import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

// Run the SDK in a real Chromium page against the live SOBYA RPC.\nconst root = process.cwd();
const mime = {".html":"text/html",".js":"text/javascript",".css":"text/css",".png":"image/png"};
const server = createServer(async (req,res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url,"http://127.0.0.1").pathname);
    const file = normalize(join(root,pathname));
    if (!file.startsWith(root)) throw new Error("Invalid path");
    const body = await readFile(file);
    res.writeHead(200,{"content-type":mime[extname(file)] || "application/octet-stream","access-control-allow-origin":"*"});
    res.end(body);
  } catch { res.writeHead(404); res.end("Not found"); }
});
await new Promise(resolve=>server.listen(4173,"127.0.0.1",resolve));
let browser;
try {
  browser = await chromium.launch({headless:true});
  const page = await browser.newPage();
  const errors=[];
  page.on("pageerror",e=>errors.push(e.message));
  await page.goto("http://127.0.0.1:4173/proof-suite/verify-api/index.html");
  const result = await page.evaluate(async txHash => {
    const {createSobyaVerifyClient} = await import("./client.js");
    const client = createSobyaVerifyClient();
    return await client.verifyProof({txHash});
  }, "0x615604f8649ffd4f407e64e2eb14eb91a84720fd63d0dc4eaa17088647ed4206");
  if (!result.valid || result.match !== null || result.type !== "proof") throw new Error("Unexpected SDK result: "+JSON.stringify(result));
  if (errors.length) throw new Error("Browser errors: "+errors.join("; "));
  console.log("BROWSER SDK PASS",JSON.stringify({valid:result.valid,match:result.match,block:result.blockNumber,chainId:result.chainId}));
} finally {
  if (browser) await browser.close();
  await new Promise(resolve=>server.close(resolve));
}
