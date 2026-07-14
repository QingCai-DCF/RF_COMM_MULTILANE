import hashlib
import importlib.util
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.p7_ps_mailbox_backend import (
    P7_STAGE62_MICROTEST_DESTINATION_CANARY,
    P7_STAGE62_MICROTEST_DESTINATION_GUARD,
    P7_STAGE62_MICROTEST_HEADER_BYTES,
    P7_STAGE62_MICROTEST_RECORD_BYTES,
    P7_STAGE62_MICROTEST_RECORD_MAGIC,
    P7_STAGE62_MICROTEST_SOURCE_GUARD,
    P7_STAGE62_MICROTEST_TARGET_OFFSET,
    P7_STAGE62_MICROTEST_VERSION,
    build_stage62_microtest_fixtures,
    stage62_microtest_case_geometry,
    unpack_stage62_microtest_record,
)

WRAPPER_PATH = ROOT / "scripts/hw/run_p7_ps_application_stage_safe.py"
WRAPPER_SPEC = importlib.util.spec_from_file_location(
    "p7_stage62_microtest_safe_wrapper", WRAPPER_PATH
)
assert WRAPPER_SPEC is not None and WRAPPER_SPEC.loader is not None
safe_wrapper = importlib.util.module_from_spec(WRAPPER_SPEC)
sys.modules[WRAPPER_SPEC.name] = safe_wrapper
WRAPPER_SPEC.loader.exec_module(safe_wrapper)


def build_valid_record(
    case_id: int = 2,
    transfer_length: int = 30,
    source_alignment: int = 0,
    destination_alignment: int = 0,
    run_id_crc32: int = 0xA1B2C3D4,
    control_crc32: int = 0x11223344,
) -> bytes:
    geometry = stage62_microtest_case_geometry(case_id)
    source_before, destination_before = build_stage62_microtest_fixtures(
        case_id, transfer_length, source_alignment, destination_alignment
    )
    source_after = source_before
    destination_after = bytearray(destination_before)
    source_offset = P7_STAGE62_MICROTEST_TARGET_OFFSET + source_alignment
    destination_offset = P7_STAGE62_MICROTEST_TARGET_OFFSET + destination_alignment
    destination_after[
        destination_offset : destination_offset + transfer_length
    ] = source_before[source_offset : source_offset + transfer_length]
    snapshots = (
        source_before,
        source_after,
        destination_before,
        bytes(destination_after),
    )
    words = [0] * 128
    words[0] = P7_STAGE62_MICROTEST_RECORD_MAGIC
    words[1] = P7_STAGE62_MICROTEST_VERSION
    words[2] = P7_STAGE62_MICROTEST_RECORD_BYTES
    words[3] = 1
    words[5] = 3
    words[6] = 0
    words[8] = case_id
    words[9] = transfer_length
    words[10] = int(geometry["source_fixture_address"])
    words[11] = int(geometry["destination_fixture_address"])
    words[12] = words[10] + source_offset
    words[13] = words[11] + destination_offset
    words[14] = source_alignment
    words[15] = destination_alignment
    words[16] = words[12] & 3
    words[17] = words[13] & 3
    words[18] = words[12] & 63
    words[19] = words[13] & 63
    words[20] = int(geometry["source_space"])
    words[21] = int(geometry["destination_space"])
    words[23] = 0xFFFFFFFF
    words[24:30] = [0x100] * 6
    words[30:37] = [1] * 7
    words[37] = 1
    words[38] = 1
    words[40] = P7_STAGE62_MICROTEST_SOURCE_GUARD
    words[41] = P7_STAGE62_MICROTEST_DESTINATION_GUARD
    words[42] = P7_STAGE62_MICROTEST_DESTINATION_CANARY
    words[43] = int(geometry["pattern_base"])
    words[45] = 0x1FF00
    words[52:60] = [0xFFFFFFFF] * 8
    words[67] = run_id_crc32
    words[68] = control_crc32
    words[69] = 1
    words[70] = 1
    words[71] = 0
    for index, snapshot in enumerate(snapshots):
        words[72 + index] = zlib.crc32(snapshot) & 0xFFFFFFFF
    words[76] = 0x00021000
    words[77] = P7_STAGE62_MICROTEST_RECORD_BYTES
    words[78] = source_offset
    words[79] = destination_offset
    raw = bytearray(P7_STAGE62_MICROTEST_RECORD_BYTES)
    raw[:P7_STAGE62_MICROTEST_HEADER_BYTES] = struct.pack("<128I", *words)
    digest_offset = 80 * 4
    for index, snapshot in enumerate(snapshots):
        raw[digest_offset + index * 32 : digest_offset + (index + 1) * 32] = (
            hashlib.sha256(snapshot).digest()
        )
        start = P7_STAGE62_MICROTEST_HEADER_BYTES + index * 256
        raw[start : start + 256] = snapshot
    raw[0:4] = b"\x00" * 4
    raw[16:20] = b"\x00" * 4
    record_crc = zlib.crc32(raw) & 0xFFFFFFFF
    struct.pack_into("<I", raw, 16, record_crc)
    struct.pack_into("<I", raw, 0, P7_STAGE62_MICROTEST_RECORD_MAGIC)
    return bytes(raw)


class P7Stage62MicrotestTest(unittest.TestCase):
    def test_control_is_run_bound_crc_protected_and_zero_coverage(self):
        control, identity = safe_wrapper.build_stage62_microtest_control(
            run_id="p7_stage62_microtest_r35",
            case_name="C",
            transfer_length=31,
            source_alignment=2,
            destination_alignment=3,
        )
        self.assertEqual(len(control), 64)
        words = struct.unpack("<16I", control)
        self.assertEqual(words[0], safe_wrapper.P7_STAGE62_MICROTEST_CONTROL_MAGIC)
        self.assertEqual(words[2:6], (3, 31, 2, 3))
        self.assertEqual(words[7], zlib.crc32(control[:28]) & 0xFFFFFFFF)
        self.assertEqual(words[8], 1)
        self.assertEqual(words[14:16], (1, 0))
        self.assertEqual(words[6], identity["run_id_crc32"])
        self.assertEqual(words[7], identity["immutable_crc32"])

    def test_wrapper_builds_exact_a_to_d_geometry_and_rejects_tamper(self):
        expected_geometry = {
            "A": (0x00022400, 0x00022500),
            "B": (0x00022400, 0x00900000),
            "C": (0x00100000, 0x00022500),
            "D": (0x00100000, 0x00900000),
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "unused_input.bin"
            input_path.write_bytes(b"stage62-only")
            last_bundle = None
            for index, case_name in enumerate("ABCD"):
                bundle = safe_wrapper.build_stage_bundle(
                    bundle_dir=root / f"bundle_{case_name}",
                    mode="stage62-microtest",
                    input_path=input_path,
                    max_runtime_sec=60,
                    calibration_sec=0,
                    acceptance_sec=0,
                    sample_interval_sec=10,
                    idle_margin_sec=10,
                    stationary_object_bytes=64 * 1024,
                    run_id=f"p7_stage62_microtest_r{35 + index}",
                    execution_scope="STAGE62_ONLY",
                    diagnostic_only=True,
                    stage62_microtest_case=case_name,
                    microtest_length=29 + index,
                    microtest_source_alignment=index,
                    microtest_destination_alignment=3 - index,
                )
                safe_wrapper.verify_bundle_integrity(bundle)
                micro = bundle.stage62_microtest
                self.assertIsInstance(micro, dict)
                assert micro is not None
                self.assertEqual(
                    (
                        micro["source_fixture_address"],
                        micro["destination_fixture_address"],
                    ),
                    expected_geometry[case_name],
                )
                self.assertEqual(bundle.cases, [])
                self.assertEqual(bundle.boundary_cases, [])
                plan = bundle.plan_path.read_text(encoding="utf-8")
                self.assertIn("EXECUTION_SCOPE STAGE62_ONLY", plan)
                self.assertIn("DIAGNOSTIC_ONLY 1", plan)
                self.assertIn("COVERAGE_CLAIMED 0", plan)
                self.assertIn("CASE_COUNT 0", plan)
                self.assertIn(f"MICROTEST_CASE {case_name}", plan)
                last_bundle = bundle
            assert last_bundle is not None
            control_path = last_bundle.directory / "stage62_microtest_control.bin"
            tampered = bytearray(control_path.read_bytes())
            tampered[4] ^= 1
            control_path.write_bytes(tampered)
            with self.assertRaisesRegex(RuntimeError, "microtest control|integrity"):
                safe_wrapper.verify_bundle_integrity(last_bundle)

    def test_complete_host_postprocess_accepts_valid_copy_and_wipe_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "unused_input.bin"
            input_path.write_bytes(b"stage62-only")
            bundle = safe_wrapper.build_stage_bundle(
                bundle_dir=root / "bundle_A",
                mode="stage62-microtest",
                input_path=input_path,
                max_runtime_sec=60,
                calibration_sec=0,
                acceptance_sec=0,
                sample_interval_sec=10,
                idle_margin_sec=10,
                stationary_object_bytes=64 * 1024,
                run_id="p7_stage62_microtest_postprocess",
                execution_scope="STAGE62_ONLY",
                diagnostic_only=True,
                stage62_microtest_case="A",
                microtest_length=30,
                microtest_source_alignment=0,
                microtest_destination_alignment=0,
            )
            micro = bundle.stage62_microtest
            self.assertIsInstance(micro, dict)
            assert micro is not None

            control_input = (
                bundle.directory / "stage62_microtest_control.bin"
            ).read_bytes()
            source_input = (
                bundle.directory / "stage62_microtest_source_fixture.bin"
            ).read_bytes()
            destination_input = (
                bundle.directory / "stage62_microtest_destination_fixture.bin"
            ).read_bytes()
            (bundle.directory / "stage62_microtest_control_prestart.bin").write_bytes(
                control_input
            )
            (bundle.directory / "stage62_microtest_source_prestart.bin").write_bytes(
                source_input
            )
            (
                bundle.directory / "stage62_microtest_destination_prestart.bin"
            ).write_bytes(destination_input)

            control_final = bytearray(control_input)
            struct.pack_into(
                "<8I",
                control_final,
                8 * 4,
                3,
                0,
                safe_wrapper.P7_STAGE62_DIAGNOSTIC_ADDRESS,
                P7_STAGE62_MICROTEST_RECORD_BYTES,
                P7_STAGE62_MICROTEST_RECORD_MAGIC,
                1,
                1,
                0,
            )
            (bundle.directory / "stage62_microtest_control_final.bin").write_bytes(
                control_final
            )
            (bundle.directory / "stage62_microtest_record_result.bin").write_bytes(
                build_valid_record(
                    case_id=1,
                    run_id_crc32=int(micro["run_id_crc32"]),
                    control_crc32=int(micro["immutable_crc32"]),
                )
            )
            (bundle.directory / "stage62_microtest_source_final.bin").write_bytes(
                source_input
            )
            destination_final = bytearray(destination_input)
            destination_offset = int(micro["destination_target_offset"])
            destination_final[destination_offset : destination_offset + 30] = (
                b"\x00" * 30
            )
            (
                bundle.directory / "stage62_microtest_destination_final.bin"
            ).write_bytes(destination_final)

            result = safe_wrapper.postprocess_stage62_microtest(
                bundle,
                "\n".join(
                    (
                        "P7_STAGE62_MICROTEST=1",
                        "P7_STAGE62_MICROTEST_CASE=A",
                        "P7_STAGE62_MICROTEST_DIAGNOSTIC_ONLY=1",
                        "P7_STAGE62_MICROTEST_COVERAGE_CLAIMED=0",
                        "P7_STAGE62_MICROTEST_STAGE62_EXECUTED=0",
                    )
                ),
            )
            self.assertTrue(result["passed"], result["failures"])
            self.assertEqual(result["independent_readback_classification"], "COPY_OK")
            self.assertTrue(result["output_wipe_verified"])
            self.assertFalse(result["stage62_executed"])

    def test_firmware_initializes_copy_ok_terminal_metadata(self):
        source = (
            ROOT / "software/ps_driver/p7_stage62_microtest.c"
        ).read_text(encoding="utf-8")
        validation = source.index("if (valid_control != 0U) {")
        self.assertLess(
            source.index("record->first_bad_index = UINT32_MAX;"), validation
        )
        self.assertLess(
            source.index("record->expected_byte = UINT32_C(0x100);"), validation
        )
        self.assertLess(
            source.index("record->observed_byte = UINT32_C(0x100);"), validation
        )
        error_clear = source.index(
            "record->error_code = P7_STAGE62_MICROTEST_ERROR_NONE;",
            validation,
        )
        self.assertLess(error_clear, source.index("source_fixture =", validation))

    def test_tcl_microtest_branch_is_isolated_and_dumps_before_failure(self):
        tcl = (ROOT / "scripts/hw/p7_ps_application_execute.tcl").read_text(
            encoding="utf-8"
        )
        start = tcl.index('if {$mode eq "stage62-microtest"} {', tcl.index("rst -processor"))
        end = tcl.index("} else {\n  set host_input_start_ms", start)
        block = tcl[start:end]
        self.assertLess(block.index("dow $elf_file"), block.index("stage62_microtest_control.bin"))
        self.assertLess(block.index("P7_STAGE62_MICROTEST_PRESTART_READBACK=PASS"), block.index("\n    con\n"))
        self.assertLess(block.index("catch {stop}"), block.index("stage62_microtest_record_result.bin"))
        self.assertNotIn("p7_wait_service_ready", block)
        self.assertNotIn("mwr 0x0002000C", block)
        self.assertNotIn("0x43C00000", block)
        self.assertIn("P7_STAGE62_MICROTEST_STAGE62_EXECUTED=0", block)
        catch_block = tcl[tcl.index("if {$rc != 0}") :]
        self.assertIn('if {$mode ne "stage62-microtest"}', catch_block)

    def test_fixture_matrix_is_nonzero_distinguishable_and_guarded(self):
        cases = 0
        patterns = set()
        for case_id in range(1, 5):
            for transfer_length in range(29, 33):
                for source_alignment in range(4):
                    for destination_alignment in range(4):
                        source, destination = build_stage62_microtest_fixtures(
                            case_id,
                            transfer_length,
                            source_alignment,
                            destination_alignment,
                        )
                        source_offset = (
                            P7_STAGE62_MICROTEST_TARGET_OFFSET + source_alignment
                        )
                        destination_offset = (
                            P7_STAGE62_MICROTEST_TARGET_OFFSET
                            + destination_alignment
                        )
                        payload = source[
                            source_offset : source_offset + transfer_length
                        ]
                        self.assertNotIn(0, payload)
                        self.assertNotEqual(payload[0], 0)
                        self.assertTrue(
                            all(
                                byte == P7_STAGE62_MICROTEST_SOURCE_GUARD
                                for byte in source[:source_offset]
                            )
                        )
                        self.assertEqual(
                            destination[
                                destination_offset : destination_offset
                                + transfer_length
                            ],
                            bytes([P7_STAGE62_MICROTEST_DESTINATION_CANARY])
                            * transfer_length,
                        )
                        self.assertTrue(
                            all(
                                byte == P7_STAGE62_MICROTEST_DESTINATION_GUARD
                                for byte in destination[:destination_offset]
                            )
                        )
                        patterns.add((case_id, payload))
                        cases += 1
        self.assertEqual(cases, 256)
        self.assertEqual(len(patterns), 16)

    def test_valid_record_round_trip(self):
        parsed = unpack_stage62_microtest_record(build_valid_record())
        self.assertEqual(parsed["case"], "B")
        self.assertEqual(parsed["classification"], 0)
        self.assertTrue(parsed["diagnostic_only"])
        self.assertFalse(parsed["coverage_claimed"])
        self.assertEqual(parsed["transfer_length"], 30)

    def test_snapshot_tamper_is_rejected(self):
        raw = bytearray(build_valid_record())
        raw[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "record CRC32"):
            unpack_stage62_microtest_record(bytes(raw))

    def test_digest_tamper_with_recomputed_record_crc_is_rejected(self):
        raw = bytearray(build_valid_record())
        raw[80 * 4] ^= 1
        raw[0:4] = b"\x00" * 4
        raw[16:20] = b"\x00" * 4
        struct.pack_into("<I", raw, 16, zlib.crc32(raw) & 0xFFFFFFFF)
        struct.pack_into("<I", raw, 0, P7_STAGE62_MICROTEST_RECORD_MAGIC)
        with self.assertRaisesRegex(ValueError, "snapshot SHA256"):
            unpack_stage62_microtest_record(bytes(raw))


if __name__ == "__main__":
    unittest.main()
