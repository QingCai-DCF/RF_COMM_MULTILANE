from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class P10PowerStateEvidenceTests(unittest.TestCase):
    def test_power_state_is_reclassified_without_closing_d17(self) -> None:
        blocker = load_json("evidence/generated/p10_severe_hardware_blocker.json")
        reassessment = load_json("evidence/generated/p10_hardware_admission_reassessment.json")
        scope = blocker["refined_scope"]

        self.assertEqual("P10-SAFETY-POWERUP-001", blocker["blocker_id"])
        self.assertEqual("RECLASSIFIED_NONBLOCKING_PENDING_D17", blocker["status"])
        self.assertFalse(blocker["p10_scope_decision"]["blocking_for_p10"])
        self.assertEqual(
            "INHIBITED_BY_SD_HIGH_PER_TFDU6102_TRUTH_TABLE",
            scope["ordinary_powered_configuration_optical_tx"],
        )
        self.assertEqual("PENDING_D17", scope["partial_power_optical_tx_disabled"])
        self.assertEqual(
            "PENDING_D17_NONBLOCKING_FOR_P10_SCOPED_NO_POWER_CYCLE_RUN",
            reassessment["power_state_finding_status"],
        )
        self.assertEqual("P10-ROLE-BINDING-001", reassessment["blocking_condition"])
        self.assertFalse(reassessment["p10_hardware_admission"])
        self.assertIn("PHYSICAL_GLOBAL_PERMIT=PENDING_D17", reassessment["unchanged_pending"])
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
        self.assertEqual("P10-ROLE-BINDING-001", summary["blocking_condition"])
        self.assertEqual(
            [
                "State which of 210249855178 and 210512180081 is AX7020-F; the other will be bound as AX7020-R."
            ],
            summary["required_user_resolution"],
        )
        self.assertEqual("ENUMERATED_UNASSIGNED", identity["status"])
        self.assertEqual(
            ["210249855178", "210512180081"],
            identity["observed_cable_serials"],
        )


if __name__ == "__main__":
    unittest.main()
