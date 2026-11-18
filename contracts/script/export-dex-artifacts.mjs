import fs from "node:fs";
import crypto from "node:crypto";

const root = new URL("../../", import.meta.url);
const contractsDir = new URL("../out/", import.meta.url);
const outputDir = new URL("../../dex/deploy/", import.meta.url);
const names = ["WSOBY", "SobyaV2Factory", "SobyaV2Router"];
const sourceCommit = process.env.GITHUB_SHA;
if (!sourceCommit || !/^[0-9a-f]{40}$/i.test(sourceCommit)) {
  throw new Error("GITHUB_SHA must be a full commit SHA");
}
const contracts = {};
for (const name of names) {
  const artifactPath = new URL(`${name}.sol/${name}.json`, contractsDir);
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));
  const rawBytecode = artifact.bytecode?.object;
  const rawDeployedBytecode = artifact.deployedBytecode?.object;
  const bytecode = typeof rawBytecode === "string" ? (rawBytecode.startsWith("0x") ? rawBytecode : "0x" + rawBytecode) : rawBytecode;
  const deployedBytecode = typeof rawDeployedBytecode === "string" ? (rawDeployedBytecode.startsWith("0x") ? rawDeployedBytecode : "0x" + rawDeployedBytecode) : rawDeployedBytecode;
  if (!Array.isArray(artifact.abi) || typeof bytecode !== "string" ||
      !/^0x[0-9a-f]+$/i.test(bytecode) || typeof deployedBytecode !== "string" ||
      !/^0x[0-9a-f]+$/i.test(deployedBytecode)) {
    throw new Error(`Invalid Foundry artifact for ${name}`);
  }
  contracts[name] = {
    abi: artifact.abi,
    bytecode,
    deployedBytecode,
    bytecodeSha256: crypto.createHash("sha256").update(bytecode.toLowerCase()).digest("hex"),
    deployedBytecodeSha256: crypto.createHash("sha256").update(deployedBytecode.toLowerCase()).digest("hex")
  };
}
const bundle = {
  schemaVersion: 1,
  chainId: 357812033857,
  sourceCommit,
  compiler: "solc 0.8.24",
  optimizer: { enabled: true, runs: 200 },
  contracts
};
fs.mkdirSync(outputDir, { recursive: true });
fs.writeFileSync(new URL("artifacts.json", outputDir), JSON.stringify(bundle, null, 2) + "\n");
console.log("Exported verified build inputs for:", names.join(", "));
