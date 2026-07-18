from __future__ import annotations

import hashlib
import json
import re
import struct
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class P8EProfileContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matrix_path = ROOT / "config/p8e_build_matrix.yaml"
        self.matrix = yaml.safe_load(self.matrix_path.read_text(encoding="utf-8"))
        self.generated = json.loads(
            (ROOT / "config/generated/p8e_build_profiles.json").read_text(encoding="utf-8"))

    def test_generated_hash_matches_canonical_matrix(self) -> None:
        expected = hashlib.sha256(self.matrix_path.read_bytes()).hexdigest()
        self.assertEqual(self.generated["source_sha256"], expected)
        header = (ROOT / "software/ps_driver/p8e_profile_config.h").read_text(encoding="utf-8")
        self.assertIn(expected, header)

    def test_profile_values_are_generated_not_redeclared(self) -> None:
        expected = {item["profile_id"]: item for item in self.matrix["profiles"]}
        self.assertEqual(set(expected), set(self.generated["profiles"]))
        for profile_id, source in expected.items():
            generated = self.generated["profiles"][profile_id]
            self.assertEqual(generated["LANE_COUNT"], source["lane_count"])
            self.assertEqual(generated["PHYSICAL_MODULE_COUNT"], source["physical_module_count"])
            self.assertEqual(generated["TX_WINDOW"], source["tx_window"])
            self.assertEqual(generated["RX_WINDOW"], source["rx_window"])
            self.assertEqual(generated["SACK_BITS"], source["sack_bits"])
            self.assertGreaterEqual(generated["TX_WINDOW"], 32)

    def test_profile_abi_is_32_bytes(self) -> None:
        self.assertEqual(struct.calcsize("<IIIIHHHHHHB3x"), 32)

    def test_z7020_board_inputs_remain_pending(self) -> None:
        for profile in self.matrix["profiles"]:
            if profile["part"].startswith("xc7z020"):
                self.assertEqual(profile["board_pinmap"], "PENDING_D12")
                self.assertEqual(profile["board_xdc"], "PENDING_D12")

    def test_software_does_not_create_or_override_global_permit(self) -> None:
        text = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("software/ps_driver/p8e_profile.c", "software/ps_driver/p8e_profile.h")
        )
        self.assertIsNone(re.search(r"GLOBAL_PERMIT|permit_override|permit_heartbeat", text, re.I))


if __name__ == "__main__":
    unittest.main()
