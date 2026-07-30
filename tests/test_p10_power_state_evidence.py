from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class P10PowerStateEvidenceTests(unittest.TestCase):
    def test_refined_power_state_conclusion_is_fail_closed(self) -> None:
        blocker = load_json("evidence/generated/p10_severe_hardware_blocker.json")
        scope = blocker["refined_scope"]

        self.assertEqual("P10-SAFETY-POWERUP-001", blocker["blocker_id"])
        self.assertEqual("OPEN", blocker["status"])
        self.assertEqual(
            "INHIBITED_BY_SD_HIGH_PER_TFDU6102_TRUTH_TABLE",
            scope["ordinary_powered_configuration_optical_tx"],
        )
        self.assertEqual("NOT_ESTABLISHED", scope["partial_power_optical_tx_disabled"])
        self.assertIn(
            "PDF page 10 / printed page 9",
            "\n".join(blocker["sources"]["tfdu_datasheet"]["citation_locations"]),
        )

    def test_all_signal_rows_retain_required_provenance(self) -> None:
        audit = load_json("evidence/generated/p10_wiring_design_audit.json")
        required = {
            "board_role",
            "module_id",
            "logical_signal",
            "fpga_direction",
            "connector",
            "connector_pin",
            "fpga_package_pin",
            "io_bank",
            "vcco_volts",
            "iostandard",
            "tfdu_board_pin",
            "reset_default",
            "pull",
            "source_document",
            "source_page_table",
            "notes",
        }

        self.assertEqual(16, audit["signal_line_count"])
        self.assertFalse(audit["ax7010_xdc_reused"])
        for row in audit["signal_lines"]:
            self.assertTrue(required.issubset(row), row)
            for key in required:
                self.assertNotEqual("", str(row[key]).strip(), f"{row['module_id']} {key}")

    def test_programming_and_tfdu_drive_remain_unexecuted_and_roles_unassigned(self) -> None:
        summary = load_json("evidence/generated/p10_fasttrack_final_summary.json")
        identity = load_json("config/hardware/p10_jtag_identity_inventory.json")

        self.assertEqual("PARTIAL", summary["status"])
        self.assertFalse(summary["programming_executed"])
        self.assertFalse(summary["tfdu_drive_executed"])
        self.assertFalse(summary["network_used"])
        self.assertEqual("ENUMERATED_UNASSIGNED", identity["status"])
        self.assertEqual(
            ["210249855178", "210512180081"],
            identity["observed_cable_serials"],
        )


if __name__ == "__main__":
    unittest.main()
