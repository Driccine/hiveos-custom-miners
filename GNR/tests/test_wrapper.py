import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gnr", BASE / "hiveos/gnr.py")
gnr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gnr)
FAKE_ADDRESS = "gnr1" + "q" * 2600  # Syntax-only fixture. Never used on a real network.


class WrapperTests(unittest.TestCase):
    def config(self, **overrides):
        env = {"GNR_WALLET": FAKE_ADDRESS}
        env.update(overrides)
        return gnr.config_from_env(env)

    def test_defaults(self):
        c = self.config()
        self.assertEqual(c["node"], "https://genoryn.io")
        self.assertIsNone(c["devices"])

    def test_empty_node_uses_default(self):
        self.assertEqual(self.config(GNR_NODE=" ")["node"], gnr.DEFAULT_NODE)

    def test_short_address_explained(self):
        with self.assertRaisesRegex(ValueError, "COMPLETE"):
            self.config(GNR_WALLET="gnrs1example")

    def test_reject_worker_suffix_and_testnet(self):
        for addr in (FAKE_ADDRESS + ".rig1", "t" + FAKE_ADDRESS, "", "%WAL%"):
            with self.assertRaises(ValueError):
                self.config(GNR_WALLET=addr)

    def test_url_validation(self):
        for url in ("stratum+tcp://host:123", "https://u:p@host", "https://host?q=1", "https://host\nhttp://evil"):
            with self.assertRaises(ValueError):
                self.config(GNR_NODE=url)

    def test_local_node(self):
        self.assertEqual(self.config(GNR_NODE="http://192.168.1.2:30334/")["node"], "http://192.168.1.2:30334")

    def test_devices_and_batch(self):
        c = self.config(GNR_EXTRA="--devices 0,2 --batch 1048576")
        self.assertEqual(c["devices"], [0, 2])
        cmd = gnr.command("krypton-miner", c, "/run/a.txt", 2)
        self.assertEqual(cmd[cmd.index("--backend") + 1], "cuda")
        self.assertEqual(cmd[cmd.index("--devices") + 1], "2")
        self.assertNotIn(FAKE_ADDRESS, cmd)

    def test_duplicate_or_invalid_devices(self):
        for extra in ("--devices 0,0", "--devices x", "--batch 1"):
            with self.assertRaises(ValueError):
                self.config(GNR_EXTRA=extra)

    def test_extra_never_evaluates_shell(self):
        for extra in ("--node http://evil", "$(touch /tmp/evil)", "--backend cpu"):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.config(GNR_EXTRA=extra)

    def test_select_nvidia_only(self):
        p = {"gpus": [{"backend": "cuda", "index": 0, "usable": True},
                       {"backend": "opencl", "index": 1, "usable": True}]}
        self.assertEqual(gnr.select_devices(p, None), [0])
        with self.assertRaises(RuntimeError):
            gnr.select_devices(p, [1])

    def test_no_cpu_fallback(self):
        with self.assertRaises(RuntimeError):
            gnr.select_devices({"gpus": []}, None)
        with self.assertRaisesRegex(RuntimeError, "PTX"):
            gnr.select_devices({"gpus": [{"backend": "cuda", "index": 0, "usable": False, "error": "PTX"}]}, None)

    def test_status_validation(self):
        self.assertIsNone(gnr.accepted_status("not json"))
        self.assertIsNone(gnr.accepted_status('{"event":"share"}'))
        for value in (-1, float("nan"), float("inf")):
            self.assertIsNone(gnr.accepted_status(json.dumps({"event": "status", "hashrate_hs": value})))
        self.assertEqual(gnr.accepted_status('{"event":"status","hashrate_hs":1000}')["hashrate_hs"], 1000)

    def test_hive_units_shares_and_bus_mapping(self):
        states = {2: {"seen": 100, "data": {"hashrate_hs": 12500000, "accepted_shares": 4, "accepted_blocks": 1, "rejected": 1}},
                  0: {"seen": 100, "data": {"hashrate_hs": 20000000, "accepted_shares": 3, "rejected": 0}}}
        buses = {2: "0000:0b:00.0", 0: "0000:03:00.0"}
        result = gnr.snapshot(states, [2, 0], buses, {buses[2]: (60, 40), buses[0]: (50, 30)}, 80, 100)
        self.assertEqual(result["khs"], 32500)
        self.assertEqual(result["stats"]["hs"], [12500000, 20000000])
        self.assertEqual(result["stats"]["ar"], [7, 1])  # no double-count of blocks
        self.assertEqual(result["stats"]["bus_numbers"], [11, 3])
        self.assertEqual(result["stats"]["temp"], [60, 50])

    def test_stale_device_rate_is_zero(self):
        result = gnr.snapshot({0: {"seen": 1, "data": {"hashrate_hs": 999}}}, [0], {}, {}, 1, 100)
        self.assertEqual(result["khs"], 0)
        self.assertNotIn("temp", result["stats"])

    def test_atomic_stats_and_stale_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stats.json"
            gnr.atomic_json(path, {"updated": 100, "khs": 12, "stats": {"hs": [12000]}})
            self.assertEqual(gnr.read_stats(path, 110)[0], 12)
            self.assertEqual(gnr.read_stats(path, 200), (0, None))
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text("bad")
            self.assertEqual(gnr.read_stats(path, 110), (0, None))


if __name__ == "__main__":
    unittest.main()
