from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "hw"))

import run_p7_ps_application_stage_safe as stage  # noqa: E402


RUN_ID = "p7_20260714_ddr_external_campaign_c2_08"
RUN_ROOT = (
    ROOT / "evidence" / "hardware" / "p7" / "stage62_functional" / RUN_ID
)
BUNDLE = RUN_ROOT / "bundle"
AUDIT = ROOT / "ddr_debug" / "campaign_c2" / "C2_08_PARTIAL_EVIDENCE_AUDIT.json"
CLOSURE = ROOT / "ddr_debug" / "campaign_c2" / "CAMPAIGN_C2_CLOSURE.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CampaignC2PartialEvidenceTests(unittest.TestCase):
    def test_audit_sources_and_closure_binding_are_exact(self) -> None:
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        closure = json.loads(CLOSURE.read_text(encoding="utf-8"))
        self.assertEqual(RUN_ID, audit["run_id"])
        self.assertEqual("PENDING_HW", audit["HARDWARE_ACCEPTANCE"])
        self.assertFalse(audit["formal_stage"]["completed"])
        self.assertFalse(audit["formal_stage"]["acceptance_credit"])
        for record in audit["immutable_sources"]:
            path = ROOT / record["path"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(record["size_bytes"], path.stat().st_size)
            self.assertEqual(record["sha256"], sha256(path))
        binding = closure["package_bindings"]
        self.assertEqual(
            "ddr_debug/campaign_c2/C2_08_PARTIAL_EVIDENCE_AUDIT.json",
            binding["c2_08_partial_evidence_audit"],
        )
        self.assertEqual(sha256(AUDIT), binding["c2_08_partial_evidence_audit_sha256"])
        self.assertEqual(
            "BYTE_WIDE_LARGE_EVIDENCE_HARVEST_EXCEEDED_BOUNDED_OUTER_WINDOW",
            closure["root_cause"]["classification"],
        )

    def test_partial_raw_markers_prove_attempt_but_not_completion(self) -> None:
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        raw_path = RUN_ROOT / "p7_ps_application_raw_result.log.partial.write_partial"
        markers = stage.parse_markers(raw_path.read_text(encoding="utf-8"))
        for key, expected in audit["raw_attempt_markers"].items():
            self.assertEqual(str(expected), markers[key])
        self.assertNotIn("P7_PS_STAGE_RESULT", markers)
        self.assertNotIn("P7_FUNCTIONAL_LARGE_POLICY_MATRIX_COMPLETE", markers)

    def test_retained_boundary_checkpoint_and_64k_evidence_is_complete(self) -> None:
        for index in range(48):
            prefix = f"boundary_{index}"
            descriptor = stage.unpack_descriptor(
                (BUNDLE / f"{prefix}_descriptor_result.bin").read_bytes()
            )
            self.assertEqual(stage.P7_DESCRIPTOR_COMPLETE, descriptor["status"])
            self.assertEqual(0, descriptor["error_code"])
            self.assertEqual(index + 1, descriptor["completion_sequence"])
            self.assertEqual(
                (BUNDLE / f"{prefix}_input.bin").read_bytes(),
                (BUNDLE / f"{prefix}_output_result.bin").read_bytes(),
            )
            self.assertEqual(
                descriptor["fragments_total"] * 64,
                (BUNDLE / f"{prefix}_trace_result.bin").stat().st_size,
            )

        checkpoint = stage.unpack_descriptor(
            (BUNDLE / "functional_checkpoint_4k_descriptor_result.bin").read_bytes()
        )
        self.assertEqual(stage.P7_DESCRIPTOR_COMPLETE, checkpoint["status"])
        self.assertEqual(0, checkpoint["error_code"])
        self.assertEqual(49, checkpoint["completion_sequence"])
        self.assertEqual(
            (BUNDLE / "functional_checkpoint_4k_input.bin").read_bytes(),
            (BUNDLE / "functional_checkpoint_4k_output_result.bin").read_bytes(),
        )

        for slot, sequence in zip(range(4, 8), range(50, 54), strict=True):
            descriptor = stage.unpack_descriptor(
                (BUNDLE / f"descriptor_result_{slot}.bin").read_bytes()
            )
            self.assertEqual(stage.P7_DESCRIPTOR_COMPLETE, descriptor["status"])
            self.assertEqual(0, descriptor["error_code"])
            self.assertEqual(sequence, descriptor["completion_sequence"])
            self.assertEqual(
                (BUNDLE / f"input_{slot}.bin").read_bytes(),
                (BUNDLE / f"output_result_{slot}.bin").read_bytes(),
            )
            self.assertEqual(
                descriptor["fragments_total"] * 64,
                (BUNDLE / f"trace_result_{slot}.bin").stat().st_size,
            )

    def test_first_1m_firmware_descriptor_is_terminal_but_host_dump_is_absent(self) -> None:
        audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        descriptor_path = BUNDLE / "descriptor_result_0.bin"
        descriptor = stage.unpack_descriptor(descriptor_path.read_bytes())
        input_path = BUNDLE / "input_0.bin"
        expected_sha = sha256(input_path)
        self.assertEqual(stage.P7_DESCRIPTOR_COMPLETE, descriptor["status"])
        self.assertEqual(0, descriptor["error_code"])
        self.assertEqual(1_048_576, descriptor["object_length"])
        self.assertEqual(4_878, descriptor["fragments_completed"])
        self.assertEqual(54, descriptor["completion_sequence"])
        self.assertEqual(expected_sha, descriptor["output_sha256"])
        self.assertEqual(
            expected_sha,
            audit["completed_internal_evidence"]["first_1m_case"][
                "descriptor_output_sha256"
            ],
        )
        self.assertFalse((BUNDLE / "output_result_0.bin").exists())
        self.assertFalse((BUNDLE / "output_result_0.bin.write_partial").exists())


if __name__ == "__main__":
    unittest.main()
