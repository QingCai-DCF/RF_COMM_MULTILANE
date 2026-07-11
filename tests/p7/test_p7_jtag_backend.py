from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from p7_app_transport import LanePolicy  # noqa: E402
from p7_jtag_backend import (  # noqa: E402
    BackendValidationError,
    MAX_TRANSACTION_BYTES,
    MAX_TRANSACTION_OPERATIONS,
    MemoryMockExecutor,
    generate_bundle,
    lane_for_fragment,
    parse_raw_result,
    runtime_feasibility,
    run_memory_mock_self_test,
    transaction_shape,
)


def data_pattern(size: int, salt: int) -> bytes:
    seed = bytes(((index * 31 + salt * 17) ^ (index >> 2)) & 0xFF for index in range(256))
    return (seed * ((size + 255) // 256))[:size]


class P7JtagBackendTests(unittest.TestCase):
    def test_large_object_operation_formula_and_limits(self) -> None:
        expected = {
            4096: (20, 1189, 4269),
            65536: (305, 18900, 67092),
            1048576: (4878, 302388, 1073038),
        }
        for size, (fragments, words, operations) in expected.items():
            with self.subTest(size=size):
                shape = transaction_shape(size)
                self.assertEqual(fragments, shape["fragment_count"])
                self.assertEqual(words, shape["encoded_word_count"])
                self.assertEqual(operations, shape["operation_count"])
                self.assertLessEqual(operations, MAX_TRANSACTION_OPERATIONS)
                feasibility = runtime_feasibility(operations)
                self.assertTrue(feasibility["feasible_within_authorized_runtime"])
        slow = runtime_feasibility(
            expected[1048576][2], jtag_frequency_hz=100_000
        )
        self.assertFalse(slow["feasible_within_authorized_runtime"])
        one_mib_global = runtime_feasibility(
            expected[1048576][2],
            preflight_timeout_sec=60,
            shutdown_timeout_sec=60,
            configured_stage_timeout_sec=1400,
        )
        self.assertTrue(one_mib_global["feasible_within_authorized_runtime"])
        self.assertEqual(1372, one_mib_global["minimum_stage_runtime_sec"])
        self.assertEqual(
            {
                "containment": 120,
                "other": 65,
                "configured": 1765,
                "margin": 35,
            },
            {
                "containment": one_mib_global["global_runtime_budget"][
                    "containment_allowance_seconds"
                ],
                "other": one_mib_global["global_runtime_budget"]["other_guard_seconds"],
                "configured": one_mib_global["global_runtime_budget"][
                    "configured_global_timeout_ceiling_sec"
                ],
                "margin": one_mib_global["global_runtime_budget"][
                    "configured_unallocated_margin_seconds"
                ],
            },
        )
        self.assertEqual(128 * 1024 * 1024, MAX_TRANSACTION_BYTES)
        self.assertGreater(
            transaction_shape(8 * 1024 * 1024)["operation_count"],
            MAX_TRANSACTION_OPERATIONS,
        )

    def test_memory_mock_roundtrip_sizes_and_lane_policies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            temp = Path(temp_text)
            for policy_index, policy in enumerate(LanePolicy):
                for size in (0, 215, 216, 4096):
                    with self.subTest(policy=policy.name, size=size):
                        data = data_pattern(size, policy_index + 1)
                        stem = f"{policy.name}_{size}"
                        transaction = temp / f"{stem}.transactions.txt"
                        manifest = temp / f"{stem}.manifest.json"
                        raw = temp / f"{stem}.raw.log"
                        output = temp / f"{stem}.output.bin"
                        generated = generate_bundle(
                            data,
                            transaction_path=transaction,
                            manifest_path=manifest,
                            session_epoch=0x50370000 + policy_index,
                            object_id=size + 1,
                            lane_policy=policy,
                        )
                        MemoryMockExecutor().execute(transaction, raw)
                        summary = parse_raw_result(
                            manifest_path=manifest,
                            raw_log_path=raw,
                            output_path=output,
                        )
                        self.assertEqual(output.read_bytes(), data)
                        self.assertEqual(summary["P7_JTAG_BACKEND_PARSE"], "PASS")
                        self.assertEqual(
                            generated["transaction_shape"]["operation_count"],
                            generated["transaction_operation_count"],
                        )
                        self.assertEqual(
                            transaction.stat().st_size, generated["transaction_file_bytes"]
                        )
                        self.assertEqual(
                            [fragment["lane_mask"] for fragment in generated["fragments"]],
                            [
                                lane_for_fragment(policy, index)
                                for index in range(generated["fragment_count"])
                            ],
                        )
                        self.assertTrue(
                            all("rx_bytes_hex" in record for record in summary["fragments"])
                        )

    def test_missing_and_duplicate_raw_keys_are_rejected_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            temp = Path(temp_text)
            transaction = temp / "object.transactions.txt"
            manifest = temp / "object.manifest.json"
            raw = temp / "object.raw.log"
            output = temp / "object.output.bin"
            generate_bundle(
                data_pattern(216, 9),
                transaction_path=transaction,
                manifest_path=manifest,
                session_epoch=9,
                object_id=10,
                lane_policy=LanePolicy.STRIPE_ROUND_ROBIN,
            )
            MemoryMockExecutor().execute(transaction, raw)
            lines = raw.read_text(encoding="utf-8").splitlines()
            variants = {
                "MISSING_KEY": [
                    line for line in lines if not line.startswith("P7F00001_RXW000=")
                ],
                "DUPLICATE_KEY": lines
                + [next(line for line in lines if line.startswith("P7F00000_RXW000="))],
                "UNEXPECTED_FRAGMENT_RECORD": lines + ["P7F99999_RXW000=00000000"],
            }
            for expected_code, content in variants.items():
                with self.subTest(expected_code=expected_code):
                    bad_raw = temp / f"{expected_code}.log"
                    bad_raw.write_text("\n".join(content) + "\n", encoding="utf-8")
                    output.write_bytes(b"prior-good-output")
                    with self.assertRaises(BackendValidationError) as caught:
                        parse_raw_result(
                            manifest_path=manifest,
                            raw_log_path=bad_raw,
                            output_path=output,
                        )
                    self.assertEqual(caught.exception.code, expected_code)
                    self.assertEqual(output.read_bytes(), b"prior-good-output")
                    self.assertFalse(list(temp.glob(f".{output.name}.*.partial")))

    def test_error_counter_and_rx_corruption_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            temp = Path(temp_text)
            transaction = temp / "object.transactions.txt"
            manifest = temp / "object.manifest.json"
            raw = temp / "object.raw.log"
            output = temp / "object.output.bin"
            generate_bundle(
                data_pattern(215, 3),
                transaction_path=transaction,
                manifest_path=manifest,
                session_epoch=3,
                object_id=4,
                lane_policy=LanePolicy.REPLICATE_0X3,
            )
            MemoryMockExecutor().execute(transaction, raw)
            original = raw.read_text(encoding="utf-8")
            variants = {
                "ERROR_COUNTER": original.replace(
                    "P7F00000_DUTY_VIOLATION=00000000",
                    "P7F00000_DUTY_VIOLATION=00000001",
                ),
                "RX_BYTES": original.replace(
                    next(
                        line
                        for line in original.splitlines()
                        if line.startswith("P7F00000_RXW000=")
                    ),
                    "P7F00000_RXW000=00000000",
                ),
            }
            for expected_code, content in variants.items():
                with self.subTest(expected_code=expected_code):
                    bad_raw = temp / f"{expected_code}.log"
                    bad_raw.write_text(content, encoding="utf-8")
                    with self.assertRaises(BackendValidationError) as caught:
                        parse_raw_result(
                            manifest_path=manifest,
                            raw_log_path=bad_raw,
                            output_path=output,
                        )
                    self.assertEqual(caught.exception.code, expected_code)

    def test_embedded_self_test(self) -> None:
        result = run_memory_mock_self_test()
        self.assertEqual(result["P7_JTAG_BACKEND_MEMORY_MOCK_SELF_TEST"], "PASS")
        self.assertEqual(result["roundtrip_cases"], 16)
        self.assertFalse(result["hardware_actions_executed"])


if __name__ == "__main__":
    unittest.main()
