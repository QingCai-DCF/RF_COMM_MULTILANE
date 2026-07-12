from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import p7_diagnostic_impact as subject  # noqa: E402


class P7DiagnosticImpactTests(unittest.TestCase):
    def test_adaptive_matrix_is_prefix_plus_contiguous_suffix_without_stationary(self) -> None:
        self.assertEqual(
            [1, 2, 3, 4, 62, 63, 64, 65],
            subject.expected_selected_ordinals(62),
        )
        for invalid in (0, 4, 66, 100):
            with self.assertRaises(ValueError):
                subject.expected_selected_ordinals(invalid)

    def test_backend_manifest_comparison_ignores_only_run_local_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = {
                "schema": "example",
                "input_file": "old/input.bin",
                "input_file_sha256": "a" * 64,
                "transaction_file": "old/transaction.txt",
                "operation_count": 123,
            }
            old = root / "old.json"
            new = root / "new.json"
            old.write_text(json.dumps(base), encoding="utf-8")
            base["input_file"] = "new/input.bin"
            base["transaction_file"] = "new/transaction.txt"
            new.write_text(json.dumps(base), encoding="utf-8")
            self.assertEqual(
                subject.canonical_backend_manifest_sha256(old),
                subject.canonical_backend_manifest_sha256(new),
            )
            base["operation_count"] = 124
            new.write_text(json.dumps(base), encoding="utf-8")
            self.assertNotEqual(
                subject.canonical_backend_manifest_sha256(old),
                subject.canonical_backend_manifest_sha256(new),
            )

    def test_symbol_fingerprint_is_narrow_but_fail_closed_on_executable_change(self) -> None:
        old = b"CONST = 1\n\ndef used(value):\n    return value + CONST\n"
        unrelated = b"# comment changed\nCONST = 1\n\ndef used(value):\n    return value + CONST\n\ndef unrelated():\n    return 9\n"
        changed = b"CONST = 1\n\ndef used(value):\n    return value - CONST\n"
        self.assertEqual(
            subject.symbol_sha256(old, "used"),
            subject.symbol_sha256(unrelated, "used"),
        )
        self.assertNotEqual(
            subject.symbol_sha256(old, "used"),
            subject.symbol_sha256(changed, "used"),
        )

    def test_newline_materialization_does_not_fake_a_source_change(self) -> None:
        self.assertEqual(
            subject.normalized_source_sha256(b"one\ntwo\n"),
            subject.normalized_source_sha256(b"one\r\ntwo\r\n"),
        )


if __name__ == "__main__":
    unittest.main()
