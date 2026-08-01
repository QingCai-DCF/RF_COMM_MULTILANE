from __future__ import annotations

import unittest
from pathlib import Path

from scripts import run_p8b_geometry_gate as gate


class P8BCheckoutStabilityTests(unittest.TestCase):
    def test_checkout_paths_normalize_to_identical_evidence(self) -> None:
        first_root = Path(r"C:\worktrees\first\RF_COMM_MULTILANE")
        second_root = Path(r"D:\short\RF_COMM_MULTILANE")
        first = gate.normalize_checkout_text(
            rf"tool -i {first_root}\rtl {first_root}\sim\tb.sv",
            root=first_root,
        )
        second = gate.normalize_checkout_text(
            rf"tool -i {second_root}\rtl {second_root}\sim\tb.sv",
            root=second_root,
        )
        self.assertEqual(first, second)
        self.assertEqual(first.count("<REPO_ROOT>"), 2)

    def test_xsim_exit_timestamp_is_normalized(self) -> None:
        first = gate.normalize_checkout_text(
            "INFO: [Common 17-206] Exiting xsim at Fri Jul 31 21:45:43 2026..."
        )
        second = gate.normalize_checkout_text(
            "INFO: [Common 17-206] Exiting xsim at Fri Jul 31 21:46:05 2026..."
        )
        self.assertEqual(first, second)
        self.assertTrue(first.endswith("<TIMESTAMP>"))

    def test_p10_1_streaming_hardware_stage_preserves_p8b_scope(self) -> None:
        state = {
            "current_program_stage": (
                "P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE"
            ),
            "current_run_hardware_authorization": False,
            "current_z7010_platform_status": "PLATFORM_LIMITED_PASS",
            "final_product_status": "PENDING_HW",
            "no_hardware_default": True,
            "p7_status": "PASS",
            "product_final_acceptance": "PENDING",
            "rotation_status": "PENDING_FINAL_MECHANICAL",
            "z7020_target_status": "PENDING_Z7020_HW",
            "stage_status": {
                "P8B_GEOMETRY_MAPPING_HANDOVER": "PASS",
                "P8C_TFDU_SAFETY_SINGLE_GLOBAL_PERMIT": "PASS",
            },
        }
        passed, details = gate.check_state(state)
        self.assertTrue(passed, details)

    def test_p10_1r_remediation_stage_preserves_p8b_scope(self) -> None:
        state = {
            "current_program_stage": (
                "P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION"
            ),
            "current_run_hardware_authorization": False,
            "current_z7010_platform_status": "PLATFORM_LIMITED_PASS",
            "final_product_status": "PENDING_HW",
            "no_hardware_default": True,
            "p7_status": "PASS",
            "product_final_acceptance": "PENDING",
            "rotation_status": "PENDING_FINAL_MECHANICAL",
            "z7020_target_status": "PENDING_Z7020_HW",
            "stage_status": {
                "P8B_GEOMETRY_MAPPING_HANDOVER": "PASS",
                "P8C_TFDU_SAFETY_SINGLE_GLOBAL_PERMIT": "PASS",
            },
        }
        passed, details = gate.check_state(state)
        self.assertTrue(passed, details)

    def test_current_hardware_authorization_still_fails_closed(self) -> None:
        state = {
            "current_program_stage": "P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE",
            "current_run_hardware_authorization": True,
            "current_z7010_platform_status": "PLATFORM_LIMITED_PASS",
            "final_product_status": "PENDING_HW",
            "no_hardware_default": True,
            "p7_status": "PASS",
            "product_final_acceptance": "PENDING",
            "rotation_status": "PENDING_FINAL_MECHANICAL",
            "z7020_target_status": "PENDING_Z7020_HW",
            "stage_status": {
                "P8B_GEOMETRY_MAPPING_HANDOVER": "PASS",
                "P8C_TFDU_SAFETY_SINGLE_GLOBAL_PERMIT": "PASS",
            },
        }
        passed, details = gate.check_state(state)
        self.assertFalse(passed)
        self.assertIn("current_run_hardware_authorization", details["mismatches"])


if __name__ == "__main__":
    unittest.main()
