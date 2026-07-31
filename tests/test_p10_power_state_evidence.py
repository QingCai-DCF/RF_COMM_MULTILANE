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
        self.assertIsNone(reassessment["blocking_condition"])
        self.assertTrue(reassessment["p10_hardware_admission"])
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

    def test_formal_hardware_run_is_scoped_and_roles_are_serial_bound(self) -> None:
        summary = load_json("evidence/generated/p10_fasttrack_final_summary.json")
        identity = load_json("config/hardware/p10_jtag_identity_inventory.json")

        self.assertEqual("PASS", summary["status"])
        self.assertTrue(summary["formal_campaign"])
        self.assertTrue(summary["current_run_hardware_authorization"])
        self.assertTrue(summary["hardware_actions_executed"])
        self.assertFalse(summary["network_used"])
        self.assertFalse(summary["hardware_movement"])
        self.assertFalse(summary["rotation_executed"])
        self.assertFalse(summary["rewiring_executed"])
        self.assertEqual("0x3", summary["maximum_lane_mask_used"])
        self.assertEqual("PASS", summary["SHUTDOWN_FIXED"])
        self.assertEqual("PASS", summary["SHUTDOWN_ROTATING"])
        self.assertEqual("AX7020-F/JTAG:210249855178", summary["fixed_board_id"])
        self.assertEqual("AX7020-R/JTAG:210512180081", summary["rotating_board_id"])
        self.assertEqual("BOUND_EXPLICIT_SERIAL_TO_ROLE", identity["status"])
        self.assertEqual(
            ["210249855178", "210512180081"],
            identity["observed_cable_serials"],
        )
        self.assertEqual("210249855178", identity["fixed_board_serial"])
        self.assertEqual("210512180081", identity["rotating_board_serial"])
        self.assertEqual(
            "USER_AUTHORIZED_AGENT_SELECTED_STABLE_JTAG_SERIAL_BINDING",
            identity["role_binding_source"],
        )
        self.assertEqual(
            "LEXICOGRAPHICALLY_SMALLEST_OBSERVED_SERIAL_AS_FIXED",
            identity["role_binding_selection_rule"],
        )
        self.assertFalse(identity["target_order_used_for_role_binding"])


if __name__ == "__main__":
    unittest.main()
