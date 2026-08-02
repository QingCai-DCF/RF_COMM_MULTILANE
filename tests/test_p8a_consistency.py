from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from p8a_common import (  # noqa: E402
    RECONCILIATION_JSON_PATH,
    RECONCILIATION_MD_PATH,
    REQUIREMENTS_PATH,
    STATE_PATH,
    STATUS_PATH,
    TRACEABILITY_PATH,
    load_json,
    load_yaml,
    render_project_status,
    render_traceability,
    validate_requirements,
    validate_state,
)
from reconcile_p0_p7_evidence import build_reconciliation  # noqa: E402


class P8AConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.state = load_json(STATE_PATH)
        cls.requirements = load_yaml(REQUIREMENTS_PATH)

    def test_canonical_state_validates(self) -> None:
        self.assertEqual([], validate_state(self.state, ROOT))

    def test_state_rejects_p7_regression(self) -> None:
        state = copy.deepcopy(self.state)
        state["p7_status"] = "PENDING_HW"
        errors = validate_state(state, ROOT)
        self.assertTrue(any("p7_status must remain PASS" in error for error in errors))

    def test_state_rejects_final_product_promotion(self) -> None:
        state = copy.deepcopy(self.state)
        state["final_product_status"] = "PASS"
        state["product_final_acceptance"] = "PASS"
        errors = validate_state(state, ROOT)
        self.assertTrue(any("final_product_status" in error for error in errors))
        self.assertTrue(any("product_final_acceptance" in error for error in errors))

    def test_p10_scoped_pass_does_not_promote_final_z7020_or_rotation(self) -> None:
        self.assertEqual("PASS", self.state["p10_status"])
        self.assertEqual("PENDING_Z7020_HW", self.state["z7020_target_status"])
        self.assertEqual("PENDING_FINAL_MECHANICAL", self.state["rotation_status"])
        self.assertEqual("PENDING_HW", self.state["final_product_status"])

    def test_p10_acceptance_rejects_network_or_pending_scope_promotion(self) -> None:
        state = copy.deepcopy(self.state)
        state["p10_acceptance"]["network_used"] = True
        state["p10_acceptance"]["unchanged_pending_scopes"]["PRODUCT_FINAL"] = "PASS"
        errors = validate_state(state, ROOT)
        self.assertTrue(any("p10_acceptance.network_used" in error for error in errors))
        self.assertTrue(any("PRODUCT_FINAL" in error for error in errors))

    def test_latest_p10_1r_hardware_run_owns_last_hardware_fields(self) -> None:
        self.assertEqual("P10_1R", self.state["last_hardware_stage"])
        self.assertEqual(
            self.state["p10_1r_remediation"]["last_hardware_run_id"],
            self.state["last_hardware_run_id"],
        )
        state = copy.deepcopy(self.state)
        state["last_hardware_stage"] = "P10_1"
        errors = validate_state(state, ROOT)
        self.assertTrue(
            any(
                "last_hardware_stage must be P10_1R" in error
                for error in errors
            )
        )

    def test_p10_1r_blocker_hash_is_fail_closed(self) -> None:
        state = copy.deepcopy(self.state)
        state["p10_1r_remediation"]["hardware_blocker"]["sha256"] = "0" * 64
        errors = validate_state(state, ROOT)
        self.assertTrue(
            any("P10.1R hardware blocker: SHA256 mismatch" in error for error in errors)
        )

    def test_state_requires_legacy_ab_l1_record(self) -> None:
        state = copy.deepcopy(self.state)
        state["legacy_known_failures"] = []
        errors = validate_state(state, ROOT)
        self.assertTrue(any("AB_L1_BAD_DIR" in error for error in errors))

    def test_requirements_baseline_validates(self) -> None:
        self.assertEqual([], validate_requirements(self.requirements, ROOT))

    def test_pass_requirement_requires_test_and_hash(self) -> None:
        requirements = copy.deepcopy(self.requirements)
        item = next(req for req in requirements["requirements"] if req["requirement_id"] == "P8A-STATE-001")
        item["test_id"] = None
        item["artifact_hashes"] = []
        errors = validate_requirements(requirements, ROOT)
        self.assertTrue(any("PASS requires test_id" in error for error in errors))
        self.assertTrue(any("PASS requires artifact_hashes" in error for error in errors))

    def test_duplicate_requirement_id_fails(self) -> None:
        requirements = copy.deepcopy(self.requirements)
        requirements["requirements"].append(copy.deepcopy(requirements["requirements"][0]))
        errors = validate_requirements(requirements, ROOT)
        self.assertTrue(any("duplicate requirement IDs" in error for error in errors))

    def test_generated_documents_are_deterministic(self) -> None:
        self.assertEqual(render_project_status(self.state), render_project_status(self.state))
        self.assertEqual(render_traceability(self.requirements), render_traceability(self.requirements))

    def test_generated_documents_are_byte_exact_lf(self) -> None:
        self.assertEqual(render_project_status(self.state).encode("utf-8"), STATUS_PATH.read_bytes())
        self.assertEqual(render_traceability(self.requirements).encode("utf-8"), TRACEABILITY_PATH.read_bytes())
        for path in (RECONCILIATION_JSON_PATH, RECONCILIATION_MD_PATH):
            self.assertNotIn(b"\r\n", path.read_bytes())

    def test_p0_p7_reconciliation_passes_and_preserves_conflicts(self) -> None:
        reconciliation = build_reconciliation(ROOT)
        self.assertEqual("PASS", reconciliation["status"])
        conflicts = {item["conflict_id"] for item in reconciliation["historical_conflicts"]}
        self.assertIn("AB_L1_LEGACY_BAD_DIR_VS_CURRENT_P7_USABILITY", conflicts)
        self.assertIn("P7_R41_FAIL_VS_P7_R74_PASS", conflicts)
        self.assertFalse(reconciliation["hardware_scope_promoted"])


if __name__ == "__main__":
    unittest.main()
