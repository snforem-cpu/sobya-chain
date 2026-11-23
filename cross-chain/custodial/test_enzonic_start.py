import json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import enzonic_start

def disabled_config():
    return {"mode":"custodial-inventory", "featureEnabled":False, "depositWatchEnabled":False, "networks":{"ethereum":{"enabled":False},"sobya":{"enabled":False}}, "api":{"enabled":True,"host":"127.0.0.1","port":8080,"allowedOrigin":"https://snforem-cpu.github.io","gatewayTokenEnv":"SOBYA_GATEWAY_TOKEN"}}

class EnzonicLauncherTests(unittest.TestCase):
    def test_bootstraps_only_disabled_local_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/"config.example.json").write_text(json.dumps(disabled_config()),encoding="utf-8")
            old=Path.cwd()
            with patch.object(enzonic_start,"HERE",root), patch.dict(os.environ,{},clear=True), patch("custodial_runtime.main",return_value=0):
                try:
                    self.assertEqual(enzonic_start.main(),0)
                    cfg=json.loads((root/"config.json").read_text(encoding="utf-8"))
                    self.assertFalse(cfg["featureEnabled"])
                    self.assertEqual(os.environ["SOBYA_CUSTODIAL_CONFIG"],str(root/"config.json"))
                finally: os.chdir(old)

    def test_disabled_operator_config_is_accepted_and_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); cfg=disabled_config(); (root/"config.example.json").write_text("{}",encoding="utf-8")
            path=root/"config.json"; path.write_text(json.dumps(cfg),encoding="utf-8"); old=Path.cwd()
            with patch.object(enzonic_start,"HERE",root), patch.dict(os.environ,{"SOBYA_CUSTODIAL_CONFIG":str(path)},clear=True), patch("custodial_runtime.main",return_value=0):
                try:
                    self.assertEqual(enzonic_start.main(),0)
                    self.assertEqual(json.loads(path.read_text(encoding="utf-8")),cfg)
                finally: os.chdir(old)

    def test_incomplete_live_config_is_rejected(self):
        cfg=disabled_config(); cfg["featureEnabled"]=True
        with self.assertRaisesRegex(SystemExit,"global depositWatchEnabled"): enzonic_start._validate_operator_config(cfg)

    def test_live_config_requires_https_rpc_keystores_and_reference_liquidity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); eth=root/"eth.json"; sob=root/"sob.json"; cert=root/"server.crt"; key=root/"server.key"; eth.write_text("{}",encoding="utf-8"); sob.write_text("{}",encoding="utf-8"); cert.write_text("test-cert",encoding="utf-8"); key.write_text("test-key",encoding="utf-8")
            cfg={"mode":"custodial-inventory","featureEnabled":True,"depositWatchEnabled":True,"networks":{
                "ethereum":{"enabled":True,"depositWatchEnabled":True,"inventoryVerified":True,"chainId":1,"usdtContract":"0xdAC17F958D2ee523a2206206994597C13D831ec7","rpcUrlEnv":"ETH_RPC","keystorePathEnv":"ETH_KEY","keystorePassphraseEnv":"ETH_PASS"},
                "sobya":{"enabled":True,"depositWatchEnabled":True,"inventoryVerified":True,"chainId":357812033857,"rpcUrlEnv":"SOB_RPC","keystorePathEnv":"SOB_KEY","keystorePassphraseEnv":"SOB_PASS"}},
                "api":{"enabled":True,"host":"0.0.0.0","port":25701,"gatewayTokenEnv":"SOBYA_GATEWAY_TOKEN","allowedOrigin":"https://snforem-cpu.github.io"},
                "pricing":{"baseReferencePriceUsdtPerSoby":"0.005","upwardDemandSensitivityBps":10000,"downwardDemandSensitivityBps":2500,"priceCeiling":None,"priceFloor":None,"referenceLiquidityUsdtBaseUnits":1000000000000},"limits":{"feeBps":100,"maxOrderUsdtBaseUnits":500000000,"maxDailyUsdtBaseUnitsPerNetwork":10000000000,"minimumInventoryBaseUnits":"100000000000000000000000"}}
            env={"ETH_RPC":"https://eth.example/rpc","ETH_KEY":str(eth),"ETH_PASS":"secret","SOB_RPC":"https://sob.example/rpc","SOB_KEY":str(sob),"SOB_PASS":"secret"}
            with patch.dict(os.environ,{**env,"SOBYA_GATEWAY_TOKEN":"a".repeat(64),"SOBYA_API_TLS_CERT":str(cert),"SOBYA_API_TLS_KEY":str(key)},clear=True): enzonic_start._validate_operator_config(cfg)

if __name__ == "__main__": unittest.main()
