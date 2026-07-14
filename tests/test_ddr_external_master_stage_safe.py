import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
import tkinter
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WRAPPER_PATH = ROOT / "scripts/hw/run_p7_ps_application_stage_safe.py"
WRAPPER_SPEC = importlib.util.spec_from_file_location(
    "p7_ddr_external_master_safe_wrapper", WRAPPER_PATH
)
assert WRAPPER_SPEC is not None and WRAPPER_SPEC.loader is not None
safe_wrapper = importlib.util.module_from_spec(WRAPPER_SPEC)
sys.modules[WRAPPER_SPEC.name] = safe_wrapper
WRAPPER_SPEC.loader.exec_module(safe_wrapper)


RUN_ID = "p7_20260714_ddr_external_r38_stage62_fixture_rep1"
FIXTURE_SHA256 = (
    "b7ef71102905bfadd7b60c7ff310f2a9adf2a31f327c18c2c9c1411119ea7776"
)


def build_bundle(root: Path) -> safe_wrapper.StageBundle:
    input_path = root / "unused_input.bin"
    input_path.write_bytes(b"DDR external-master diagnostic does not start the ELF")
    return safe_wrapper.build_stage_bundle(
        bundle_dir=root / "bundle",
        mode="ddr-external-master",
        input_path=input_path,
        max_runtime_sec=60,
        calibration_sec=0,
        acceptance_sec=0,
        sample_interval_sec=10,
        idle_margin_sec=60,
        stationary_object_bytes=64 * 1024,
        run_id=RUN_ID,
        execution_scope="STAGE62_ONLY",
        diagnostic_only=True,
        ddr_pattern="stage62_fixture",
        ddr_address="0x00900000",
        ddr_access_method="download",
        ddr_repetition=1,
        ddr_unaligned_accesses=False,
        ddr_fixture_sha256=FIXTURE_SHA256,
    )


def successful_markers() -> str:
    return "\n".join(
        (
            "P7_DDR_EXTERNAL_MASTER=1",
            "P7_DDR_EXTERNAL_PATTERN=stage62_fixture",
            "P7_DDR_EXTERNAL_ADDRESS=0x00900000",
            "P7_DDR_EXTERNAL_ACCESS_METHOD=download",
            "P7_DDR_EXTERNAL_LENGTH=256",
            "P7_DDR_EXTERNAL_REPETITION=1",
            "P7_DDR_EXTERNAL_UNALIGNED_ACCESSES=0",
            f"P7_DDR_EXTERNAL_FIXTURE_SHA256={FIXTURE_SHA256}",
            "P7_DDR_EXTERNAL_DIAGNOSTIC_ONLY=1",
            "P7_DDR_EXTERNAL_COVERAGE_CLAIMED=0",
            "P7_DDR_EXTERNAL_CPU_RELEASED=0",
            "P7_DDR_EXTERNAL_STAGE62_EXECUTED=0",
            "P7_DDR_EXTERNAL_WRITE_ATTEMPTED=1",
            "P7_DDR_EXTERNAL_READBACK_CAPTURED=1",
            "P7_DDR_EXTERNAL_READBACK=PASS",
        )
    )


class DdrExternalMasterStageSafeTests(unittest.TestCase):
    def test_stage62_fixture_is_exact_and_bundle_is_zero_coverage(self) -> None:
        payload = safe_wrapper.build_ddr_external_fixture("stage62_fixture")
        self.assertEqual(256, len(payload))
        self.assertEqual(0xC3, payload[9])
        self.assertEqual(FIXTURE_SHA256, hashlib.sha256(payload).hexdigest())

        with tempfile.TemporaryDirectory() as temp:
            bundle = build_bundle(Path(temp))
            safe_wrapper.verify_bundle_integrity(bundle)
            self.assertEqual([], bundle.cases)
            self.assertEqual([], bundle.boundary_cases)
            self.assertIsNone(bundle.stage62_microtest)
            self.assertIsInstance(bundle.ddr_external_master, dict)
            plan = bundle.plan_path.read_text(encoding="utf-8")
            for line in (
                "MODE ddr-external-master",
                "EXECUTION_SCOPE STAGE62_ONLY",
                "DIAGNOSTIC_ONLY 1",
                "COVERAGE_CLAIMED 0",
                "DDR_EXTERNAL_PATTERN stage62_fixture",
                "DDR_EXTERNAL_ADDRESS 0x00900000",
                "DDR_EXTERNAL_ACCESS_METHOD download",
                "DDR_EXTERNAL_LENGTH 256",
                f"DDR_EXTERNAL_FIXTURE_SHA256 {FIXTURE_SHA256}",
                "CASE_COUNT 0",
                "BOUNDARY_COUNT 0",
                "CHECKPOINT_COUNT 0",
            ):
                self.assertIn(line, plan)
            manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["diagnostic_only"])
            self.assertFalse(manifest["coverage_claimed"])
            self.assertFalse(manifest["hardware_actions_executed"])
            self.assertEqual("PENDING_HW", manifest["HARDWARE_ACCEPTANCE"])

            fixture = bundle.directory / "ddr_external_master_fixture.bin"
            tampered = bytearray(fixture.read_bytes())
            tampered[9] = 0
            fixture.write_bytes(tampered)
            with self.assertRaisesRegex(RuntimeError, "DDR external-master fixture|integrity"):
                safe_wrapper.verify_bundle_integrity(bundle)

    def test_postprocess_preserves_raw_first_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            bundle = build_bundle(Path(temp))
            fixture = (bundle.directory / "ddr_external_master_fixture.bin").read_bytes()
            readback = bundle.directory / "ddr_external_master_readback.bin"
            readback.write_bytes(fixture)
            passed = safe_wrapper.postprocess_ddr_external_master(
                bundle, successful_markers()
            )
            self.assertTrue(passed["passed"], passed["failures"])
            self.assertFalse(passed["cpu_released"])
            self.assertFalse(passed["stage62_executed"])

            corrupted = bytearray(fixture)
            corrupted[9] = 0
            readback.write_bytes(corrupted)
            failed = safe_wrapper.postprocess_ddr_external_master(
                bundle, successful_markers()
            )
            self.assertFalse(failed["passed"])
            self.assertEqual(1, failed["comparison"]["mismatch_count"])
            self.assertEqual(
                {
                    "offset": 9,
                    "absolute_address": "0x00900009",
                    "expected": 0xC3,
                    "observed": 0,
                },
                failed["comparison"]["first_mismatch"],
            )

    def test_authorization_extension_binds_run_and_fixture_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutdown_hash = "a" * 64
            args = argparse.Namespace(
                authorization_file=str(root / "authorization.txt"),
                mode="ddr-external-master",
                stage62_only=True,
                run_id=RUN_ID,
                ddr_pattern="stage62_fixture",
                ddr_address="0x00900000",
                ddr_access_method="download",
                ddr_repetition=1,
                ddr_unaligned_accesses=False,
                ddr_fixture_file=str(root / "fixture.bin"),
                ddr_fixture_sha256=FIXTURE_SHA256,
                ddr_run_configuration=str(root / "run_configuration.json"),
                ddr_run_configuration_sha256="8" * 64,
                ddr_artifact_manifest=str(root / "artifact_manifest.json"),
                ddr_artifact_manifest_sha256="9" * 64,
                ps7_init=str(root / "ps7_init.tcl"),
                ps7_init_sha256="1" * 64,
                p6_build_summary=str(root / "p6.json"),
                p6_build_summary_sha256="2" * 64,
                p7_build_summary=str(root / "p7.json"),
                p7_build_summary_sha256="3" * 64,
                input_file=str(root / "input.bin"),
                input_sha256="4" * 64,
                core_readiness_attestation=str(root / "core.json"),
                core_readiness_attestation_sha256="5" * 64,
                active_profile=str(root / "active.json"),
                active_profile_sha256="6" * 64,
                lane1_promotion_summary=str(root / "lane1.json"),
                lane1_promotion_summary_sha256="7" * 64,
                shutdown_bitstream_sha256=shutdown_hash,
            )
            fields = {
                "PS7_INIT_PATH": args.ps7_init,
                "PS7_INIT_SHA256": args.ps7_init_sha256,
                "P6_PS_BUILD_SUMMARY_PATH": args.p6_build_summary,
                "P6_PS_BUILD_SUMMARY_SHA256": args.p6_build_summary_sha256,
                "P7_PS_BUILD_SUMMARY_PATH": args.p7_build_summary,
                "P7_PS_BUILD_SUMMARY_SHA256": args.p7_build_summary_sha256,
                "P7_INPUT_PATH": args.input_file,
                "P7_INPUT_SHA256": args.input_sha256,
                "P7_PS_MODE": args.mode,
                "P7_PS_CORE_READINESS": "PASS",
                "P7_PS_CORE_READINESS_PATH": args.core_readiness_attestation,
                "P7_PS_CORE_READINESS_SHA256": args.core_readiness_attestation_sha256,
                "ACTIVE_PROFILE_PATH": args.active_profile,
                "ACTIVE_PROFILE_SHA256": args.active_profile_sha256,
                "P7_LANE1_PROMOTION_SUMMARY_PATH": args.lane1_promotion_summary,
                "P7_LANE1_PROMOTION_SUMMARY_SHA256": args.lane1_promotion_summary_sha256,
                "P7_FROZEN_SHUTDOWN_PATH": str(
                    safe_wrapper.frozen_shutdown_path(args)
                ),
                "P7_FROZEN_SHUTDOWN_SHA256": shutdown_hash,
                "P7_COUNTS_PER_SECOND": str(safe_wrapper.P7_COUNTS_PER_SECOND),
                "P7_RUN_ID": RUN_ID,
                "P7_EXECUTION_SCOPE": "STAGE62_ONLY",
                "P7_DIAGNOSTIC_ONLY": "true",
                "P7_COVERAGE_CLAIMED": "false",
                "P7_DDR_EXTERNAL_PATTERN": "stage62_fixture",
                "P7_DDR_EXTERNAL_FIXTURE_PATH": args.ddr_fixture_file,
                "P7_DDR_EXTERNAL_ADDRESS": "0x00900000",
                "P7_DDR_EXTERNAL_ACCESS_METHOD": "download",
                "P7_DDR_EXTERNAL_LENGTH": "256",
                "P7_DDR_EXTERNAL_REPETITION": "1",
                "P7_DDR_EXTERNAL_UNALIGNED_ACCESSES": "false",
                "P7_DDR_EXTERNAL_FIXTURE_SHA256": FIXTURE_SHA256,
                "P7_DDR_RUN_CONFIGURATION_PATH": args.ddr_run_configuration,
                "P7_DDR_RUN_CONFIGURATION_SHA256": args.ddr_run_configuration_sha256,
                "P7_DDR_ARTIFACT_MANIFEST_PATH": args.ddr_artifact_manifest,
                "P7_DDR_ARTIFACT_MANIFEST_SHA256": args.ddr_artifact_manifest_sha256,
            }
            auth = Path(args.authorization_file)
            auth.write_text(
                "\n".join(f"{key}={value}" for key, value in fields.items()) + "\n",
                encoding="utf-8",
            )
            self.assertEqual([], safe_wrapper._authorization_extension_errors(args))
            fields["P7_DDR_EXTERNAL_FIXTURE_SHA256"] = "f" * 64
            auth.write_text(
                "\n".join(f"{key}={value}" for key, value in fields.items()) + "\n",
                encoding="utf-8",
            )
            self.assertIn(
                "authorization extension field mismatch: P7_DDR_EXTERNAL_FIXTURE_SHA256",
                safe_wrapper._authorization_extension_errors(args),
            )

    def test_tcl_branch_never_releases_cpu_or_touches_pl_mmio(self) -> None:
        tcl = (ROOT / "scripts/hw/p7_ps_application_execute.tcl").read_text(
            encoding="utf-8"
        )
        reset = tcl.index("rst -processor")
        start = tcl.index('if {$mode eq "ddr-external-master"} {', reset)
        end = tcl.index('} elseif {$mode eq "stage62-microtest"} {', start)
        block = tcl[start:end]
        for required in (
            "dow -data $ddr_fixture_path $ddr_address",
            "mwr -size b -bin -file $ddr_fixture_path $ddr_address 256",
            "p7_ddr_external_scalar_write",
            "mrd -value -size w",
            "p7_atomic_dump $ddr_readback_path $ddr_address 256",
            "p7_require_files_equal",
            "P7_DDR_EXTERNAL_CPU_RELEASED=0",
            "P7_DDR_EXTERNAL_STAGE62_EXECUTED=0",
        ):
            self.assertIn(required, block)
        for forbidden in (
            "dow $elf_file",
            "\n    con\n",
            "0x43C00000",
            "mwr 0x0002000C",
            "P7_PS_ELF_DOWNLOADED",
        ):
            self.assertNotIn(forbidden, block)
        self.assertLess(
            block.index("P7_DDR_EXTERNAL_WRITE_ATTEMPTED=1"),
            block.index("switch -- $plan_value(DDR_EXTERNAL_ACCESS_METHOD)"),
        )
        self.assertLess(
            block.index("mrd -value -size w"),
            block.index("p7_atomic_dump $ddr_readback_path"),
        )
        self.assertLess(
            block.index("p7_atomic_dump $ddr_readback_path"),
            block.index("P7_DDR_EXTERNAL_READBACK=PASS"),
        )

    def test_tcl_scalar_write_command_matches_run_configuration(self) -> None:
        tcl = (ROOT / "scripts/hw/p7_ps_application_execute.tcl").read_text(
            encoding="utf-8"
        )
        start = tcl.index("proc p7_ddr_external_scalar_write")
        end = tcl.index("proc p7_zero_words_and_verify", start)
        scalar_write_proc = tcl[start:end]

        def capture_commands(fixture: Path, address: str, unaligned: bool) -> list[tuple[str, ...]]:
            interpreter = tkinter.Tcl()
            interpreter.eval(
                """
                proc p7_read_binary_exact {path expected_size} {
                  set handle [open $path rb]
                  fconfigure $handle -translation binary
                  set data [read $handle]
                  close $handle
                  if {[string length $data] != $expected_size} {
                    error "unexpected fixture size"
                  }
                  return $data
                }
                """
            )
            commands: list[tuple[str, ...]] = []
            interpreter.createcommand(
                "mwr", lambda *args: commands.append(tuple(args)) or ""
            )
            interpreter.eval(scalar_write_proc)
            interpreter.call(
                "p7_ddr_external_scalar_write",
                str(fixture),
                address,
                "h",
                1 if unaligned else 0,
            )
            return commands

        cases = (
            ("aligned", "0x00900000", False),
            ("unaligned", "0x00900001", True),
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "unused_input.bin"
            input_path.write_bytes(b"offline command-generation regression")
            for label, address, unaligned in cases:
                bundle = safe_wrapper.build_stage_bundle(
                    bundle_dir=root / label / "bundle",
                    mode="ddr-external-master",
                    input_path=input_path,
                    max_runtime_sec=60,
                    calibration_sec=0,
                    acceptance_sec=0,
                    sample_interval_sec=10,
                    idle_margin_sec=60,
                    stationary_object_bytes=64 * 1024,
                    run_id=f"p7_20260714_ddr_external_regression_{label}",
                    execution_scope="STAGE62_ONLY",
                    diagnostic_only=True,
                    ddr_pattern="stage62_fixture",
                    ddr_address=address,
                    ddr_access_method="halfword",
                    ddr_repetition=1,
                    ddr_unaligned_accesses=unaligned,
                    ddr_fixture_sha256=FIXTURE_SHA256,
                )
                plan = {
                    key: value
                    for key, value in (
                        line.split(" ", 1)
                        for line in bundle.plan_path.read_text(encoding="utf-8").splitlines()
                        if " " in line
                    )
                }
                run_configuration = {
                    "address": address.lower(),
                    "access_method": "halfword",
                    "unaligned_accesses": unaligned,
                }
                self.assertEqual(run_configuration["address"], plan["DDR_EXTERNAL_ADDRESS"])
                self.assertEqual(
                    run_configuration["access_method"],
                    plan["DDR_EXTERNAL_ACCESS_METHOD"],
                )
                self.assertEqual(
                    "1" if run_configuration["unaligned_accesses"] else "0",
                    plan["DDR_EXTERNAL_UNALIGNED_ACCESSES"],
                )

                commands = capture_commands(
                    bundle.directory / "ddr_external_master_fixture.bin",
                    plan["DDR_EXTERNAL_ADDRESS"],
                    plan["DDR_EXTERNAL_UNALIGNED_ACCESSES"] == "1",
                )
                self.assertEqual(128, len(commands))
                for index, command in enumerate(commands):
                    self.assertEqual(("-size", "h"), command[:2])
                    self.assertNotIn("-unaligned-accesses", command)
                    self.assertEqual(
                        1 if unaligned else 0,
                        command.count("-unaligned-access"),
                    )
                    address_index = 3 if unaligned else 2
                    if unaligned:
                        self.assertEqual("-unaligned-access", command[2])
                    self.assertEqual(int(address, 16) + index * 2, int(command[address_index]))
                    self.assertRegex(command[address_index + 1], r"^0x[0-9A-F]{4}$")
                    self.assertEqual("1", command[address_index + 2])
                    self.assertEqual(address_index + 3, len(command))

    def test_resume_manifest_and_run_configuration_are_fully_bound(self) -> None:
        authorization_root = ROOT / ".hardware_authorization"
        authorization_root.mkdir(parents=True, exist_ok=True)
        source_commit = "a" * 40
        with tempfile.TemporaryDirectory(
            dir=authorization_root, prefix="ddr_resume_test_"
        ) as temp:
            root = Path(temp)
            fixture = root / "fixture.bin"
            fixture.write_bytes(
                safe_wrapper.build_ddr_external_fixture("stage62_fixture")
            )
            fixture_sha = hashlib.sha256(fixture.read_bytes()).hexdigest()

            paths = {}
            for role in (
                "elf",
                "linker_map",
                "disassembly",
                "bitstream",
                "xsa",
                "platform_ps7_init",
                "shutdown_bitstream",
            ):
                path = root / f"{role}.bin"
                path.write_bytes((role + "\n").encode("ascii"))
                paths[role] = path

            run_configuration_path = root / "run_configuration.json"
            run_configuration = {
                "schema": safe_wrapper.DDR_RUN_CONFIGURATION_SCHEMA,
                "run_id": RUN_ID,
                "source_commit": source_commit,
                "mode": "ddr-external-master",
                "execution_scope": "STAGE62_ONLY",
                "stage62_only": True,
                "diagnostic_only": True,
                "coverage_claimed": False,
                "functional_stages_1_61_executed": False,
                "stage62_executed": False,
                "stationary_executed": False,
                "historical_run_reused": False,
                "pattern": "stage62_fixture",
                "address": "0x00900000",
                "access_method": "download",
                "length": 256,
                "repetition": 1,
                "unaligned_accesses": False,
                "max_runtime_sec": 60,
                "fixture_path": str(fixture.resolve()),
                "fixture_sha256": fixture_sha,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
            run_configuration_path.write_text(
                json.dumps(run_configuration), encoding="utf-8"
            )
            run_configuration_sha = hashlib.sha256(
                run_configuration_path.read_bytes()
            ).hexdigest()

            args = argparse.Namespace(
                run_id=RUN_ID,
                source_commit=source_commit,
                max_runtime_sec=60,
                ddr_pattern="stage62_fixture",
                ddr_address="0x00900000",
                ddr_access_method="download",
                ddr_repetition=1,
                ddr_unaligned_accesses=False,
                ddr_fixture_file=str(fixture.resolve()),
                ddr_fixture_sha256=fixture_sha,
                ddr_run_configuration=str(run_configuration_path.resolve()),
                ddr_run_configuration_sha256=run_configuration_sha,
                ddr_artifact_manifest=str((root / "artifact_manifest.json").resolve()),
                ddr_artifact_manifest_sha256="",
                elf=str(paths["elf"].resolve()),
                elf_sha256=hashlib.sha256(paths["elf"].read_bytes()).hexdigest(),
                bitstream=str(paths["bitstream"].resolve()),
                bitstream_sha256=hashlib.sha256(
                    paths["bitstream"].read_bytes()
                ).hexdigest(),
                xsa=str(paths["xsa"].resolve()),
                xsa_sha256=hashlib.sha256(paths["xsa"].read_bytes()).hexdigest(),
                ps7_init=str(paths["platform_ps7_init"].resolve()),
                ps7_init_sha256=hashlib.sha256(
                    paths["platform_ps7_init"].read_bytes()
                ).hexdigest(),
                shutdown_bitstream=str(paths["shutdown_bitstream"].resolve()),
                shutdown_bitstream_sha256=hashlib.sha256(
                    paths["shutdown_bitstream"].read_bytes()
                ).hexdigest(),
            )

            role_paths = {
                **paths,
                "fixture": fixture,
                "microtest_image": fixture,
                "runner_python": Path(safe_wrapper.__file__).resolve(),
                "runner_tcl": safe_wrapper.PS_EXECUTE_TCL.resolve(),
                "parser": (ROOT / "tools/ddr_external_master_diagnostic.py").resolve(),
                "run_configuration": run_configuration_path,
            }
            records = []
            for role, path in role_paths.items():
                records.append(
                    {
                        "role": role,
                        "absolute_path": str(path.resolve()),
                        "size_bytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "git_commit": source_commit,
                        "actual_run_input": role not in {"linker_map", "disassembly"},
                    }
                )
            manifest_path = Path(args.ddr_artifact_manifest)
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": safe_wrapper.DDR_RESUME_ARTIFACT_SCHEMA,
                        "run_id": RUN_ID,
                        "source_commit": source_commit,
                        "status": "READY_FOR_HUMAN_AUTHORIZATION",
                        "hardware_actions_executed": False,
                        "human_authorization_required": True,
                        "HARDWARE_ACCEPTANCE": "PENDING_HW",
                        "artifacts": records,
                    }
                ),
                encoding="utf-8",
            )
            args.ddr_artifact_manifest_sha256 = hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest()
            self.assertEqual([], safe_wrapper._ddr_resume_artifact_errors(args))

            records[0]["sha256"] = "f" * 64
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema": safe_wrapper.DDR_RESUME_ARTIFACT_SCHEMA,
                        "run_id": RUN_ID,
                        "source_commit": source_commit,
                        "status": "READY_FOR_HUMAN_AUTHORIZATION",
                        "hardware_actions_executed": False,
                        "human_authorization_required": True,
                        "HARDWARE_ACCEPTANCE": "PENDING_HW",
                        "artifacts": records,
                    }
                ),
                encoding="utf-8",
            )
            args.ddr_artifact_manifest_sha256 = hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest()
            self.assertIn(
                "DDR artifact manifest SHA256 mismatch: elf",
                safe_wrapper._ddr_resume_artifact_errors(args),
            )

    def test_preparation_tool_cannot_grant_or_launch_hardware(self) -> None:
        source = (ROOT / "tools/prepare_ddr_resume_gate.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("never creates a granted authorization file", source)
        self.assertIn("# P7_STATIONARY_APP_LAYER_APPROVED", source)
        self.assertIn(
            "USER_HARDWARE_AUTHORIZATION_FOR_P7=REQUIRES_HUMAN_GRANT", source
        )
        self.assertIn("authorization_environment_modified\": False", source)
        self.assertNotIn("os.environ[\"RF_COMM_HW_AUTH\"]", source)
        self.assertNotIn("subprocess.run(command", source)

    def test_preparation_tool_binds_rebuilt_ps_artifacts_to_source_commit(self) -> None:
        source = (ROOT / "tools/prepare_ddr_resume_gate.py").read_text(
            encoding="utf-8"
        )
        roles = ("bitstream", "xsa", "platform_xsa", "platform_ps7_init")
        for index, role in enumerate(roles[:-1]):
            start = source.index(f'role="{role}"')
            end = source.index(f'role="{roles[index + 1]}"', start)
            stanza = source[start:end]
            self.assertIn("git_commit=source_commit", stanza, role)
            self.assertIn(
                'provenance_kind="rebuilt_from_source_commit"', stanza, role
            )
            self.assertNotIn("STAGE62_PACKAGING_COMMIT", stanza, role)


if __name__ == "__main__":
    unittest.main()
