from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import summarize_p7_hardware as subject  # noqa: E402


COMMIT = "a" * 40
BOARD = "210512180081"
PART = "xc7z010clg400-1"
TARGET = "localhost:3121/xilinx_tcf/Digilent/210512180081"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SyntheticEvidence:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.commit = COMMIT
        self.hardware = root / "evidence" / "hardware" / "p7"
        self.output = root / "evidence" / "generated"
        self.hardware.mkdir(parents=True)
        self.artifact_dir = root / "frozen"
        self.artifact_dir.mkdir()
        self.artifacts: dict[str, Path] = {}
        for name, suffix in (
            ("plan", ".md"),
            ("bitstream", ".bit"),
            ("xsa", ".xsa"),
            ("elf", ".elf"),
            ("active_xdc", ".xdc"),
            ("pinmap", ".csv"),
            ("register_map", ".yaml"),
            ("shutdown_bitstream", ".bit"),
            ("ltx", ".ltx"),
        ):
            path = self.artifact_dir / f"{name}{suffix}"
            path.write_bytes(f"synthetic-{name}\n".encode())
            self.artifacts[name] = path
        self.functional_profile = self._profile("functional", 900)
        self.stationary_profile = self._profile("stationary", 1800)
        self.authorization_dir = root / ".hardware_authorization"
        self.authorization_dir.mkdir()
        readiness_sources: dict[str, str] = {}
        for relative in subject.CORE_READINESS_SOURCES:
            source = root / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source_text = f"synthetic readiness source: {relative}\n"
            if relative == "software/ps_driver/p7_app_service.c":
                source_text += (
                    "descriptor->status = P7_DESCRIPTOR_RUNNING;\n"
                    "object_start = p7_get_ticks();\n"
                    "p7_integrity_checked(input);\n"
                    "p7_integrity_checked(output);\n"
                    "object_end = p7_get_ticks();\n"
                )
            source.write_text(source_text, encoding="utf-8")
            readiness_sources[relative] = digest(source)
        self.readiness = self.artifact_dir / "core_readiness.json"
        self.readiness.write_text(
            json.dumps(
                {
                    "schema": "rf-comm-p7-ps-core-hardware-readiness-v1",
                    "P7_PS_CORE_HARDWARE_READINESS": "PASS",
                    "hardware_actions_executed": False,
                    "HARDWARE_ACCEPTANCE": "PENDING_HW",
                    "checks": {name: True for name in subject.CORE_READINESS_CHECKS},
                    "sources": readiness_sources,
                    "native_shutdown_test": {"returncode": 0},
                    "unit_tests": {"returncode": 0},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.sequence = 0

    def _profile(self, name: str, runtime: int) -> Path:
        path = self.artifact_dir / f"profile_{name}.json"
        path.write_text(
            json.dumps(
                {
                    "stage": name,
                    "network_required": False,
                    "motion_required": False,
                    "lane_count": 2,
                    "allowed_lane_masks": ["0x1", "0x2", "0x3"],
                    "max_lane_mask": "0x3",
                    "max_runtime_sec": runtime,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def _record(self, path: Path) -> dict[str, object]:
        value = digest(path)
        return {"path": str(path), "expected_sha256": value, "actual_sha256": value, "exists": True}

    def _safety(
        self,
        profile: Path,
        runtime: int,
        *,
        mode: str | None = None,
        stage_name: str | None = None,
        semantic_mode: str | None = None,
    ) -> dict[str, object]:
        records = {name: self._record(path) for name, path in self.artifacts.items()}
        records["profile"] = self._record(profile)
        authorization_fields = {
            "AUTHORIZED_STAGE": "P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET",
            "USER_HARDWARE_AUTHORIZATION_FOR_P7": "GRANTED",
            "SOURCE_COMMIT": self.commit,
            "SHUTDOWN_ON_EXIT": "required",
            "NO_ETHERNET": "true",
            "NO_MOTION": "true",
            "LANE_COUNT": "2",
            "MAX_LANE_MASK": "0x3",
            "MAX_RUNTIME_SEC": "1800",
            "BOARD_ID": BOARD,
            "EXPECTED_PART": PART,
            "EXPECTED_TARGET": TARGET,
        }
        for name, (path_key, sha_key) in subject.AUTH_ARTIFACT_KEYS.items():
            record = records[name]
            authorization_fields[path_key] = str(record["path"])
            authorization_fields[sha_key] = str(record["actual_sha256"])
        if mode is not None:
            authorization_fields.update(
                {
                    "P7_PS_MODE": mode,
                    "P7_PS_CORE_READINESS": "PASS",
                    "P7_PS_CORE_READINESS_PATH": str(self.readiness),
                    "P7_PS_CORE_READINESS_SHA256": digest(self.readiness),
                }
            )
        if stage_name is not None:
            authorization_fields["P7_JTAG_STAGE_NAME"] = stage_name
        if semantic_mode is not None:
            authorization_fields["P7_JTAG_SEMANTIC_MODE"] = semantic_mode
        auth = self.authorization_dir / f"P7_SYNTHETIC_{self.sequence:03d}.txt"
        auth.write_text(
            "P7_STATIONARY_APP_LAYER_APPROVED\n"
            + "\n".join(f"{key}={value}" for key, value in authorization_fields.items())
            + "\n",
            encoding="utf-8",
        )
        return {
            "P7_HARDWARE_SAFETY": "PASS",
            "ready_for_hardware_preflight": True,
            "hardware_actions_executed": False,
            "authorization_environment_present": True,
            "authorization": self._record(auth),
            "authorization_fields": authorization_fields,
            "source_commit_requested": self.commit,
            "source_commit_current": self.commit,
            "dirty_files": [],
            "max_runtime_sec": runtime,
            "lane_count": 2,
            "max_lane_mask": "0x3",
            "no_ethernet": True,
            "no_motion": True,
            "shutdown_on_exit": True,
            "abort_file_present": False,
            "artifacts": records,
            "errors": [],
            "warnings": [],
        }

    @staticmethod
    def _process(name: str, stdout: Path, stderr: Path, **extra: object) -> dict[str, object]:
        return {
            "name": name,
            "returncode": 0,
            "stdout_path": str(stdout),
            "stderr_path": str(stderr),
            "elapsed_seconds": 1.0,
            "timed_out": False,
            "abort_seen": False,
            "interrupted": False,
            "process_tree_terminated": False,
            "process_tree_reaped": True,
            "containment_kind": "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE",
            "containment_assigned": True,
            "containment_closed": True,
            "descendant_count_after": 0,
            "expected_tool_daemon_grace_used": False,
            "expected_tool_daemon_grace_seconds": 0.0,
            "expected_tool_daemon_paths": [],
            "descendant_paths_seen": [],
            "descendant_processes_seen": [],
            "expected_tool_daemon_classification": "NONE",
            "expected_tool_daemon_topology_snapshots": [
                {"classification": "EMPTY", "elapsed_seconds": 0.0, "processes": []}
            ],
            "expected_tool_daemon_topology_revalidation_count": 0,
            "expected_tool_daemon_topology_monotonic": False,
            "expected_tool_daemon_topology_sample_elapsed_seconds": [0.0],
            "expected_tool_daemon_topology_max_sample_gap_seconds": 0.0,
            "expected_tool_daemon_grace_elapsed_seconds": 0.0,
            "expected_tool_daemon_hashes_verified": False,
            "expected_tool_daemon_sha256_by_role": {},
            "expected_tool_daemon_hash_error": "",
            "expected_tool_daemon_prelaunch_hashes_verified": False,
            "expected_tool_daemon_prelaunch_sha256_by_role": {},
            "expected_tool_daemon_prelaunch_hash_error": "",
            "expected_tool_daemon_postexit_hashes_verified": False,
            "expected_tool_daemon_postexit_sha256_by_role": {},
            "expected_tool_daemon_postexit_hash_error": "",
            "expected_tool_daemon_topology_error": "",
            "expected_tool_daemon_topology_terminal_empty": True,
            "process_identity_query_retry_count": 0,
            "process_exit_race_recheck_count": 0,
            "containment_cleanup_attempted": False,
            "containment_cleanup_terminated": False,
            "process_exit_race_rechecked": False,
            "process_identity_query_retried": False,
            "containment_query_error": "",
            "launch_error": "",
            "argv": ["synthetic", name],
            "started_at_utc": "2026-07-10T00:00:00+00:00",
            "ended_at_utc": "2026-07-10T00:00:01+00:00",
            **extra,
        }

    def _run_files(self, run: Path, raw_name: str, raw_lines: list[str]) -> dict[str, Path]:
        run.mkdir(parents=True)
        files = {
            "preflight_stdout": run / "preflight.stdout.log",
            "preflight_stderr": run / "preflight.stderr.log",
            "stage_stdout": run / "stage.stdout.log",
            "stage_stderr": run / "stage.stderr.log",
            "before_stdout": run / "shutdown_before.stdout.log",
            "before_stderr": run / "shutdown_before.stderr.log",
            "after_stdout": run / "shutdown_after.stdout.log",
            "after_stderr": run / "shutdown_after.stderr.log",
            "raw": run / raw_name,
        }
        for key, path in files.items():
            if key == "raw":
                path.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
            elif "before_stdout" == key or "after_stdout" == key:
                path.write_text("Vivado shutdown transcript (not authoritative)\n", encoding="utf-8")
            else:
                path.write_text("\n", encoding="utf-8")
        for which in ("before", "after"):
            result = run / f"shutdown_{which}_result.txt"
            result.write_text(
                "P7_TCL_PROGRAMMING_ATTEMPTED=1\n"
                f"TFDU_SHUTDOWN_PROGRAMMED={self.artifacts['shutdown_bitstream'].resolve()}\n"
                "P7_SHUTDOWN_RESULT=PASS\n",
                encoding="utf-8",
            )
            files[f"{which}_result"] = result
        return files

    def _identity(self) -> dict[str, str]:
        return {
            "P7_HW_PREFLIGHT_RESULT": "PASS",
            "P7_HW_PREFLIGHT_READ_ONLY": "1",
            "P7_HW_PREFLIGHT_BOARD_ID": BOARD,
            "P7_HW_PREFLIGHT_PART": PART,
            "P7_HW_PREFLIGHT_DEVICE": subject.CANONICAL_LIVE_DEVICE,
            "P7_HW_PREFLIGHT_IDCODE": "00010011011100100010000010010011",
            "P7_HW_PREFLIGHT_CANONICAL_PART": PART,
            "P7_HW_PREFLIGHT_LIVE_PART": subject.CANONICAL_LIVE_PART,
            "P7_HW_PREFLIGHT_LIVE_DEVICE": subject.CANONICAL_LIVE_DEVICE,
            "P7_HW_PREFLIGHT_LIVE_IDCODE": "00010011011100100010000010010011",
            "P7_HW_PREFLIGHT_TARGET": TARGET,
        }

    def _shutdown(self, files: dict[str, Path], which: str, **timing: object) -> dict[str, object]:
        return self._process(
            f"shutdown_{which}",
            files[f"{which}_stdout"],
            files[f"{which}_stderr"],
            result_file=str(files[f"{which}_result"]),
            passed=True,
            attempted=True,
            programming_attempted=True,
            failures=[],
            **timing,
        )

    def _hardware_lock(self, run: Path, *, kind: str, stage_name: str, mode: str | None = None) -> dict[str, object]:
        owner: dict[str, object] = {
            "wrapper": "run_p7_ps_application_stage_safe.py" if kind == "ps" else "run_p7_jtag_axi_stage_safe.py",
            "stage_name": stage_name,
            "acquired_at_utc": "2026-07-10T00:00:00+00:00",
            "evidence_dir": str(run.resolve()),
        }
        if kind == "ps":
            owner["mode"] = mode
        return {
            "path": str((self.root / subject.HARDWARE_EXECUTION_LOCK_RELATIVE).resolve()),
            "token_sha256": "b" * 64,
            "owner": owner,
            "acquired": True,
            "stale_lock_auto_recovery": False,
        }

    def make_historical_read_only_preflight_epoch(
        self,
        source_commit: str,
        *,
        epoch_name: str = "historical_epoch",
        hour: int = 0,
        minute_offset: int = 0,
        identity_pass_containment_failure: bool = False,
    ) -> Path:
        self.sequence += 1
        epoch = self.hardware / "authorized_sequence" / epoch_name
        run = epoch / "001_p7_safe_idle"
        run.mkdir(parents=True)
        def at(minute: int, second: int = 0) -> str:
            total_minutes = hour * 60 + minute_offset + minute
            return f"2026-07-10T{total_minutes // 60:02d}:{total_minutes % 60:02d}:{second:02d}+00:00"
        preflight_stdout = run / "p7_preflight.stdout.log"
        preflight_stderr = run / "p7_preflight.stderr.log"
        preflight_result = run / "p7_preflight_result.txt"
        identity = self._identity()
        identity["P7_HW_PREFLIGHT_AUTHORIZED"] = "1"
        if identity_pass_containment_failure:
            preflight_markers = identity
        else:
            preflight_markers = {
                "P7_HW_PREFLIGHT_AUTHORIZED": "0",
                "P7_HW_PREFLIGHT_READ_ONLY": "1",
                "P7_HW_PREFLIGHT_RESULT": "FAIL",
                "P7_HW_PREFLIGHT_ERROR": "P7 expected exactly one authorized part match; found 0",
            }
        preflight_stdout.write_text(
            "INFO: [Labtools 27-2285] Connecting to hw_server url TCP:localhost:3121\n"
            "INFO: [Labtoolstcl 44-466] Opening hw_target localhost:3121/xilinx_tcf/Digilent/210512180081\n"
            + "".join(f"{key}={value}\n" for key, value in preflight_markers.items()),
            encoding="utf-8",
        )
        preflight_stderr.write_bytes(b"")
        preflight_result.write_text(
            "".join(f"{key}={value}\n" for key, value in preflight_markers.items()),
            encoding="utf-8",
        )
        transaction = self.root / "old_inputs" / epoch_name / "001_p7_safe_idle.transactions.txt"
        transaction.parent.mkdir(parents=True)
        transaction.write_text("P7_JTAG_AXI_TRANSACTIONS_V1\nEND\n", encoding="ascii")
        transaction_sha = digest(transaction)
        safety = self._safety(
            self.functional_profile,
            300,
            stage_name="p7_safe_idle",
            semantic_mode="safe-idle",
        )
        safety["source_commit_requested"] = source_commit
        safety["source_commit_current"] = source_commit
        safety["preflight_tcl_sha256"] = hashlib.sha256(
            subprocess.run(
                ["git", "show", f"{source_commit}:scripts/hw/p7_hw_preflight.tcl"],
                cwd=self.root,
                capture_output=True,
                check=True,
            ).stdout
        ).hexdigest()
        auth_fields = safety["authorization_fields"]
        assert isinstance(auth_fields, dict)
        auth_fields["SOURCE_COMMIT"] = source_commit
        auth_fields["P7_JTAG_TRANSACTION_PATH"] = str(transaction)
        auth_fields["P7_JTAG_TRANSACTION_SHA256"] = transaction_sha
        auth_path = Path(str(safety["authorization"]["path"]))
        auth_path.write_text(
            "P7_STATIONARY_APP_LAYER_APPROVED\n"
            + "\n".join(f"{key}={value}" for key, value in auth_fields.items())
            + "\n",
            encoding="utf-8",
        )
        safety["authorization"] = self._record(auth_path)
        events = [
            {"timestamp_utc": at(10), "event": "authorized_execution_begin", "stage": "p7_safe_idle"},
            {"timestamp_utc": at(11), "event": "preflight_finished", "returncode": 125, "passed": False},
            {"timestamp_utc": at(11, 1), "event": "authorized_execution_end", "status": "FAIL_PREFLIGHT"},
        ]
        (run / "p7_jtag_axi_stage_events.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in events),
            encoding="utf-8",
        )
        vivado = r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat"
        cs_server = r"D:\Xilinx\Vivado\2023.1\bin\unwrapped\win64.o\cs_server.exe"
        rdi_xsdb = r"D:\Xilinx\Vivado\2023.1\bin\unwrapped\win64.o\rdi_xsdb.exe"
        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        conhost = str(system_root / "System32/conhost.exe")
        cmd = str(system_root / "System32/cmd.exe")
        if identity_pass_containment_failure:
            preflight_argv = [
                vivado,
                "-mode",
                "batch",
                "-source",
                str((self.root / "scripts/hw/p7_hw_preflight.tcl").resolve()),
                "-tclargs",
                str(self.root.resolve()),
                str(auth_path),
                BOARD,
                PART,
                TARGET,
                "localhost:3121",
                str(preflight_result.resolve()),
            ]
            preflight_extra: dict[str, object] = {
                "process_tree_terminated": True,
                "containment_cleanup_terminated": True,
                "expected_tool_daemon_grace_used": False,
                "expected_tool_daemon_grace_seconds": 0.0,
                "expected_tool_daemon_paths": [cs_server],
                "descendant_paths_seen": [conhost, cs_server, cs_server, cmd, conhost, rdi_xsdb],
                "descendant_processes_seen": [
                    {"pid": 101, "parent_pid": 9001, "image_path": conhost},
                    {"pid": 201, "parent_pid": 9002, "image_path": cs_server},
                    {"pid": 202, "parent_pid": 201, "image_path": cs_server},
                    {"pid": 301, "parent_pid": 9003, "image_path": cmd},
                    {"pid": 302, "parent_pid": 301, "image_path": conhost},
                    {"pid": 303, "parent_pid": 301, "image_path": rdi_xsdb},
                ],
                "expected_tool_daemon_classification": "UNAPPROVED",
                "process_exit_race_rechecked": False,
                "process_identity_query_retried": False,
                "containment_query_error": "",
            }
        else:
            preflight_argv = ["synthetic-vivado", "read-only-preflight"]
            preflight_extra = {"process_tree_terminated": False}
        preflight_process = self._process(
            "preflight",
            preflight_stdout,
            preflight_stderr,
            returncode=125,
            passed=False,
            result_file=str(preflight_result),
            process_tree_reaped=False,
            argv=preflight_argv,
            started_at_utc=at(10, 1),
            ended_at_utc=at(10, 59),
            **preflight_extra,
        )
        summary: dict[str, object] = {
            subject.JTAG_MARKER: "FAIL_PREFLIGHT",
            "generated_at_utc": at(10),
            "stage_name": "p7_safe_idle",
            "semantic_mode": "safe-idle",
            "requested_execute_hardware": True,
            "hardware_actions_executed": True,
            "programmed_fpga": False,
            "programmed_candidate": False,
            "programmed_shutdown_before": False,
            "programmed_shutdown_after": False,
            "started_ps_elf": False,
            "drove_tfdu_txd": False,
            "enabled_tfdu_receiver": False,
            "uart_access": False,
            "ethernet_used": False,
            "motion_used": False,
            "hardware_acceptance": "PENDING_HW",
            "safety_validation": safety,
            "transaction_validation": {
                "path": str(transaction),
                "expected_sha256": transaction_sha,
                "actual_sha256": transaction_sha,
                "valid": True,
                "metadata": {"EVIDENCE_KIND": "safe_idle"},
            },
            "hardware_execution_lock": self._hardware_lock(run, kind="jtag", stage_name="p7_safe_idle"),
            "preflight_process": preflight_process,
            "target_identity": preflight_markers,
            "reason": (
                "read-only target preflight did not return rc=0 with exact identity markers"
                if identity_pass_containment_failure
                else "read-only target preflight failed part identity"
            ),
        }
        if identity_pass_containment_failure:
            summary.update(
                {
                    "preflight_result_file": str(preflight_result),
                    "preflight_failures": ["preflight process returned nonzero exit code: 125"],
                    "global_runtime": {
                        "elapsed_seconds": 59.0,
                        "authorized_max_seconds": 300,
                        "within_authorized_limit": True,
                    },
                }
            )
        summary_path = run / "p7_jtag_axi_stage_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

        canonical_files = {
            "profile": self.root / "config/profiles/G1_LANE0_BASELINE.json",
            "shutdown_tcl": self.root / "scripts/legacy_safe_tools/program_tfdu_shutdown.tcl",
            "shutdown_bit": self.root / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit",
            "pinmap": self.root / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv",
            "xdc": self.root / "constraints/active/PORT1.generated.xdc",
        }
        for name, path in canonical_files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"synthetic historical recovery {name}\n".encode())

        p4_auth = self.root / ".hardware_authorization/P4_APPROVED.txt"
        p4_auth.write_text(
            "I AUTHORIZE RF_COMM_MULTILANE P4 HARDWARE ACCEPTANCE ON CONNECTED HARDWARE.\n"
            "I UNDERSTAND THIS MAY DRIVE TFDU6102 TXD AFTER SAFE-IDLE CHECKS PASS.\n"
            "MAX_RUNTIME_SEC=300\nAUTHORIZED_BY=synthetic\nDATE=2026-07-10\n",
            encoding="utf-8",
        )
        p4_fields = {"MAX_RUNTIME_SEC": "300", "AUTHORIZED_BY": "synthetic", "DATE": "2026-07-10"}

        recovery_names = (
            [f"recovery_shutdown_after_failed_preflight_20260710T{hour:02d}12"]
            if identity_pass_containment_failure
            else [
                f"recovery_shutdown_after_failed_preflight_20260710T{hour:02d}12",
                f"recovery_shutdown_after_failed_preflight_20260710T{hour:02d}13",
            ]
        )

        def make_recovery(name: str, *, effective: bool) -> None:
            directory = epoch / name
            directory.mkdir(parents=True)
            authorization = {
                "AUTHORIZED": effective,
                "P4_AUTHORIZATION": "AUTHORIZED" if effective else "BLOCKED_NOT_AUTHORIZED",
                "AUTHORIZATION_FILE": ".hardware_authorization/P4_APPROVED.txt",
                "AUTHORIZATION_FILE_EXISTS": True,
                "AUTHORIZATION_FILE_SHA256": digest(p4_auth),
                "AUTHORIZATION_FIELDS": p4_fields,
                "RF_COMM_HW_AUTH_PRESENT": effective,
                "BOARD_ID": BOARD,
                "PROFILE": "config/profiles/G1_LANE0_BASELINE.json",
                "PROFILE_SHA256": digest(canonical_files["profile"]),
                "PROFILE_SHA256_EXPECTED": digest(canonical_files["profile"]),
                "BITSTREAM": "shutdown_bitstream/tfdu_shutdown_j10_j11.bit",
                "BITSTREAM_SHA256": digest(canonical_files["shutdown_bit"]),
                "BITSTREAM_SHA256_EXPECTED": digest(canonical_files["shutdown_bit"]),
                "ACTIVE_PINMAP_HASH": digest(canonical_files["pinmap"]),
                "ACTIVE_PINMAP_HASH_EXPECTED": digest(canonical_files["pinmap"]),
                "ACTIVE_XDC_HASH": digest(canonical_files["xdc"]),
                "ACTIVE_XDC_HASH_EXPECTED": digest(canonical_files["xdc"]),
                "ABORT_FILE": ".hardware_authorization/ABORT_NOW.txt",
                "ABORT_FILE_PRESENT": False,
                "missing": [] if effective else ["RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW"],
            }
            (directory / "hardware_authorization.json").write_text(json.dumps(authorization) + "\n", encoding="utf-8")
            manifest_files = [
                {
                    "path": str(path),
                    "exists": True,
                    "sha256": digest(path),
                }
                for path in canonical_files.values()
            ]
            (directory / "hash_manifest.json").write_text(json.dumps({"files": manifest_files}, indent=2) + "\n", encoding="utf-8")
            (directory / "hash_manifest.csv").write_text("path,exists,sha256\n", encoding="utf-8")
            if effective:
                (directory / "program_tfdu_shutdown_safe.stdout.log").write_text(
                    "HW_TARGET localhost:3121/xilinx_tcf/Digilent/210512180081\n"
                    "HW_JTAG_FREQUENCY_HZ 1000000\n"
                    "HW_DEVICE xc7z010_1\n"
                    f"TFDU_SHUTDOWN_PROGRAMMED {canonical_files['shutdown_bit'].as_posix()}\n",
                    encoding="utf-8",
                )
                (directory / "program_tfdu_shutdown_safe.stderr.log").write_bytes(b"")
            start = at(13) if effective and not identity_pass_containment_failure else at(12)
            end = at(14) if effective and not identity_pass_containment_failure else at(12, 1)
            lines = [
                f"PROGRAM_TFDU_SHUTDOWN_SAFE_BEGIN {start}",
                f"PROFILE_PATH={canonical_files['profile']}",
                f"PROFILE_SHA256={digest(canonical_files['profile'])}",
                f"HASH_MANIFEST_JSON={directory / 'hash_manifest.json'}",
                f"HASH_MANIFEST_CSV={directory / 'hash_manifest.csv'}",
                f"SHUTDOWN_TCL={canonical_files['shutdown_tcl']}",
                f"SHUTDOWN_TCL_SHA256={digest(canonical_files['shutdown_tcl'])}",
                f"SHUTDOWN_BITSTREAM={canonical_files['shutdown_bit']}",
                f"SHUTDOWN_BITSTREAM_SHA256={digest(canonical_files['shutdown_bit'])}",
                f"HARDWARE_AUTHORIZATION_LOG={directory / 'hardware_authorization.json'}",
            ]
            if effective:
                lines.extend(
                    [
                        "HARDWARE_AUTHORIZATION_EXIT=0",
                        "ALLOW_HARDWARE=1",
                        "NO_HARDWARE_ACTIONS_EXECUTED=0",
                        f"SHUTDOWN_STDOUT_LOG={directory / 'program_tfdu_shutdown_safe.stdout.log'}",
                        f"SHUTDOWN_STDERR_LOG={directory / 'program_tfdu_shutdown_safe.stderr.log'}",
                        "SHUTDOWN_RAW_EXIT=125",
                        "TFDU_SHUTDOWN_PROGRAMMED_SEEN=1",
                        "SHUTDOWN_EXIT=0",
                        "PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS",
                    ]
                )
            else:
                lines.extend(
                    [
                        "HARDWARE_AUTHORIZATION_EXIT=2",
                        "AUTHORIZATION_MISSING=1",
                        "NO_HARDWARE_ACTIONS_EXECUTED=1",
                        "PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=AUTHORIZATION_MISSING",
                    ]
                )
            lines.append(f"PROGRAM_TFDU_SHUTDOWN_SAFE_END {end}")
            (directory / "program_tfdu_shutdown_safe.summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

        if identity_pass_containment_failure:
            make_recovery(recovery_names[0], effective=True)
        else:
            make_recovery(recovery_names[0], effective=False)
            make_recovery(recovery_names[1], effective=True)

        tree_listing = subprocess.run(
            ["git", "ls-tree", "-r", "--full-tree", source_commit],
            cwd=self.root,
            text=True,
            capture_output=True,
            check=True,
        ).stdout
        checkpoint_hashes: dict[str, str] = {}
        for relative in subject.HISTORICAL_GIT_CRITICAL_SOURCES:
            blob = subprocess.run(
                ["git", "show", f"{source_commit}:{relative}"],
                cwd=self.root,
                capture_output=True,
                check=True,
            ).stdout
            checkpoint_hashes[relative] = hashlib.sha256(blob).hexdigest()
        old_offline = self.root / "old_inputs" / epoch_name / "p7_offline_gate_summary.json"
        old_offline.parent.mkdir(parents=True, exist_ok=True)
        old_offline.write_text(
            json.dumps(
                {
                    "P7_OFFLINE_GATE": "PASS",
                    "source_commit": source_commit,
                    "hardware_actions_executed": False,
                    "NO_HARDWARE_ACTIONS_EXECUTED": True,
                    "source_tree_listing_sha256": hashlib.sha256(tree_listing.encode("utf-8")).hexdigest(),
                    "checkpoint_input_hashes": checkpoint_hashes,
                    "checkpoint_input_count": len(checkpoint_hashes),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        command = [
            "synthetic-sequence",
            "--source-commit", source_commit,
            "--authorization-file", str(auth_path),
            "--authorization-sha256", digest(auth_path),
            "--transaction-file", str(transaction),
            "--transaction-sha256", transaction_sha,
            "--evidence-dir", str(run),
        ]
        old_plan = self.root / "old_inputs" / epoch_name / "p7_sequence_plan.txt"
        old_stages = [
            {
                "id": "p7_safe_idle",
                "group": "safe_idle",
                "risk_index": 10,
                "case": {},
                "command": command,
                "summary_path": str(summary_path),
            }
        ] + [
            {
                "id": f"stage_{index}",
                "group": "synthetic",
                "risk_index": 20 + index,
                "case": {},
                "command": ["synthetic", str(index)],
                "summary_path": str(self.hardware / f"unused_{index}.json"),
            }
            for index in range(1, 66)
        ]
        old_plan.write_text(
            json.dumps(
                {
                    "schema": "rf-comm-p7-hardware-sequence-plan-v1",
                    "source_commit": source_commit,
                    "offline_checkpoint": {"path": str(old_offline), "sha256": digest(old_offline)},
                    "stages": old_stages,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        generation = self.root / "build/p7_authorized_sequence" / epoch_name / "p7_authorized_sequence_generation_manifest.json"
        generation.parent.mkdir(parents=True, exist_ok=True)
        generation.write_text(
            json.dumps(
                {
                    "schema": "rf-comm-p7-authorized-sequence-generator-v1",
                    "source_commit": source_commit,
                    "offline_checkpoint": {"path": str(old_offline), "sha256": digest(old_offline)},
                    "sequence_plan": {"path": str(old_plan), "sha256": digest(old_plan), "stage_count": 66},
                    "authorization_records": [
                        {"stage": "p7_safe_idle", "path": str(auth_path), "sha256": digest(auth_path)}
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        frozen_dir = epoch / "historical_preflight_inputs"
        frozen_dir.mkdir()
        originals = {
            "offline_checkpoint": old_offline,
            "sequence_plan": old_plan,
            "stage_authorization": auth_path,
            "stage_transactions": transaction,
            "generation_manifest": generation,
            "recovery_p4_authorization": p4_auth,
        }
        frozen_items = []
        for role, original in originals.items():
            frozen = frozen_dir / f"{role}{original.suffix}"
            frozen.write_bytes(original.read_bytes())
            frozen_items.append(
                {
                    "role": role,
                    "original_path": str(original.relative_to(self.root)),
                    "frozen_path": str(frozen.relative_to(self.root)),
                    "bytes": frozen.stat().st_size,
                    "sha256": digest(frozen),
                }
            )
        (frozen_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "schema": "rf-comm-p7-historical-preflight-inputs-v1",
                    "run_id": epoch_name,
                    "source_commit": source_commit,
                    "stage_index": 0,
                    "stage_id": "p7_safe_idle",
                    "result": "FAIL_PREFLIGHT",
                    "mutation_attempted": False,
                    "coverage_claimed": False,
                    "recovery_directories": recovery_names,
                    "files": frozen_items,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        outer_logs = epoch / ".sequence_execution_ledger_wrapper_logs"
        outer_logs.mkdir()
        outer_stdout = outer_logs / "001_p7_safe_idle.stdout.log"
        outer_stderr = outer_logs / "001_p7_safe_idle.stderr.log"
        outer_stdout.write_text("synthetic outer failure\n", encoding="utf-8")
        outer_stderr.write_bytes(b"")
        outer = {
            "schema": "rf-comm-p7-sequence-execution-ledger-v1",
            "created_at_utc": at(9),
            "updated_at_utc": at(11, 2),
            "status": "FAIL",
            "hardware_actions_executed": True,
            "network_used": False,
            "motion_used": False,
            "source_commit": source_commit,
            "sequence_plan": {"path": str(old_plan), "sha256": digest(old_plan), "stage_count": 66},
            "offline_checkpoint": {"path": str(old_offline), "sha256": digest(old_offline), "result": "PASS", "source_commit": source_commit},
            "attempt_count": 1,
            "completed_stage_count": 0,
            "next_stage_index": 0,
            "failed_stage_index": 0,
            "attempts": [
                {
                    "attempt": 1,
                    "stage_index": 0,
                    "stage_id": "p7_safe_idle",
                    "group": "safe_idle",
                    "risk_index": 10,
                    "case": {},
                    "command": command,
                    "state": "TERMINAL",
                    "result": "FAIL",
                    "started_at_utc": at(9, 59),
                    "ended_at_utc": at(11, 2),
                    **({"launch_intent_at_utc": at(9, 58)} if identity_pass_containment_failure else {}),
                    "process": {
                        **(
                            {
                                "name": "sequence_p7_safe_idle",
                                "stdout_path": str(outer_stdout),
                                "stderr_path": str(outer_stderr),
                                "elapsed_seconds": 63.0,
                            }
                            if identity_pass_containment_failure
                            else {}
                        ),
                        "returncode": 1,
                        "argv": command,
                        "started_at_utc": at(9, 59),
                        "ended_at_utc": at(11, 2),
                        "timed_out": False,
                        "abort_seen": False,
                        "interrupted": False,
                        "process_tree_terminated": False,
                        "process_tree_reaped": True,
                        "containment_kind": "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE",
                        "containment_assigned": True,
                        "containment_closed": True,
                        "descendant_count_after": 0,
                        "launch_error": "",
                        **(
                            {
                                "expected_tool_daemon_grace_used": False,
                                "expected_tool_daemon_grace_seconds": 0.0,
                                "expected_tool_daemon_paths": [],
                                "descendant_paths_seen": [],
                                "descendant_processes_seen": [],
                                "expected_tool_daemon_classification": "NONE",
                                "containment_cleanup_terminated": False,
                                "process_exit_race_rechecked": False,
                                "process_identity_query_retried": False,
                                "containment_query_error": "",
                            }
                            if identity_pass_containment_failure
                            else {}
                        ),
                        "stdout_file": {"path": str(outer_stdout), "sha256": digest(outer_stdout), "bytes": outer_stdout.stat().st_size},
                        "stderr_file": {"path": str(outer_stderr), "sha256": digest(outer_stderr), "bytes": outer_stderr.stat().st_size},
                    },
                    "summary_file": {"path": str(summary_path), "sha256": digest(summary_path), "bytes": summary_path.stat().st_size},
                    "shutdown_after": {"present": False},
                    "failures": (
                        [
                            "outer wrapper process containment/return-code policy failed",
                            "wrapper result is not PASS: P7_JTAG_AXI_SAFE_STAGE=FAIL_PREFLIGHT",
                            "wrapper summary does not prove programmed_shutdown_after=true",
                            "wrapper shutdown-after record is missing",
                            "wrapper candidate process record is missing: stage_process",
                            "JTAG wrapper strict backend parse is missing or not bound to this run",
                        ]
                        if identity_pass_containment_failure
                        else ["read-only preflight failed"]
                    ),
                    **({"orchestrator_elapsed_seconds": 64.0} if identity_pass_containment_failure else {}),
                }
            ],
        }
        (epoch / "sequence_execution_ledger.json").write_text(json.dumps(outer, indent=2) + "\n", encoding="utf-8")
        return summary_path

    def make_jtag(
        self,
        stage_name: str,
        semantic: list[str],
        *,
        backend: tuple[int, str, str] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> tuple[Path, dict[str, object]]:
        self.sequence += 1
        stage_hour = 2 + self.sequence // 60
        stage_minute = self.sequence % 60
        run = self.hardware / "jtag_axi" / stage_name / f"run_{self.sequence:03d}"
        semantic_mode = "safe-idle" if "safe_idle" in stage_name else "rfap"
        safe_idle_lines = []
        if semantic_mode == "safe-idle":
            safe_idle_lines = [
                "P7_TXN_META_EVIDENCE_KIND=safe_idle",
                "P7_TRANSACTION_COUNT=13",
                *(f"{key}=0x00000000" for key in sorted(subject.SAFE_IDLE_REQUIRED_KEYS)),
            ]
        raw_lines = [
            "P7_JTAG_STAGE_RESULT=PASS",
            "P7_JTAG_AXI_TRANSACTIONS=PASS",
            "P7_CANDIDATE_PROGRAMMED=1",
            f"P7_HW_TARGET={TARGET}",
            f"P7_HW_PART={PART}",
            f"P7_HW_DEVICE={subject.CANONICAL_LIVE_DEVICE}",
            "P7_HW_IDCODE=00010011011100100010000010010011",
            f"P7_HW_CANONICAL_PART={PART}",
            f"P7_HW_LIVE_PART={subject.CANONICAL_LIVE_PART}",
            f"P7_HW_LIVE_DEVICE={subject.CANONICAL_LIVE_DEVICE}",
            "P7_HW_LIVE_IDCODE=00010011011100100010000010010011",
            *safe_idle_lines,
            *semantic,
        ]
        files = self._run_files(run, "p7_jtag_axi_raw_result.txt", raw_lines)
        preflight_result = run / "p7_preflight_result.txt"
        preflight_result.write_text(
            "\n".join(f"{key}={value}" for key, value in self._identity().items()) + "\n",
            encoding="utf-8",
        )
        event_prefix = f"2026-07-10T{stage_hour:02d}:{stage_minute:02d}"
        event_rows = [
            {"timestamp_utc": f"{event_prefix}:00+00:00", "event": "authorized_execution_begin"},
            {"timestamp_utc": f"{event_prefix}:02+00:00", "event": "candidate_started"},
            {"timestamp_utc": f"{event_prefix}:04+00:00", "event": "candidate_child_reaped", "process_tree_reaped": True, "candidate_returncode": 0},
            {"timestamp_utc": f"{event_prefix}:05+00:00", "event": "shutdown_after_started", "candidate_child_reaped": True, "candidate_returncode": 0},
            {"timestamp_utc": f"{event_prefix}:07+00:00", "event": "authorized_execution_end", "status": "PASS"},
        ]
        (run / "p7_jtag_axi_stage_events.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in event_rows), encoding="utf-8"
        )
        # JTAG runner uses p7_-prefixed shutdown result names.
        for which in ("before", "after"):
            prefixed = run / f"p7_shutdown_{which}_result.txt"
            files[f"{which}_result"].replace(prefixed)
            files[f"{which}_result"] = prefixed
        transaction = run / "transaction.txt"
        transaction.write_text("P7_JTAG_AXI_TRANSACTIONS_V1\nEND\n", encoding="ascii")
        tx_hash = digest(transaction)
        stage_markers = {}
        for line in raw_lines:
            if "=" in line:
                key, value = line.split("=", 1)
                stage_markers[key] = value
        safety = self._safety(
            self.functional_profile,
            900,
            stage_name=stage_name,
            semantic_mode=semantic_mode,
        )
        summary: dict[str, object] = {
            subject.JTAG_MARKER: "PASS",
            "generated_at_utc": f"{event_prefix}:06+00:00",
            "stage_name": stage_name,
            "requested_execute_hardware": True,
            "hardware_actions_executed": True,
            "programmed_candidate": True,
            "programmed_shutdown_before": True,
            "programmed_shutdown_after": True,
            "child_reaped_before_shutdown_after": True,
            "started_ps_elf": False,
            "semantic_mode": semantic_mode,
            "drove_tfdu_txd": semantic_mode != "safe-idle",
            "enabled_tfdu_receiver": semantic_mode != "safe-idle",
            "uart_access": False,
            "ethernet_used": False,
            "motion_used": False,
            "hardware_execution_lock": self._hardware_lock(run, kind="jtag", stage_name=stage_name),
            "safety_validation": safety,
            "transaction_validation": {
                "path": str(transaction),
                "expected_sha256": tx_hash,
                "actual_sha256": tx_hash,
                "valid": True,
                "metadata": {"EVIDENCE_KIND": "safe_idle"} if semantic_mode == "safe-idle" else (metadata or {}),
                "start_operation_count": 0 if semantic_mode == "safe-idle" else 1,
                "commit_operation_count": 0 if semantic_mode == "safe-idle" else 1,
                "payload_write_count": 0 if semantic_mode == "safe-idle" else 1,
                "write_operations": [{"offset": "0x100", "value": "0x00000030"}] if semantic_mode == "safe-idle" else [],
                "result_keys": sorted(subject.SAFE_IDLE_REQUIRED_KEYS) if semantic_mode == "safe-idle" else [],
            },
            "preflight_process": self._process(
                "preflight", files["preflight_stdout"], files["preflight_stderr"],
                result_file=str(preflight_result), passed=True, failures=[],
                started_at_utc=f"{event_prefix}:00+00:00", ended_at_utc=f"{event_prefix}:01+00:00",
            ),
            "target_identity": self._identity(),
            "stage_process": self._process(
                "jtag_axi_stage",
                files["stage_stdout"],
                files["stage_stderr"],
                result_file=str(files["raw"]),
                passed=True,
                failures=[],
                argv=["synthetic-jtag", stage_name],
                started_at_utc=f"{event_prefix}:02+00:00",
                ended_at_utc=f"{event_prefix}:03+00:00",
            ),
            "stage_result_markers": stage_markers,
            "shutdown_before": self._shutdown(files, "before", started_at_utc=f"{event_prefix}:01+00:00", ended_at_utc=f"{event_prefix}:02+00:00"),
            "shutdown_after": self._shutdown(files, "after", started_at_utc=f"{event_prefix}:05+00:00", ended_at_utc=f"{event_prefix}:06+00:00"),
        }
        summary_path = run / "p7_jtag_axi_stage_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        if semantic_mode == "safe-idle":
            parsed = {
                "P7_SAFE_IDLE_PARSE": "PASS",
                "semantic_mode": "safe-idle",
                "expected_operation_count": 13,
                "observed_operation_count": 13,
                "required_values": {key: "0x00000000" for key in sorted(subject.SAFE_IDLE_REQUIRED_KEYS)},
                "forbidden_status_mask": "0x000000e8",
                "drove_tfdu_txd": False,
                "enabled_tfdu_receiver": False,
                "failures": [],
            }
            parse_path = run / "p7_safe_idle_parse_summary.json"
            parse_path.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")
            summary["backend_parse"] = {
                "passed": True,
                "semantic_mode": "safe-idle",
                "summary_file": str(parse_path),
                "summary_sha256": digest(parse_path),
                "required_values": parsed["required_values"],
                "raw_log_bound_to_this_hardware_process": True,
            }
            summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        if backend is not None:
            length, policy, pattern = backend
            fragment_count = max(1, (length + 214) // 215)
            fragments = [
                {"fragment_index": index, "latency_upper_bound_us": 100, "txd_high_max_cycles": 8}
                for index in range(fragment_count)
            ]
            latency_summary = {
                "sample_count": fragment_count,
                "min": 100,
                "mean": 100.0,
                "p50": 100,
                "p95": 100,
                "p99": 100,
                "max": 100,
                "percentile_method": "nearest_rank",
                "semantics": "upper_bound",
                "source": "bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period",
            }
            object_upper = fragment_count * 100
            poll_goodput = (length * 8_000_000) // object_upper
            output = run / "output.bin"
            unit = bytes(((index * 17 + self.sequence) & 0xFF for index in range(256)))
            output.write_bytes((unit * (length // 256 + 1))[:length])
            manifest = {
                "schema": subject.JTAG_MANIFEST_SCHEMA,
                "kind": "P7_JTAG_AXI_DRY_RUN_MANIFEST",
                "network_used": False,
                "allowed_lane_masks": [1, 2, 3],
                "input_length": length,
                "input_crc32": zlib.crc32(output.read_bytes()) & 0xFFFFFFFF,
                "input_sha256": digest(output),
                "lane_policy": policy,
                "payload_pattern": pattern,
                "transaction_file": transaction.name,
                "transaction_sha256": tx_hash,
            }
            manifest_path = run / "bundle_manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            parsed = {
                subject.BACKEND_PARSE_MARKER: "PASS",
                "manifest": str(manifest_path),
                "raw_log": str(files["raw"]),
                "output_file": str(output),
                "object_length": length,
                "object_crc32": zlib.crc32(output.read_bytes()) & 0xFFFFFFFF,
                "object_sha256": digest(output),
                "lane_policy": policy,
                "fragment_count": fragment_count,
                "fragments": fragments,
                "fragment_latency_upper_bound_us": latency_summary,
                "object_transport_latency_upper_bound_us": object_upper,
                "object_transport_latency_semantics": "sum_of_sequential_fragment_poll_upper_bounds",
                "poll_bound_application_goodput_lower_bound_bps": poll_goodput,
                "poll_bound_goodput_semantics": "lower_bound_from_object_bytes_over_transport_latency_upper_bound",
                "missing_fragments": 0,
                "duplicate_fragments": 0,
                "error_counter_increments": 0,
            }
            parse_path = run / "p7_jtag_backend_parse_summary.json"
            parse_path.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")
            summary["backend_parse"] = {
                "passed": True,
                "semantic_mode": "rfap",
                "summary_file": str(parse_path),
                "summary_sha256": digest(parse_path),
                "output_file": str(output),
                "output_sha256": digest(output),
                "object_length": length,
                "lane_policy": policy,
                "fragment_count": fragment_count,
                "fragment_latency_upper_bound_us": latency_summary,
                "object_transport_latency_upper_bound_us": object_upper,
                "object_transport_latency_semantics": "sum_of_sequential_fragment_poll_upper_bounds",
                "poll_bound_application_goodput_lower_bound_bps": poll_goodput,
                "poll_bound_goodput_semantics": "lower_bound_from_object_bytes_over_transport_latency_upper_bound",
                "host_end_to_end_elapsed_seconds": 1.0,
                "host_end_to_end_goodput_bps": round(length * 8.0, 6),
                "host_end_to_end_time_source": "host_monotonic_child_process_elapsed",
                "host_end_to_end_semantics": "includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency",
                "raw_log_bound_to_this_hardware_process": True,
            }
            summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary_path, summary

    @staticmethod
    def descriptor(
        length: int,
        policy: int,
        *,
        status: int = 3,
        error: int = 0,
        fallback: int = 0,
        unavailable: int = 0,
        unavailable_after: int | None = None,
    ) -> dict[str, object]:
        payload = (bytes(range(256)) * (length // 256 + 1))[:length]
        sha = hashlib.sha256(payload).hexdigest()
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        fragments = max(1, (length + 214) // 215)
        unavailable_after = (2 if unavailable else 0) if unavailable_after is None else unavailable_after
        lane_distribution = subject.expected_lane_distribution(policy, fragments, unavailable, unavailable_after)
        lane0, lane1, replicated = lane_distribution or (0, 0, 0)
        return {
            "magic": 0x53443750,
            "version": 1,
            "command": 1,
            "status": status,
            "error_code": error,
            "session_epoch": 0x50370001,
            "object_id": 1,
            "object_length": length,
            "bytes_completed": length if status == 3 else 0,
            "expected_sha256": sha,
            "input_sha256": sha,
            "output_sha256": sha if status == 3 else "0" * 64,
            "expected_crc32": crc,
            "output_crc32": crc if status == 3 else 0,
            "lane_policy": policy,
            "unavailable_lane_mask": unavailable,
            "unavailable_after_fragment": unavailable_after,
            "fragments_total": fragments,
            "fragments_completed": fragments if status == 3 else 0,
            "fragment_attempts": fragments if status == 3 else 0,
            "fallback_count": fallback,
            "lane0_fragments": lane0 if status == 3 else 0,
            "lane1_fragments": lane1 if status == 3 else 0,
            "replicated_fragments": replicated if status == 3 else 0,
            "p6_retry_count": 0,
            "p6_retry_exhausted": 0,
            "p6_tx_fail": 0,
            "p6_crc_bad": 0,
            "p6_payload_mismatch": 0,
            "max_txd_high_cycles": 8,
            "duty_violation_count": 0,
            "start_ticks": 1,
            "end_ticks": 2,
            "completion_sequence": 1,
        }

    @classmethod
    def case(cls, name: str, length: int, policy: int, **kwargs: int) -> dict[str, object]:
        descriptor = cls.descriptor(length, policy, **kwargs)
        return {
            "name": name,
            "slot": 0,
            "passed": True,
            "failures": [],
            "descriptor": descriptor,
            "output_bytes": length,
            "output_sha256": descriptor["output_sha256"],
        }

    def make_ps(self, mode: str, postprocess: dict[str, object], extra_raw: list[str] | None = None) -> tuple[Path, dict[str, object]]:
        self.sequence += 1
        stage_hour = 2 + self.sequence // 60
        stage_minute = self.sequence % 60
        run = self.hardware / "ps_application" / mode / f"run_{self.sequence:03d}"
        raw_lines = [
            "P7_PS_STAGE_RESULT=PASS",
            f"P7_PS_MODE={mode}",
            "P7_PS_CANDIDATE_PROGRAMMED=1",
            "P7_PS_ELF_DOWNLOADED=1",
            f"P7_HW_TARGET={TARGET}",
            f"P7_HW_PART={PART}",
            f"P7_HW_CANONICAL_PART={PART}",
            f"P7_HW_LIVE_PART={subject.CANONICAL_LIVE_PART}",
            f"P7_HW_LIVE_DEVICE={subject.CANONICAL_LIVE_DEVICE}",
            "P7_HW_LIVE_IDCODE=00010011011100100010000010010011",
            f"P7_XSDB_LIVE_DEVICE={subject.CANONICAL_LIVE_PART}",
            "P7_XSDB_LIVE_IDCODE=0x13722093",
            "P7_XSDB_PREFLIGHT_IDCODE=00010011011100100010000010010011",
            *(extra_raw or []),
        ]
        files = self._run_files(run, "p7_ps_application_raw_result.log", raw_lines)
        preflight_result = run / "p7_hw_preflight_result.txt"
        preflight_result.write_text(
            "\n".join(f"{key}={value}" for key, value in self._identity().items()) + "\n",
            encoding="utf-8",
        )
        bundle = run / "bundle"
        bundle.mkdir()
        plan = bundle / "execution_plan.txt"
        mailbox_image = bundle / "mailbox.bin"
        descriptors_image = bundle / "descriptors.bin"
        input_source = bundle / "input_source.bin"
        plan.write_text("P7_PS_APPLICATION_EXECUTION_PLAN_V1\nEND\n", encoding="ascii")
        mailbox_image.write_bytes(bytes(256))
        descriptors_image.write_bytes(bytes(8 * 256))
        input_source.write_bytes(b"synthetic-input")
        def file_record(path: Path) -> dict[str, object]:
            return {"path": str(path), "size_bytes": path.stat().st_size, "sha256": digest(path)}
        bundle_case_records: list[dict[str, object]] = []
        if mode == "stationary":
            for case in postprocess.get("cases", []):
                if not isinstance(case, dict) or not isinstance(case.get("descriptor"), dict):
                    continue
                slot = int(case["slot"])
                descriptor = case["descriptor"]
                object_length = int(descriptor["object_length"])
                payload = (bytes(range(256)) * (object_length // 256 + 1))[:object_length]
                input_path = bundle / f"input_{slot}.bin"
                input_path.write_bytes(payload)
                contract = subject.STATIONARY_SLOT_CONTRACT[slot]
                bundle_case_records.append(
                    {
                        "slot": slot,
                        "name": case["name"],
                        "pattern": contract[1],
                        "object_length": object_length,
                        "lane_policy": descriptor["lane_policy"],
                        "unavailable_lane_mask": descriptor["unavailable_lane_mask"],
                        "unavailable_after_fragment": descriptor["unavailable_after_fragment"],
                        "input": file_record(input_path),
                    }
                )
        if mode == "stationary":
            objects = [item for item in postprocess.get("stationary_objects", []) if isinstance(item, dict)]
            cases_by_slot = {
                int(item.get("slot", -1)): item.get("descriptor", {})
                for item in postprocess.get("cases", [])
                if isinstance(item, dict) and isinstance(item.get("descriptor"), dict)
            }
            trace_summary = postprocess.get("stationary_trace_validation")
            if isinstance(trace_summary, dict):
                trace_records = []
                fragment_timing_records = []
                fallback_lane0_to_lane1 = 0
                fallback_lane1_to_lane0 = 0
                for item in objects:
                    sequence = int(item["sequence"])
                    descriptor_path = bundle / f"stationary_{sequence:08d}_descriptor_result.bin"
                    output_path = bundle / f"stationary_{sequence:08d}_output_result.bin"
                    trace_path = bundle / f"stationary_{sequence:08d}_trace_result.bin"
                    descriptor = cases_by_slot[int(item["slot"])]
                    object_length = int(item["bytes_completed"])
                    output_payload = (bytes(range(256)) * (object_length // 256 + 1))[:object_length]
                    output_path.write_bytes(output_payload)
                    fragment_count = int(item["fragments_completed"])
                    policy = int(descriptor["lane_policy"])
                    unavailable = int(descriptor.get("unavailable_lane_mask", 0))
                    unavailable_after = int(descriptor.get("unavailable_after_fragment", 0))
                    trace_payload = bytearray()
                    directions: set[str] = set()
                    redirected_fragments = 0
                    for fragment_index in range(fragment_count):
                        if policy == 1:
                            lane_mask = 1
                        elif policy == 2:
                            lane_mask = 2
                        elif policy == 4:
                            lane_mask = 3
                        else:
                            lane_mask = 1 if fragment_index % 2 == 0 else 2
                            if fragment_index >= unavailable_after and lane_mask & unavailable:
                                if lane_mask == 1:
                                    lane_mask = 2
                                    directions.add("lane0_to_lane1")
                                else:
                                    lane_mask = 1
                                    directions.add("lane1_to_lane0")
                                redirected_fragments += 1
                        start_ticks = int(item["start_ticks"]) + 1 + 2 * fragment_index
                        end_ticks = start_ticks + 1
                        trace_payload.extend(
                            struct.pack(
                                "<16I",
                                subject.P7_TRACE_MAGIC,
                                int(item["session_epoch"]),
                                int(item["object_id"]),
                                (fragment_count << 16) | fragment_index,
                                lane_mask,
                                1,
                                1,
                                0,
                                start_ticks & 0xFFFFFFFF,
                                (start_ticks >> 32) & 0xFFFFFFFF,
                                end_ticks & 0xFFFFFFFF,
                                (end_ticks >> 32) & 0xFFFFFFFF,
                                0,
                                0,
                                0,
                                0,
                            )
                        )
                        fragment_timing_records.append(
                            {
                                "sequence": sequence,
                                "fragment_index": fragment_index,
                                "start_ticks": start_ticks,
                                "end_ticks": end_ticks,
                                "latency_ticks": 1,
                            }
                        )
                    trace_path.write_bytes(trace_payload)
                    sha_words = struct.unpack(">8I", bytes.fromhex(str(descriptor["expected_sha256"])))
                    descriptor_words = [0] * 64
                    descriptor_words[0:24] = [
                        0x53443750,
                        1,
                        1,
                        3,
                        int(item["session_epoch"]),
                        int(item["object_id"]),
                        0x01000000,
                        0x02000000,
                        object_length,
                        int(descriptor["expected_crc32"]),
                        policy,
                        8,
                        unavailable,
                        unavailable_after,
                        0,
                        0x03000000,
                        fragment_count,
                        0,
                        object_length,
                        fragment_count,
                        fragment_count,
                        int(descriptor["expected_crc32"]),
                        fragment_count,
                        len(directions),
                    ]
                    descriptor_words[24:32] = sha_words
                    descriptor_words[32:40] = sha_words
                    descriptor_words[40:48] = sha_words
                    descriptor_words[48:58] = [
                        int(item["p6_retry_count"]),
                        int(item["p6_retry_exhausted"]),
                        int(item["p6_tx_fail"]),
                        int(item["p6_crc_bad"]),
                        int(item["p6_payload_mismatch"]),
                        int(item["max_txd_high_cycles"]),
                        int(item["duty_violations"]),
                        int(item["lane0_fragments"]),
                        int(item["lane1_fragments"]),
                        int(item["replicated_fragments"]),
                    ]
                    start_ticks = int(item["start_ticks"])
                    end_ticks = int(item["end_ticks"])
                    descriptor_words[58:64] = [
                        start_ticks & 0xFFFFFFFF,
                        (start_ticks >> 32) & 0xFFFFFFFF,
                        end_ticks & 0xFFFFFFFF,
                        (end_ticks >> 32) & 0xFFFFFFFF,
                        0,
                        sequence,
                    ]
                    descriptor_path.write_bytes(struct.pack("<64I", *descriptor_words))
                    fallback_lane0_to_lane1 += int("lane0_to_lane1" in directions)
                    fallback_lane1_to_lane0 += int("lane1_to_lane0" in directions)
                    trace_records.append(
                        {
                            "sequence": sequence,
                            "slot": item["slot"],
                            "session_epoch": item["session_epoch"],
                            "object_id": item["object_id"],
                            "fragment_count": fragment_count,
                            "fragment_attempts": item["fragment_attempts"],
                            "fallback_count": len(directions),
                            "redirected_fragments": redirected_fragments,
                            "passed": True,
                            "failures": [],
                            "descriptor_file": file_record(descriptor_path),
                            "output_file": file_record(output_path),
                            "trace_file": file_record(trace_path),
                        }
                    )
                    with files["raw"].open("a", encoding="utf-8") as handle:
                        handle.write(f"P7_STATIONARY_TERMINAL_BUNDLE_{sequence:08d}_CAPTURED=1\n")
                trace_summary["records"] = trace_records
                trace_summary["fragment_timing_records"] = fragment_timing_records
                trace_summary["fragment_trace_entries"] = len(fragment_timing_records)
                trace_summary["fragment_latency_samples"] = len(fragment_timing_records)
                trace_summary["fallback_lane0_to_lane1"] = fallback_lane0_to_lane1
                trace_summary["fallback_lane1_to_lane0"] = fallback_lane1_to_lane0
        bundle_manifest = {
            "schema": "rf-comm-p7-ps-hardware-bundle-v1",
            "mode": mode,
            "hardware_actions_executed": False,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
            "input_source": file_record(input_source),
            "mailbox": file_record(mailbox_image),
            "descriptors": file_record(descriptors_image),
            "execution_plan": file_record(plan),
            "case_count": len(bundle_case_records),
            "cases": bundle_case_records,
            "atomic_files": True,
        }
        bundle_manifest_path = bundle / "bundle_manifest.json"
        bundle_manifest_path.write_text(json.dumps(bundle_manifest, indent=2) + "\n", encoding="utf-8")
        event_prefix = f"2026-07-10T{stage_hour:02d}:{stage_minute:02d}"
        events = {
            "events": [
                {"timestamp_utc": f"{event_prefix}:00+00:00", "event": "authorized_execution_begin"},
                {"timestamp_utc": f"{event_prefix}:02+00:00", "event": "candidate_started"},
                {"timestamp_utc": f"{event_prefix}:04+00:00", "event": "candidate_child_reaped", "process_tree_reaped": True, "candidate_returncode": 0},
                {"timestamp_utc": f"{event_prefix}:05+00:00", "event": "shutdown_after_started", "candidate_child_reaped": True, "candidate_returncode": 0},
                {"timestamp_utc": f"{event_prefix}:07+00:00", "event": "authorized_execution_end", "status": "PASS"},
            ]
        }
        (run / "p7_ps_application_events.json").write_text(json.dumps(events) + "\n", encoding="utf-8")
        raw_manifest_path = run / "p7_raw_evidence_sha256_manifest.json"
        raw_records = []
        for path in sorted(item for item in run.rglob("*") if item.is_file() and item != raw_manifest_path):
            raw_records.append(
                {
                    "path": path.relative_to(run).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": digest(path),
                    "committed": True,
                }
            )
        raw_manifest_path.write_text(
            json.dumps(
                {
                    "schema": "rf-comm-p7-raw-evidence-sha256-v1",
                    "hardware_acceptance": "PENDING_HW",
                    "record_count": len(raw_records),
                    "partial_file_count": 0,
                    "partial_files": [],
                    "records": raw_records,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        runtime = 1800 if mode == "stationary" else 900
        profile = self.stationary_profile if mode == "stationary" else self.functional_profile
        readiness_record = self._record(self.readiness)
        readiness_record["status"] = "PASS"
        safety = self._safety(profile, runtime, mode=mode)
        summary: dict[str, object] = {
            subject.PS_MARKER: "PASS",
            "generated_at_utc": f"{event_prefix}:06+00:00",
            "mode": mode,
            "stage_name": f"p7_{mode}",
            "requested_execute_hardware": True,
            "hardware_actions_executed": True,
            "programmed_candidate": True,
            "started_ps_elf": True,
            "programmed_shutdown_before": True,
            "programmed_shutdown_after": True,
            "child_reaped_before_shutdown_after": True,
            "drove_tfdu_txd": True,
            "enabled_tfdu_receiver": True,
            "uart_access": False,
            "ethernet_used": False,
            "motion_used": False,
            "hardware_execution_lock": self._hardware_lock(
                run, kind="ps", stage_name=f"p7_{mode}", mode=mode
            ),
            "service_runtime_limit_sec": runtime,
            "scheduling_cutoff_sec": 1740 if mode == "stationary" else None,
            "safety_validation": safety,
            "core_hardware_readiness": readiness_record,
            "bundle_manifest": file_record(bundle_manifest_path),
            "execution_plan": file_record(plan),
            "frozen_shutdown": file_record(self.artifacts["shutdown_bitstream"]),
            "raw_evidence_sha256_manifest": file_record(raw_manifest_path),
            "preflight": self._process(
                "preflight", files["preflight_stdout"], files["preflight_stderr"],
                result_file=str(preflight_result), passed=True, failures=[],
                started_at_utc=f"{event_prefix}:00+00:00", ended_at_utc=f"{event_prefix}:01+00:00",
            ),
            "target_identity": self._identity(),
            "ps_process": self._process(
                "ps_application_stage",
                files["stage_stdout"],
                files["stage_stderr"],
                passed=True,
                failures=[],
                argv=["synthetic-ps", mode],
                started_at_utc=f"{event_prefix}:02+00:00",
                ended_at_utc=f"{event_prefix}:03+00:00",
            ),
            "shutdown_before": self._shutdown(files, "before", started_at_utc=f"{event_prefix}:01+00:00", ended_at_utc=f"{event_prefix}:02+00:00"),
            "shutdown_after": self._shutdown(files, "after", started_at_utc=f"{event_prefix}:05+00:00", ended_at_utc=f"{event_prefix}:06+00:00"),
            "postprocess": postprocess,
        }
        summary_path = run / "p7_ps_application_stage_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return summary_path, summary

    def full_pass(self) -> None:
        self.make_jtag(
            "p7_safe_idle_recheck",
            [
                "P7_SAFE_IDLE_RESULT=PASS",
                "P7_SAFE_IDLE_TXD_IDLE=1",
                "P7_SAFE_IDLE_SD_SHUTDOWN=1",
                "P7_SAFE_IDLE_STUCK_HIGH_VIOLATIONS=0",
                "P7_SAFE_IDLE_DUTY_VIOLATIONS=0",
                "P7_SAFE_IDLE_ERROR_COUNT=0",
            ],
        )
        self.make_jtag(
            "p7_p6_frame_regression",
            [
                "P7_P6_FRAME_REGRESSION=PASS",
                "P7_P6_LANE0_FRAMES=10",
                "P7_P6_LANE1_FRAMES=10",
                "P7_P6_MASK3_FRAMES=10",
                "P7_P6_CRC_BAD=0",
                "P7_P6_PAYLOAD_MISMATCH=0",
                "P7_P6_RETRY_EXHAUSTED=0",
                "P7_P6_TX_FAIL=0",
                "P7_P6_DUTY_VIOLATION=0",
                "P7_P6_MAX_TXD_HIGH_CYCLES=8",
            ],
        )
        for length, policy in sorted(subject.REQUIRED_BOUNDARY_JTAG):
            self.make_jtag(
                f"fragment_boundary_{length}_{policy}_deterministic_random",
                [],
                backend=(length, policy, "deterministic_random"),
            )
        for length, policy, pattern in sorted(subject.REQUIRED_LARGE_JTAG):
            name = f"large_object_jtag_{length}_{policy}_{pattern}"
            self.make_jtag(name, [], backend=(length, policy, pattern))

        large_specs = (
            ("1m_lane0", 1_048_576, 1),
            ("1m_lane1", 1_048_576, 2),
            ("1m_stripe", 1_048_576, 3),
            ("1m_replicate", 1_048_576, 4),
            ("64k_counter_stripe", 65_536, 3),
            ("64k_prbs15_stripe", 65_536, 3),
            ("64k_random_stripe", 65_536, 3),
            ("64k_all_bytes_stripe", 65_536, 3),
        )
        functional_cases = [self.case(name, length, policy) for name, length, policy in large_specs]
        for slot, item in enumerate(functional_cases):
            item["slot"] = slot
            item["descriptor"]["object_id"] = (54 + slot) if slot < 4 else (50 + slot - 4)
            item["descriptor"]["completion_sequence"] = (54 + slot) if slot < 4 else (50 + slot - 4)
        boundary = []
        for length in subject.REQUIRED_BOUNDARY_LENGTHS:
            for policy in subject.REQUIRED_BOUNDARY_POLICIES:
                item = self.case(f"boundary_{length}_{policy}", length, policy)
                item["length"] = length
                boundary.append(item)
        mailbox = {"service_state": 4, "shutdown_result": 0}
        checkpoint = self.case("functional_checkpoint_4k", 4_096, 3)
        self.make_ps("functional", {"passed": True, "failures": [], "mailbox": mailbox, "cases": functional_cases, "boundary_cases": boundary, "functional_checkpoint": checkpoint})

        fallback_specs = (
            ("stripe_lane0_to_lane1", 3, 3, 1, 1),
            ("stripe_lane1_to_lane0", 3, 3, 1, 2),
            ("replicate_lane0_unavailable", 3, 4, 1, 1),
            ("replicate_lane1_unavailable", 3, 4, 1, 2),
            ("strict_lane0_unavailable", 4, 1, 0, 1),
            ("strict_lane1_unavailable", 4, 2, 0, 2),
            ("stripe_both_unavailable", 4, 3, 0, 3),
        )
        fallback_cases = [
            self.case(
                name,
                65_536,
                policy,
                status=status,
                error=0 if status == 3 else 8,
                fallback=fallback,
                unavailable=unavailable,
                unavailable_after=2 if name.startswith("stripe_lane") else 0,
            )
            for name, status, policy, fallback, unavailable in fallback_specs
        ]
        for slot, item in enumerate(fallback_cases):
            item["slot"] = slot
            item["descriptor"]["object_id"] = slot + 1
            item["descriptor"]["completion_sequence"] = slot + 1
        self.make_ps("fault-fallback", {"passed": True, "failures": [], "mailbox": mailbox, "cases": fallback_cases}, ["P7_FAULT_MODEL=SOFTWARE_INJECTED_SCHEDULER_FAULT"])

        abort_cases = [
            self.case("abort_mid_object", 1_048_576, 3, status=5, error=15),
            self.case("restart_new_epoch", 1_048_576, 3),
            self.case("duplicate_replay_rejected", 1_048_576, 3, status=6, error=19),
        ]
        for slot, item in enumerate(abort_cases):
            item["slot"] = slot
            item["descriptor"]["object_id"] = (1, 2, 2)[slot]
            item["descriptor"]["session_epoch"] = 0x50370001 + int(slot > 0)
            item["descriptor"]["completion_sequence"] = (1, 1, 2)[slot]
        self.make_ps(
            "abort-restart",
            {"passed": True, "failures": [], "mailbox": mailbox, "cases": abort_cases},
            [
                "P7_ABORT_RESTART_NEW_EPOCH=1", "P7_ABORT_RESTART_REPLAY_REJECTED=1",
                "P7_ABORT_INTERPHASE_SHUTDOWN_PROGRAMMED=1", "P7_ABORT_RESTART_CANDIDATE_REPROGRAMMED=1",
            ],
        )

        queue_mailbox = {"service_state": 4, "shutdown_result": 0, "queue_high_watermark": 8, "backpressure_events": 1, "abort_count": 1}
        queue_cases = [self.case(f"queue_{index}", 512 + index, 3) for index in range(8)]
        for slot, item in enumerate(queue_cases):
            item["slot"] = slot
            item["descriptor"]["object_id"] = slot + 1
            item["descriptor"]["completion_sequence"] = slot + 1
        self.make_ps(
            "queue",
            {"passed": True, "failures": [], "mailbox": queue_mailbox, "cases": queue_cases},
            [
                "P7_QUEUE_DEPTH1_COMPLETE=1", "P7_QUEUE_FULL_BEFORE_RUN=1",
                "P7_QUEUE_STOP_WHILE_QUEUED=1", "P7_QUEUE_OVERFLOW_REJECTED_BEFORE_DDR_WRITE=1",
                "P7_QUEUE_PRODUCER_FASTER_THAN_CONSUMER=1", "P7_QUEUE_MAX_FIFO_COMPLETE=1",
                "P7_QUEUE_ABORT_WHILE_QUEUED=1", "P7_QUEUE_INTERPHASE_SHUTDOWN_1_PROGRAMMED=1",
                "P7_QUEUE_INTERPHASE_CANDIDATE_REPROGRAM_1=1", "P7_QUEUE_INTERPHASE_SHUTDOWN_2_PROGRAMMED=1",
                "P7_QUEUE_INTERPHASE_CANDIDATE_REPROGRAM_2=1", "P7_QUEUE_INTERPHASE_SHUTDOWN_COUNT=2",
                "P7_QUEUE_OVERFLOW_ADMISSION=FULL", "P7_QUEUE_OVERFLOW_OCCUPANCY=8",
                "P7_QUEUE_OVERFLOW_CAPACITY=8", "P7_QUEUE_OVERFLOW_DDR_WRITE=0",
                "P7_QUEUE_OVERFLOW_DDR_WRITE_COUNT=0", "P7_QUEUE_OVERFLOW_CANDIDATE_OBJECT_ID=9",
            ],
        )

        stationary_cases = []
        slots = (
            (1_048_576, 1, 0, "deterministic_random"),
            (65_536, 3, 1, "counter"),
            (65_536, 3, 2, "prbs15"),
            (65_536, 2, 0, "binary_all_byte_values_repeated"),
            (1_048_576, 4, 0, "deterministic_random"),
            (4_096, 3, 0, "counter"),
            (65_536, 1, 0, "prbs15"),
            (65_536, 2, 0, "binary_all_byte_values_repeated"),
        )
        runtime_start_ticks = 1_000_000_000
        for slot, (length, policy, unavailable, pattern) in enumerate(slots):
            fallback = 1 if unavailable else 0
            case = self.case(
                f"stationary_{pattern}_{length}_slot_{slot}",
                length,
                policy,
                fallback=fallback,
                unavailable=unavailable,
                unavailable_after=2 if unavailable else 0,
            )
            case["slot"] = slot
            stationary_cases.append(case)
        objects = []
        slot_generations = {slot: 0 for slot in range(len(stationary_cases))}
        for sequence in range(1, 91):
            slot = (sequence - 1) % len(stationary_cases)
            case = stationary_cases[slot]
            descriptor = case["descriptor"]
            length = int(descriptor["object_length"])
            fallback = int(descriptor["fallback_count"])
            end_elapsed_ticks = sequence * 19 * subject.PS_COUNTS_PER_SECOND
            object_latency_ticks = int(descriptor["fragments_total"]) * 2 + 10
            generation = slot_generations[slot]
            slot_generations[slot] += 1
            objects.append(
                {
                    "sequence": sequence,
                    "slot": slot,
                    "generation": generation,
                    "session_epoch": 0x50370001,
                    "object_id": sequence,
                    "status": 3,
                    "error_code": 0,
                    "bytes_completed": length,
                    "fragments_completed": descriptor["fragments_total"],
                    "fragments_total": descriptor["fragments_total"],
                    "fragment_attempts": descriptor["fragments_total"],
                    "fallback_count": fallback,
                    "output_sha256": descriptor["expected_sha256"],
                    "p6_retry_count": 0,
                    "p6_retry_exhausted": 0,
                    "p6_tx_fail": 0,
                    "p6_crc_bad": 0,
                    "p6_payload_mismatch": 0,
                    "max_txd_high_cycles": 8,
                    "duty_violations": 0,
                    "lane0_fragments": descriptor["lane0_fragments"],
                    "lane1_fragments": descriptor["lane1_fragments"],
                    "replicated_fragments": descriptor["replicated_fragments"],
                    "start_ticks": runtime_start_ticks + end_elapsed_ticks - object_latency_ticks,
                    "end_ticks": runtime_start_ticks + end_elapsed_ticks,
                }
            )
        samples = []
        for index in range(1, 61):
            elapsed_sec = 30.0 * index
            elapsed_ticks = int(elapsed_sec * subject.PS_COUNTS_PER_SECOND)
            queue_not_before_ticks = elapsed_ticks if index < 60 else int(1800.2 * subject.PS_COUNTS_PER_SECOND)
            terminal = sum(
                1 for item in objects
                if int(item["end_ticks"]) - runtime_start_ticks <= elapsed_ticks
            )
            prefix = objects[:terminal]
            previous_elapsed_ticks = 0 if index == 1 else int((30.0 * (index - 1)) * subject.PS_COUNTS_PER_SECOND)
            interval = [
                item for item in prefix
                if int(item["end_ticks"]) - runtime_start_ticks > previous_elapsed_ticks
            ]
            previous_prefix = [
                item for item in objects
                if int(item["end_ticks"]) - runtime_start_ticks <= previous_elapsed_ticks
            ]
            latency_count = len(interval)
            interval_latencies = sorted(int(item["end_ticks"]) - int(item["start_ticks"]) for item in interval)
            def interval_rank(numerator: int, denominator: int) -> int:
                rank = max(0, ((numerator * len(interval_latencies) + denominator - 1) // denominator) - 1)
                return interval_latencies[min(rank, len(interval_latencies) - 1)]
            delta_ticks = elapsed_ticks - previous_elapsed_ticks
            completed_bytes = sum(item["bytes_completed"] for item in prefix)
            previous_bytes = sum(item["bytes_completed"] for item in previous_prefix)
            samples.append(
                {
                    "sequence": index,
                    "elapsed_sec": elapsed_sec,
                    "elapsed_ticks": elapsed_ticks,
                    "queue_observation_not_before_ticks": queue_not_before_ticks,
                    "window": "CALIBRATION" if index <= 10 else "ACCEPTANCE",
                    "objects": terminal,
                    "failed": 0,
                    "bytes": sum(item["bytes_completed"] for item in prefix),
                    "fragments": sum(item["fragments_completed"] for item in prefix),
                    "lane0": sum(item["lane0_fragments"] for item in prefix),
                    "lane1": sum(item["lane1_fragments"] for item in prefix),
                    "replicated": sum(item["replicated_fragments"] for item in prefix),
                    "fallbacks": sum(item["fallback_count"] for item in prefix),
                    "p6_retries": 0,
                    "p6_retry_exhausted": 0,
                    "p6_tx_fail": 0,
                    "p6_crc_bad": 0,
                    "p6_payload_mismatch": 0,
                    "max_txd_high": 8,
                    "duty_violations": 0,
                    "queue_occupancy": 0,
                    "queue_high": 8,
                    "backpressure": 1,
                    "current_bps": (completed_bytes * 8 * subject.PS_COUNTS_PER_SECOND) // elapsed_ticks,
                    "rolling_bps": ((completed_bytes - previous_bytes) * 8 * subject.PS_COUNTS_PER_SECOND) // delta_ticks,
                    "latency_count": latency_count,
                    "latency_min_ticks": interval_latencies[0] if latency_count else 0,
                    "latency_mean_ticks": sum(interval_latencies) // latency_count if latency_count else 0,
                    "latency_p50_ticks": interval_rank(50, 100) if latency_count else 0,
                    "latency_p95_ticks": interval_rank(95, 100) if latency_count else 0,
                    "latency_p99_ticks": interval_rank(99, 100) if latency_count else 0,
                    "latency_max_ticks": interval_latencies[-1] if latency_count else 0,
                    "last_object": prefix[-1]["object_id"] if prefix else 0,
                }
            )
        stationary_mailbox = {
            "service_state": 4,
            "shutdown_result": 0,
            "max_runtime_seconds": 1800,
            "calibration_window_seconds": 300,
            "sample_interval_seconds": 30,
            "runtime_flags": 0x2,
            "runtime_elapsed_request": 7,
            "runtime_elapsed_ack": 7,
            "terminal_unacknowledged_refresh": False,
            "observed_wall_seconds": 1800.2,
            "runtime_start_ticks": runtime_start_ticks,
            "objects_requested": len(objects),
            "objects_completed": len(objects),
            "objects_failed": 0,
            "bytes_completed": sum(item["bytes_completed"] for item in objects),
            "fragments_completed": sum(item["fragments_completed"] for item in objects),
            "lane0_fragments": sum(item["lane0_fragments"] for item in objects),
            "lane1_fragments": sum(item["lane1_fragments"] for item in objects),
            "fallback_count": sum(item["fallback_count"] for item in objects),
            "queue_high_watermark": 8,
            "backpressure_events": 1,
            "p6_retry_count": 0,
            "p6_retry_exhausted": 0,
            "p6_tx_fail": 0,
            "p6_crc_bad": 0,
            "p6_payload_mismatch": 0,
            "max_txd_high_cycles": 8,
            "duty_violation_count": 0,
            "metrics_time_sources": "ps_global_timer_for_scheduler_samples_goodput_fragment_and_object_latency;host_wall_clock_for_preload_and_independent_duration_watchdog",
        }
        fragments_completed = sum(item["fragments_completed"] for item in objects)
        lane0_total = sum(item["lane0_fragments"] for item in objects)
        lane1_total = sum(item["lane1_fragments"] for item in objects)
        replicated_total = sum(item["replicated_fragments"] for item in objects)
        fallback_lane0_to_lane1 = sum(
            int(stationary_cases[int(item["slot"])]["descriptor"].get("unavailable_lane_mask", 0)) == 1
            for item in objects
        )
        fallback_lane1_to_lane0 = sum(
            int(stationary_cases[int(item["slot"])]["descriptor"].get("unavailable_lane_mask", 0)) == 2
            for item in objects
        )
        stationary_trace_validation = {
            "passed": True,
            "failures": [],
            "terminal_bundles_expected": len(objects),
            "terminal_bundle_markers_observed": len(objects),
            "artifact_files_expected": 3 * len(objects),
            "files_observed": 3 * len(objects),
            "terminal_bundles_validated": len(objects),
            "fragment_trace_entries": fragments_completed,
            "fragment_latency_samples": fragments_completed,
            "fragments_rejected": 0,
            "fragments_duplicated": 0,
            "fragments_out_of_order": 0,
            "fallback_lane0_to_lane1": fallback_lane0_to_lane1,
            "fallback_lane1_to_lane0": fallback_lane1_to_lane0,
            "sha256_mismatches": 0,
            "whole_object_crc_failures": 0,
            "percentile_method": "nearest_rank",
            "records": [],
        }
        host_input_bytes = sum(item["bytes_completed"] for item in objects)
        runtime_ticks = int(samples[-1]["queue_observation_not_before_ticks"])
        stationary_mailbox["runtime_elapsed_ticks"] = runtime_ticks
        fragment_tick_us = round(1_000_000.0 / subject.PS_COUNTS_PER_SECOND, 6)
        object_latency_ticks = sorted(int(item["end_ticks"]) - int(item["start_ticks"]) for item in objects)
        object_p95_rank = max(0, ((95 * len(object_latency_ticks) + 99) // 100) - 1)
        def object_ticks_to_ms(value: float) -> float:
            return round(value * 1000.0 / subject.PS_COUNTS_PER_SECOND, 6)
        application_metrics = {
            "objects_requested": len(objects), "objects_completed": len(objects), "objects_failed": 0,
            "fragments_generated": fragments_completed, "fragments_submitted": fragments_completed,
            "fragments_completed": fragments_completed, "fragments_retried": 0,
            "fragments_duplicated": 0, "fragments_rejected": 0, "fragments_out_of_order": 0,
            "bytes_requested": sum(item["bytes_completed"] for item in objects),
            "bytes_completed": sum(item["bytes_completed"] for item in objects),
            "whole_object_crc_failures": 0, "sha256_mismatches": 0,
            "lane0_fragments": lane0_total, "lane1_fragments": lane1_total,
            "replicated_fragments": replicated_total,
            "fallback_lane0_to_lane1": fallback_lane0_to_lane1,
            "fallback_lane1_to_lane0": fallback_lane1_to_lane0,
            "queue_high_watermark": 8, "backpressure_events": 1,
            "host_to_ps_bytes_per_sec": host_input_bytes,
            "application_goodput_bps": (host_input_bytes * 8 * subject.PS_COUNTS_PER_SECOND) // runtime_ticks,
            "fragment_latency_min_us": fragment_tick_us,
            "fragment_latency_mean_us": fragment_tick_us,
            "fragment_latency_p50_us": fragment_tick_us,
            "fragment_latency_p95_us": fragment_tick_us,
            "fragment_latency_p99_us": fragment_tick_us,
            "fragment_latency_max_us": fragment_tick_us,
            "object_latency_min_ms": object_ticks_to_ms(object_latency_ticks[0]),
            "object_latency_mean_ms": object_ticks_to_ms(sum(object_latency_ticks) / len(object_latency_ticks)),
            "object_latency_p95_ms": object_ticks_to_ms(object_latency_ticks[object_p95_rank]),
            "object_latency_max_ms": object_ticks_to_ms(object_latency_ticks[-1]),
            "p6_retry_count": 0, "p6_retry_exhausted": 0, "p6_tx_fail": 0,
            "p6_crc_bad": 0, "p6_payload_mismatch": 0, "max_txd_high_cycles": 8,
            "duty_violation_count": 0, "shutdown_result": 0,
            "fragment_latency_sample_count": fragments_completed,
            "object_latency_sample_count": len(objects),
            "host_to_ps_input_bytes": host_input_bytes,
            "host_to_ps_input_duration_ms": 1000, "host_to_ps_bits_per_sec": host_input_bytes * 8,
            "ps_counts_per_second": subject.PS_COUNTS_PER_SECOND, "ps_runtime_elapsed_ticks": runtime_ticks,
            "latency_percentile_method": "nearest_rank",
            "time_sources": {
                "host_to_ps_bytes_per_sec": "Tcl host wall clock milliseconds around preload",
                "application_goodput_bps": "PS global timer runtime elapsed ticks",
                "fragment_latency": "PS global timer ticks",
                "object_latency": "PS global timer ticks",
            },
            "validated": True, "failures": [],
        }
        self.make_ps(
            "stationary",
            {
                "passed": True, "failures": [], "mailbox": stationary_mailbox,
                "cases": stationary_cases, "stationary_objects": objects,
                "stationary_samples": samples,
                "stationary_trace_validation": stationary_trace_validation,
                "application_metrics": application_metrics,
            },
            [
                "P7_STATIONARY_PRIMARY_TIME_SOURCE=PS_RUNTIME_ELAPSED_TICKS",
                "P7_STATIONARY_HOST_TIME_ROLE=INDEPENDENT_WATCHDOG_AND_INPUT_PRELOAD",
                "P7_STATIONARY_SAMPLE_SEMANTICS=FIXED_PS_THRESHOLDS_FROM_IMMUTABLE_TERMINAL_END_TICKS",
                f"P7_STATIONARY_RUNTIME_START_TICKS={runtime_start_ticks}",
                "P7_CALIBRATION_WINDOW_COMPLETE=1",
                "P7_ACCEPTANCE_WINDOW_COMPLETE=1",
                "P7_REQUEUE_AFTER_CUTOFF=0",
                "P7_STATIONARY_REQUEUE_CUTOFF_VIOLATION=0",
                f"P7_STATIONARY_REQUEUE_CUTOFF_TICKS={1740 * subject.PS_COUNTS_PER_SECOND}",
                "P7_STATIONARY_DRAIN_COMPLETE_ELAPSED=1750.000",
                f"P7_STATIONARY_DRAIN_COMPLETE_TICKS={1750 * subject.PS_COUNTS_PER_SECOND}",
                "P7_STATIONARY_WALL_SECONDS=1800.200",
                "P7_STATIONARY_HOST_WATCHDOG_CORROBORATION=PASS",
                f"P7_STATIONARY_TERMINAL_DESCRIPTORS={len(objects)}",
                f"P7_STATIONARY_PS_ELAPSED_TICKS={runtime_ticks}",
                "P7_TERMINAL_UNACKNOWLEDGED_REFRESH=0",
                "P7_TERMINAL_UNACKNOWLEDGED_REQUEST=7",
                "P7_TERMINAL_UNACKNOWLEDGED_ACK=7",
                "P7_SAMPLE_00060_SAFE_TERMINAL_STATE=1",
                "P7_SAMPLE_SEQUENCE_WRITER=HOST_POST_TERMINAL",
                f"P7_HOST_TO_PS_INPUT_BYTES={host_input_bytes}",
                "P7_HOST_TO_PS_INPUT_DURATION_MS=1000",
                f"P7_HOST_TO_PS_INPUT_BYTES_PER_SEC={host_input_bytes}",
                f"P7_HOST_TO_PS_INPUT_BPS={host_input_bytes * 8}",
            ],
        )
        offline = self.root / "evidence" / "generated" / "p7_offline_gate_summary.json"
        offline.parent.mkdir(parents=True, exist_ok=True)
        offline_source_hashes: dict[str, str] = {}
        for relative in set(subject.OFFLINE_CRITICAL_SOURCES) | set(subject.HISTORICAL_GIT_CRITICAL_SOURCES):
            source = self.root / relative
            if not source.is_file():
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(f"synthetic offline source: {relative}\n", encoding="utf-8")
            offline_source_hashes[relative] = digest(source)
        offline.write_text(
            json.dumps(
                {
                    "P7_OFFLINE_GATE": "PASS",
                    "generated_at_utc": "2026-07-10T01:00:00+00:00",
                    "NO_HARDWARE_ACTIONS_EXECUTED": True,
                    "hardware_actions_executed": False,
                    "HARDWARE_ACCEPTANCE": "PENDING_HW",
                    "checks": {
                        "P7_CLEAN_SOURCE_CHECKPOINT": True,
                        "P7_CHECKPOINT_INPUT_HASHES": True,
                    },
                    "source_commit": self.commit,
                    "dirty_worktree": False,
                    "source_tree_listing_sha256": (
                        hashlib.sha256(
                            subprocess.run(
                                ["git", "ls-tree", "-r", "--full-tree", self.commit],
                                cwd=self.root,
                                text=True,
                                capture_output=True,
                                check=True,
                            ).stdout.encode("utf-8")
                        ).hexdigest()
                        if (self.root / ".git").exists()
                        else "c" * 64
                    ),
                    "checkpoint_input_hashes": offline_source_hashes,
                    "checkpoint_input_count": len(offline_source_hashes),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        evidence = subject.RepositoryEvidence(self.root, self.hardware, self.output)
        subject.discover(evidence)
        subject.generate_sequence_ledger(
            evidence,
            ledger_path=self.hardware / "p7_run_sequence_ledger.json",
            offline_checkpoint_summary=offline,
            offline_checkpoint_sha256=digest(offline),
            offline_checkpoint_commit=self.commit,
        )


class SummarizeP7HardwareTests(unittest.TestCase):
    @staticmethod
    def _git(root: Path, *args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()

    def _make_historical_fixture(self, root: Path) -> tuple[SyntheticEvidence, str, str]:
        fixture = SyntheticEvidence(root)
        self._git(root, "init")
        self._git(root, "config", "user.email", "synthetic@example.invalid")
        self._git(root, "config", "user.name", "Synthetic P7 Test")
        for relative in set(subject.OFFLINE_CRITICAL_SOURCES) | set(subject.HISTORICAL_GIT_CRITICAL_SOURCES):
            source = root / relative
            if not source.is_file():
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(f"synthetic pre-commit source: {relative}\n", encoding="utf-8")
        self._git(root, "add", "-A")
        self._git(root, "commit", "-m", "old source checkpoint")
        old_commit = self._git(root, "rev-parse", "HEAD")
        fixture.make_historical_read_only_preflight_epoch(old_commit)
        self._git(root, "add", "-A")
        self._git(root, "commit", "-m", "active source checkpoint")
        active_commit = self._git(root, "rev-parse", "HEAD")
        fixture.commit = active_commit
        fixture.full_pass()
        return fixture, old_commit, active_commit

    def _make_multi_historical_fixture(
        self,
        root: Path,
    ) -> tuple[SyntheticEvidence, str, str, str]:
        fixture = SyntheticEvidence(root)
        self._git(root, "init")
        self._git(root, "config", "user.email", "synthetic@example.invalid")
        self._git(root, "config", "user.name", "Synthetic P7 Test")
        for relative in set(subject.OFFLINE_CRITICAL_SOURCES) | set(subject.HISTORICAL_GIT_CRITICAL_SOURCES):
            source = root / relative
            if not source.is_file():
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(f"synthetic pre-commit source: {relative}\n", encoding="utf-8")
        self._git(root, "add", "-A")
        self._git(root, "commit", "-m", "r1 source checkpoint")
        r1_commit = self._git(root, "rev-parse", "HEAD")
        fixture.make_historical_read_only_preflight_epoch(
            r1_commit,
            epoch_name="historical_epoch_r1",
            hour=0,
        )
        self._git(root, "add", "-A")
        self._git(root, "commit", "-m", "r2 source checkpoint")
        r2_commit = self._git(root, "rev-parse", "HEAD")
        fixture.make_historical_read_only_preflight_epoch(
            r2_commit,
            epoch_name="historical_epoch_r2",
            hour=0,
            minute_offset=20,
            identity_pass_containment_failure=True,
        )
        self._git(root, "add", "-A")
        self._git(root, "commit", "-m", "active source checkpoint")
        active_commit = self._git(root, "rev-parse", "HEAD")
        fixture.commit = active_commit
        fixture.full_pass()
        return fixture, r1_commit, r2_commit, active_commit

    @staticmethod
    def _validate_ledger(fixture: SyntheticEvidence) -> tuple[str, list[str], dict[str, object]]:
        evidence = subject.RepositoryEvidence(fixture.root, fixture.hardware, fixture.output)
        subject.discover(evidence)
        return subject.validate_sequence_ledger(evidence)

    def test_duplicate_markers_and_orphan_hardware_footprints_fail_closed(self) -> None:
        parsed, duplicates = subject.parse_marker_text("P7_RESULT=PASS\nP7_RESULT=FAIL\n")
        self.assertEqual(parsed["P7_RESULT"], "PASS")
        self.assertEqual(duplicates, ["P7_RESULT"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hardware = root / "evidence" / "hardware" / "p7"
            run = hardware / "ps_application" / "orphan_run"
            run.mkdir(parents=True)
            (run / "p7_ps_application_raw_result.log").write_text(
                "P7_PS_CANDIDATE_PROGRAMMED=1\nP7_PS_ELF_DOWNLOADED=1\n",
                encoding="utf-8",
            )
            payload, returncode = subject.summarize(root, hardware, root / "evidence" / "generated")
            self.assertEqual(returncode, 1)
            self.assertEqual(payload["stages"]["consistency"]["result"], "FAIL")
            self.assertIn("no parseable final safe-wrapper summary", "\n".join(payload["stages"]["consistency"]["errors"]))

    def test_generic_shutdown_accepts_only_unique_fresh_authorized_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = SyntheticEvidence(Path(temporary))
            summary_path, _summary = fixture.make_jtag(
                "p7_safe_idle_recheck",
                [
                    "P7_SAFE_IDLE_RESULT=PASS",
                    "P7_SAFE_IDLE_TXD_IDLE=1",
                    "P7_SAFE_IDLE_SD_SHUTDOWN=1",
                    "P7_SAFE_IDLE_STUCK_HIGH_VIOLATIONS=0",
                    "P7_SAFE_IDLE_DUTY_VIOLATIONS=0",
                    "P7_SAFE_IDLE_ERROR_COUNT=0",
                ],
            )
            evidence = subject.RepositoryEvidence(fixture.root, fixture.hardware, fixture.output)
            subject.discover(evidence)
            candidate = next(item for item in evidence.candidates if item.path == summary_path)
            result_path = summary_path.parent / "p7_shutdown_after_result.txt"
            stdout_path = summary_path.parent / "shutdown_after.stdout.log"
            valid_result = result_path.read_text(encoding="utf-8")
            self.assertEqual([], subject.shutdown_errors(candidate, "after", evidence=evidence))
            ledger_shutdown = subject._ledger_shutdown(candidate, "after", evidence)
            self.assertTrue(ledger_shutdown["attempted"])
            self.assertTrue(ledger_shutdown["programming_attempted"])
            self.assertTrue(ledger_shutdown["programming_attempted_marker"])
            self.assertTrue(ledger_shutdown["tfdu_shutdown_marker"])
            self.assertTrue(ledger_shutdown["tfdu_shutdown_path_matches_authorized"])
            self.assertTrue(ledger_shutdown["p7_shutdown_result_pass"])

            def errors_for(result_text: str, *, attempted: object = True, programming_attempted: object = True) -> str:
                result_path.write_text(result_text, encoding="utf-8")
                candidate.data["shutdown_after"]["attempted"] = attempted
                candidate.data["shutdown_after"]["programming_attempted"] = programming_attempted
                return "\n".join(subject.shutdown_errors(candidate, "after", evidence=evidence))

            authorized = fixture.artifacts["shutdown_bitstream"].resolve()
            stdout_path.write_text(valid_result, encoding="utf-8")
            self.assertIn(
                "fresh result lacks TFDU_SHUTDOWN_PROGRAMMED",
                errors_for("P7_TCL_PROGRAMMING_ATTEMPTED=1\nP7_SHUTDOWN_RESULT=PASS\nSHUTDOWN_EXIT=0\n"),
            )
            self.assertIn(
                "fresh result lacks TFDU_SHUTDOWN_PROGRAMMED",
                errors_for("P7_TCL_PROGRAMMING_ATTEMPTED=1\nP7_SHUTDOWN_RESULT=PASS\n"),
            )
            self.assertIn(
                "does not match the authorized shutdown bit",
                errors_for(
                    "P7_TCL_PROGRAMMING_ATTEMPTED=1\n"
                    "TFDU_SHUTDOWN_PROGRAMMED=C:/wrong/shutdown.bit\n"
                    "P7_SHUTDOWN_RESULT=PASS\n"
                ),
            )
            self.assertIn(
                "duplicate markers",
                errors_for(valid_result + f"TFDU_SHUTDOWN_PROGRAMMED={authorized}\n"),
            )
            self.assertIn(
                "lacks exact P7_TCL_PROGRAMMING_ATTEMPTED=1",
                errors_for(
                    f"TFDU_SHUTDOWN_PROGRAMMED={authorized}\nP7_SHUTDOWN_RESULT=PASS\n"
                ),
            )
            self.assertIn(
                "was not attempted",
                errors_for(valid_result, attempted=False),
            )
            self.assertIn(
                "does not prove programming_attempted=true",
                errors_for(valid_result, programming_attempted=False),
            )
            result_path.write_text(valid_result, encoding="utf-8")
            candidate.data["shutdown_after"]["attempted"] = True
            candidate.data["shutdown_after"]["programming_attempted"] = True

    def test_process_record_recomputes_daemon_topology_and_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stdout = root / "stdout.log"
            stderr = root / "stderr.log"
            stdout.write_text("ok\n", encoding="utf-8")
            stderr.write_text("", encoding="utf-8")
            vivado = r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat"
            helper_dir = Path(vivado).parent / "unwrapped/win64.o"
            system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
            paths = {
                "cs_server": str(helper_dir / "cs_server.exe"),
                "rdi_xsdb": str(helper_dir / "rdi_xsdb.exe"),
                "cmd": str(system_root / "System32/cmd.exe"),
                "conhost": str(system_root / "System32/conhost.exe"),
            }
            initial = [
                {"pid": 100, "parent_pid": 9001, "parent_active_globally": False, "image_path": paths["cs_server"], "creation_time_100ns": 1000},
                {"pid": 101, "parent_pid": 100, "parent_active_globally": True, "image_path": paths["cs_server"], "creation_time_100ns": 1001},
                {"pid": 200, "parent_pid": 9002, "parent_active_globally": False, "image_path": paths["cmd"], "creation_time_100ns": 2000},
                {"pid": 201, "parent_pid": 200, "parent_active_globally": True, "image_path": paths["rdi_xsdb"], "creation_time_100ns": 2001},
                {"pid": 202, "parent_pid": 200, "parent_active_globally": True, "image_path": paths["conhost"], "creation_time_100ns": 2002},
                {"pid": 300, "parent_pid": 9003, "parent_active_globally": False, "image_path": paths["conhost"], "creation_time_100ns": 3000},
            ]
            shrink = [
                {**initial[1], "parent_active_globally": False},
                {**initial[3], "parent_active_globally": False},
            ]
            record = {
                "returncode": 0,
                "timed_out": False,
                "abort_seen": False,
                "interrupted": False,
                "process_tree_terminated": False,
                "process_tree_reaped": True,
                "containment_kind": "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE",
                "containment_assigned": True,
                "containment_closed": True,
                "descendant_count_after": 0,
                "containment_cleanup_attempted": False,
                "containment_cleanup_terminated": False,
                "expected_tool_daemon_grace_used": True,
                "expected_tool_daemon_grace_seconds": 30.0,
                "expected_tool_daemon_grace_elapsed_seconds": 0.21,
                "expected_tool_daemon_paths": [paths[role] for role in subject.EXPECTED_VIVADO_HELPER_ROLES],
                "descendant_paths_seen": [item["image_path"] for item in initial],
                "descendant_processes_seen": initial,
                "expected_tool_daemon_classification": "EXACT_R2_VIVADO_EXIT_HELPER_FOREST",
                "expected_tool_daemon_topology_snapshots": [
                    {
                        "classification": "EXACT_R2_VIVADO_EXIT_HELPER_FOREST",
                        "elapsed_seconds": 0.01,
                        "processes": initial,
                    },
                    {
                        "classification": "STRICT_SHRINK_SUBSET_OF_EXACT_R2_VIVADO_EXIT_HELPER_FOREST",
                        "elapsed_seconds": 0.11,
                        "processes": shrink,
                    },
                    {"classification": "EMPTY", "elapsed_seconds": 0.21, "processes": []},
                ],
                "expected_tool_daemon_topology_revalidation_count": 2,
                "expected_tool_daemon_topology_monotonic": True,
                "expected_tool_daemon_topology_sample_elapsed_seconds": [0.0, 0.01, 0.11, 0.21],
                "expected_tool_daemon_topology_max_sample_gap_seconds": 0.1,
                "expected_tool_daemon_topology_terminal_empty": True,
                "expected_tool_daemon_hashes_verified": True,
                "expected_tool_daemon_sha256_by_role": subject.EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE,
                "expected_tool_daemon_hash_error": "",
                "expected_tool_daemon_prelaunch_hashes_verified": True,
                "expected_tool_daemon_prelaunch_sha256_by_role": subject.EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE,
                "expected_tool_daemon_prelaunch_hash_error": "",
                "expected_tool_daemon_postexit_hashes_verified": True,
                "expected_tool_daemon_postexit_sha256_by_role": subject.EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE,
                "expected_tool_daemon_postexit_hash_error": "",
                "expected_tool_daemon_topology_error": "",
                "process_identity_query_retry_count": 0,
                "process_exit_race_recheck_count": 0,
                "process_exit_race_rechecked": False,
                "process_identity_query_retried": False,
                "containment_query_error": "",
                "launch_error": "",
                "argv": [vivado, "-mode", "batch"],
                "stdout_path": str(stdout),
                "stderr_path": str(stderr),
            }
            self.assertEqual(
                [],
                subject.process_record_errors(
                    record, "process", document=root / "summary.json", repo_root=root
                ),
            )

            def errors_for(value: dict[str, object]) -> str:
                return "\n".join(
                    subject.process_record_errors(
                        value, "process", document=root / "summary.json", repo_root=root
                    )
                )

            self.assertIn("process_tree_terminated=true", errors_for({**record, "process_tree_terminated": True}))
            self.assertIn("attempted forced containment cleanup", errors_for({**record, "containment_cleanup_attempted": True}))
            self.assertIn("helper prelaunch hash map mismatch", errors_for({**record, "expected_tool_daemon_prelaunch_sha256_by_role": {**subject.EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE, "cs_server": "0" * 64}}))
            self.assertIn("helper grace is not the fixed 30-second window", errors_for({**record, "expected_tool_daemon_grace_seconds": 10.0}))
            self.assertIn("identity-query retry count exceeds the global bound", errors_for({**record, "process_identity_query_retry_count": 2, "process_identity_query_retried": True}))
            self.assertIn("non-Vivado process records helper paths", errors_for({**record, "argv": [r"D:\Xilinx\Vivado\2023.1\bin\vivado.exe"]}))
            system_path_tamper = list(record["expected_tool_daemon_paths"])
            system_path_tamper[2] = r"C:\attacker\cmd.exe"
            self.assertIn("helper paths are not exactly derived from argv[0]", errors_for({**record, "expected_tool_daemon_paths": system_path_tamper}))
            with mock.patch.object(subject, "_audited_windows_system_directory", return_value=None):
                self.assertIn("non-Vivado process records helper paths", errors_for(record))
            self.assertIn("topology does not terminate in EMPTY", errors_for({**record, "expected_tool_daemon_topology_snapshots": record["expected_tool_daemon_topology_snapshots"][:-1]}))

            mutated_creation = json.loads(json.dumps(record))
            mutated_creation["expected_tool_daemon_topology_snapshots"][1]["processes"][0]["creation_time_100ns"] += 1
            self.assertIn("is not an immutable strict shrink", errors_for(mutated_creation))
            mutated_parent = json.loads(json.dumps(record))
            mutated_parent["expected_tool_daemon_topology_snapshots"][1]["processes"][0]["parent_pid"] = 9999
            self.assertIn("is not an immutable strict shrink", errors_for(mutated_parent))
            mutated_parent_activity = json.loads(json.dumps(record))
            mutated_parent_activity["expected_tool_daemon_topology_snapshots"][1]["processes"][0]["parent_active_globally"] = True
            self.assertIn("is not an immutable strict shrink", errors_for(mutated_parent_activity))
            mutated_root_activity = json.loads(json.dumps(record))
            mutated_root_activity["expected_tool_daemon_topology_snapshots"][0]["processes"][0]["parent_active_globally"] = True
            self.assertIn("initial helper topology is not independently approved", errors_for(mutated_root_activity))
            nonterminal_empty_time = json.loads(json.dumps(record))
            nonterminal_empty_time["expected_tool_daemon_topology_snapshots"][-1]["elapsed_seconds"] = 0.11
            self.assertIn("terminal EMPTY snapshot is not the final topology sample", errors_for(nonterminal_empty_time))
            wrong_initial_time = json.loads(json.dumps(record))
            wrong_initial_time["expected_tool_daemon_topology_snapshots"][0]["elapsed_seconds"] = 0.0
            self.assertIn("initial helper snapshot is not bound to the post-identity sample", errors_for(wrong_initial_time))
            reappearing = json.loads(json.dumps(record))
            reappearing["expected_tool_daemon_topology_snapshots"].insert(
                2,
                {
                    "classification": "STRICT_SHRINK_SUBSET_OF_EXACT_R2_VIVADO_EXIT_HELPER_FOREST",
                    "elapsed_seconds": 0.16,
                    "processes": [
                        {**initial[1], "parent_active_globally": False},
                        initial[2],
                        initial[3],
                    ],
                },
            )
            reappearing["expected_tool_daemon_topology_sample_elapsed_seconds"].insert(3, 0.16)
            reappearing["expected_tool_daemon_topology_revalidation_count"] = 3
            self.assertIn("is not an immutable strict shrink", errors_for(reappearing))

            no_grace = {
                **record,
                "expected_tool_daemon_grace_used": False,
                "expected_tool_daemon_grace_seconds": 0.0,
                "expected_tool_daemon_grace_elapsed_seconds": 0.0,
                "descendant_paths_seen": [],
                "descendant_processes_seen": [],
                "expected_tool_daemon_classification": "NONE",
                "expected_tool_daemon_topology_snapshots": [
                    {"classification": "EMPTY", "elapsed_seconds": 0.0, "processes": []}
                ],
                "expected_tool_daemon_topology_revalidation_count": 0,
                "expected_tool_daemon_topology_monotonic": False,
                "expected_tool_daemon_topology_sample_elapsed_seconds": [0.0],
                "expected_tool_daemon_topology_max_sample_gap_seconds": 0.0,
            }
            self.assertEqual([], subject.process_record_errors(no_grace, "process", document=root / "summary.json", repo_root=root))
            self.assertIn("records grace duration without helper grace", errors_for({**no_grace, "expected_tool_daemon_grace_seconds": False}))

            posix = {
                **no_grace,
                "containment_kind": "POSIX_PROCESS_GROUP",
                "expected_tool_daemon_paths": [],
                "expected_tool_daemon_topology_snapshots": [],
                "expected_tool_daemon_topology_sample_elapsed_seconds": [],
                "expected_tool_daemon_topology_terminal_empty": False,
                "expected_tool_daemon_hashes_verified": False,
                "expected_tool_daemon_sha256_by_role": {},
                "expected_tool_daemon_prelaunch_hashes_verified": False,
                "expected_tool_daemon_prelaunch_sha256_by_role": {},
                "expected_tool_daemon_postexit_hashes_verified": False,
                "expected_tool_daemon_postexit_sha256_by_role": {},
            }
            self.assertEqual([], subject.process_record_errors(posix, "process", document=root / "summary.json", repo_root=root))
            self.assertIn(
                "POSIX record claims Windows helper hash verification",
                errors_for({**posix, "expected_tool_daemon_hashes_verified": True}),
            )

    def test_missing_hardware_stays_pending_and_writes_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = SyntheticEvidence(Path(temporary))
            payload, returncode = subject.summarize(fixture.root, fixture.hardware, fixture.output)
            self.assertEqual(returncode, 2)
            self.assertEqual(payload["final"]["result"], "PENDING_HW")
            self.assertEqual(payload["final"]["STATIONARY_2LANE_APPLICATION_ACCEPTANCE"], "PENDING_HW")
            self.assertEqual(payload["final"]["COMMIT"], "PENDING_FINAL_EVIDENCE_COMMIT")
            self.assertIs(payload["final"]["NETWORK_CABLE_CONNECTED"], False)
            self.assertEqual(payload["final"]["PRODUCT_FINAL_ACCEPTANCE"], "PENDING")
            self.assertEqual(payload["final"]["NEXT_RECOMMENDED_STAGE"], "EXECUTE_OR_COLLECT_SAFE_IDLE")
            self.assertEqual(payload["stages"]["stationary"]["result"], "PENDING_HW")
            for aliases in subject.ALIASES.values():
                for alias in aliases:
                    self.assertTrue((fixture.output / f"{alias}.md").is_file())
                    self.assertTrue((fixture.output / f"{alias}.json").is_file())

    def test_false_pass_without_hardware_actions_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = SyntheticEvidence(Path(temporary))
            run = fixture.hardware / "ps_application" / "functional" / "false_pass"
            run.mkdir(parents=True)
            summary = {subject.PS_MARKER: "PASS", "mode": "functional", "hardware_actions_executed": False}
            (run / "p7_ps_application_stage_summary.json").write_text(json.dumps(summary), encoding="utf-8")
            payload, returncode = subject.summarize(fixture.root, fixture.hardware, fixture.output)
            self.assertEqual(returncode, 1)
            self.assertEqual(payload["stages"]["ps_runtime"]["result"], "FAIL")
            self.assertIn("hardware_actions_executed", " ".join(payload["stages"]["ps_runtime"]["errors"]))

    def test_artifact_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = SyntheticEvidence(Path(temporary))
            fixture.make_jtag(
                "p7_safe_idle_recheck",
                [
                    "P7_SAFE_IDLE_RESULT=PASS",
                    "P7_SAFE_IDLE_TXD_IDLE=1",
                    "P7_SAFE_IDLE_SD_SHUTDOWN=1",
                    "P7_SAFE_IDLE_STUCK_HIGH_VIOLATIONS=0",
                    "P7_SAFE_IDLE_DUTY_VIOLATIONS=0",
                    "P7_SAFE_IDLE_ERROR_COUNT=0",
                ],
            )
            fixture.artifacts["bitstream"].write_bytes(b"tampered\n")
            payload, returncode = subject.summarize(fixture.root, fixture.hardware, fixture.output)
            self.assertEqual(returncode, 1)
            self.assertEqual(payload["stages"]["safe_idle"]["result"], "FAIL")
            self.assertIn("artifact:bitstream SHA256 mismatch", "\n".join(payload["stages"]["safe_idle"]["errors"]))

    def test_full_synthetic_hardware_evidence_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = SyntheticEvidence(Path(temporary))
            fixture.full_pass()
            payload, returncode = subject.summarize(fixture.root, fixture.hardware, fixture.output)
            if returncode != 0:
                self.fail(json.dumps({key: value["errors"] for key, value in payload["stages"].items() if value["result"] != "PASS"}, indent=2))
            self.assertEqual(payload["final"]["result"], "PASS")
            self.assertEqual(payload["final"]["STATIONARY_2LANE_APPLICATION_ACCEPTANCE"], "PASS")
            self.assertEqual(payload["final"]["COMMIT"], "PENDING_FINAL_EVIDENCE_COMMIT")
            self.assertEqual(payload["final"]["SOURCE_COMMIT"], COMMIT)
            self.assertEqual(payload["final"]["USER_HARDWARE_AUTHORIZATION_FOR_P7"], "GRANTED")
            self.assertIs(payload["final"]["NETWORK_CABLE_CONNECTED"], False)
            self.assertIs(payload["final"]["HARDWARE_MOVEMENT_ALLOWED"], False)
            self.assertEqual(payload["final"]["AVAILABLE_LANES"], 2)
            self.assertEqual(payload["final"]["MAX_LANE_MASK"], "0x3")
            self.assertEqual(payload["final"]["PRODUCT_FINAL_ACCEPTANCE"], "PENDING")
            self.assertEqual(payload["final"]["NEXT_RECOMMENDED_STAGE"], "FINAL_EVIDENCE_COMMIT")
            self.assertIn("evidence/generated/p7_performance_summary.md", payload["final"]["GENERATED_SUMMARIES"])
            self.assertEqual(payload["stages"]["stationary"]["metrics"]["calibration_samples"], 10)
            self.assertEqual(payload["stages"]["stationary"]["metrics"]["acceptance_samples"], 50)
            self.assertEqual(payload["stages"]["large_object_jtag"]["metrics"]["observed_required_cases"], 9)
            self.assertEqual(len(payload["stages"]["large_object_jtag"]["metrics"]["cases"]), 9)
            self.assertEqual(payload["stages"]["safe_idle"]["drove_tfdu_txd"], False)
            self.assertEqual(payload["stages"]["stationary"]["HEAD"], COMMIT)
            self.assertTrue(payload["stages"]["stationary"]["profile"])
            self.assertTrue(payload["stages"]["stationary"]["output_file_hashes"])
            final_text = (fixture.output / "p7_final_summary.md").read_text(encoding="utf-8")
            self.assertIn("PS_PL_PHY_PL_PS_APPLICATION_PASS: true", final_text)
            self.assertIn("PRODUCT_FINAL_ACCEPTANCE: PENDING", final_text)
            self.assertIn("STATIONARY_2LANE_APPLICATION_ACCEPTANCE: PASS", final_text)
            self.assertIn("COMMIT: PENDING_FINAL_EVIDENCE_COMMIT", final_text)
            self.assertIn("USER_HARDWARE_AUTHORIZATION_FOR_P7: GRANTED", final_text)
            self.assertIn("NETWORK_CABLE_CONNECTED: false", final_text)
            self.assertIn("NEXT_RECOMMENDED_STAGE: FINAL_EVIDENCE_COMMIT", final_text)
            self.assertTrue((fixture.output / "p7_performance_summary.md").is_file())
            self.assertTrue((fixture.output / "p7_performance_summary.json").is_file())
            stationary_text = (fixture.output / "p7_stationary_30min_summary.md").read_text(encoding="utf-8")
            self.assertIn("## Hardware evidence envelope", stationary_text)
            self.assertIn("### bitstream", stationary_text)
            self.assertIn(digest(fixture.artifacts["bitstream"]), stationary_text)
            self.assertTrue((fixture.output / "p7_provenance.json").is_file())
            self.assertTrue((fixture.output / "p7_application_metrics_summary.csv").is_file())
            self.assertIn(
                "application_metrics",
                (fixture.output / "p7_application_metrics_summary.csv").read_text(encoding="utf-8"),
            )
            evidence = subject.RepositoryEvidence(fixture.root, fixture.hardware, fixture.output)
            subject.discover(evidence)
            functional = next(item for item in evidence.candidates if item.kind == "ps" and item.data.get("mode") == "functional")
            functional.data["postprocess"]["cases"][0]["descriptor"]["status"] = 6
            self.assertFalse(subject._candidate_basic_pass(functional, evidence))
            stationary = next(item for item in evidence.candidates if item.kind == "ps" and item.data.get("mode") == "stationary")
            trace = stationary.data["postprocess"]["stationary_trace_validation"]
            trace_path = Path(trace["records"][0]["trace_file"]["path"])
            trace_bytes = bytearray(trace_path.read_bytes())
            trace_bytes[0:4] = b"\x00\x00\x00\x00"
            trace_path.write_bytes(trace_bytes)
            trace_errors, _latencies = subject.validate_stationary_trace_binaries(
                stationary,
                stationary.data["postprocess"],
                trace,
            )
            self.assertTrue(any("fragment count mismatch" in item or "magic mismatch" in item for item in trace_errors))

    def test_old_commit_read_only_preflight_is_a_hash_bound_zero_coverage_epoch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture, old_commit, active_commit = self._make_historical_fixture(Path(temporary))
            ledger = json.loads((fixture.hardware / "p7_run_sequence_ledger.json").read_text(encoding="utf-8"))
            historical = ledger["runs"][0]
            self.assertEqual(historical["source_commit"], old_commit)
            self.assertEqual(historical["checkpoint_relation"], subject.CHECKPOINT_RELATION_OLD_DIAGNOSTIC)
            self.assertTrue(historical["diagnostic_only"])
            self.assertFalse(historical["mutation_attempted"])
            self.assertFalse(historical["eligible_for_checkpoint_coverage"])
            self.assertEqual(historical["risk_index"], 5)
            self.assertEqual(historical["result"], "FAIL")
            self.assertEqual(historical["attempted_coverage_keys"], [])
            self.assertEqual(historical["coverage_keys"], [])
            self.assertEqual(historical["historical_epoch"]["source_commit"], old_commit)
            self.assertFalse(historical["historical_epoch"]["inner_preflight_process_tree_reaped"])
            self.assertTrue(historical["historical_epoch"]["outer_process_containment"]["process_tree_reaped"])
            self.assertEqual(historical["historical_epoch"]["effective_shutdown_recovery"]["shutdown_exit"], 0)
            self.assertEqual(len(historical["historical_epoch"]["frozen_preflight_inputs"]["files"]), 6)
            self.assertEqual(ledger["offline_checkpoint"]["source_commit"], active_commit)
            status, errors, metrics = self._validate_ledger(fixture)
            self.assertEqual(status, "PASS", "\n".join(errors))
            self.assertEqual(metrics["run_count"], ledger["run_count"])
            payload, returncode = subject.summarize(fixture.root, fixture.hardware, fixture.output)
            self.assertEqual(returncode, 0, json.dumps(payload["stages"]["consistency"], indent=2))
            self.assertEqual(payload["stages"]["consistency"]["result"], "PASS")
            self.assertEqual(payload["final"]["SOURCE_COMMIT"], active_commit)

    def test_p6_jtag_candidate_binds_axi4lite_queue_depth_sixteen(self) -> None:
        build_tcl = (ROOT / "scripts/build_p6_jtag_candidate.tcl").read_text(encoding="utf-8")
        inspect_tcl = (ROOT / "scripts/vivado_inspect_p6_ip.tcl").read_text(encoding="utf-8")
        properties = (ROOT / "evidence/generated/vivado/p6_ip_inspect/jtag_axi_properties.txt").read_text(encoding="utf-8")
        summary = json.loads(
            (ROOT / "evidence/generated/vivado/p6_jtag_candidate/p6_jtag_candidate_build_summary.json").read_text(
                encoding="utf-8"
            )
        )
        for text in (build_tcl, inspect_tcl):
            self.assertIn("CONFIG.RD_TXN_QUEUE_LENGTH {16}", text)
            self.assertIn("CONFIG.WR_TXN_QUEUE_LENGTH {16}", text)
        self.assertIn("CONFIG.RD_TXN_QUEUE_LENGTH=16", properties)
        self.assertIn("CONFIG.WR_TXN_QUEUE_LENGTH=16", properties)
        self.assertEqual("PASS", summary["P6_JTAG_CANDIDATE_BUILD"])
        self.assertTrue(summary["timing_met"])
        self.assertTrue(summary["drc_clean"])
        self.assertEqual(
            {
                "protocol": "AXI4-Lite",
                "read_transaction_queue_length": 16,
                "write_transaction_queue_length": 16,
                "transaction_len_words": 1,
            },
            summary["jtag_axi_config"],
        )
        for artifact in summary["artifacts"].values():
            immutable = ROOT / artifact["immutable"]
            self.assertTrue(immutable.is_file())
            self.assertEqual(artifact["sha256"], subject.sha256_file(immutable))

    def test_real_r1_through_r12_epochs_validate_and_failed_stage_tamper_fails_closed(self) -> None:
        evidence = subject.RepositoryEvidence(
            ROOT,
            ROOT / "evidence" / "hardware" / "p7",
            ROOT / "evidence" / "generated",
        )
        epoch_names = (
            "p7_20260711_stationary_app",
            "p7_20260711_stationary_app_r2",
            "p7_20260711_stationary_app_r3",
            "p7_20260711_stationary_app_r4",
            "p7_20260711_stationary_app_r5",
            "p7_20260711_stationary_app_r6",
            "p7_20260711_stationary_app_r7",
            "p7_20260711_stationary_app_r8",
            "p7_20260711_stationary_app_r9",
            "p7_20260711_stationary_app_r10_diag_suffix55",
            "p7_20260711_stationary_app_r11_diag_suffix55",
            "p7_20260711_stationary_app_r12_diag_suffix55",
        )
        candidates: dict[str, subject.Candidate] = {}
        for epoch_name in epoch_names:
            stage_directory = (
                "058_p7_large_jtag_1m_l0_random"
                if epoch_name.endswith("_r10_diag_suffix55")
                else "002_p7_p6_frame_regression_m1"
                if epoch_name.endswith(("_r11_diag_suffix55", "_r12_diag_suffix55"))
                else "003_p7_p6_frame_regression_m2"
                if epoch_name.endswith("_r9")
                else
                "055_p7_large_jtag_64k_rr_prbs15"
                if epoch_name.endswith("_r8")
                else "003_p7_p6_frame_regression_m2"
                if epoch_name.endswith("_r7")
                else "028_p7_fragment_boundary_216_rep3"
                if epoch_name.endswith("_r6")
                else "002_p7_p6_frame_regression_m1"
                if epoch_name.endswith("_r5")
                else "001_p7_safe_idle"
            )
            summary_path = (
                evidence.hardware_root
                / "authorized_sequence"
                / epoch_name
                / stage_directory
                / "p7_jtag_axi_stage_summary.json"
            )
            self.assertTrue(summary_path.is_file(), f"missing immutable historical epoch: {epoch_name}")
            data = json.loads(summary_path.read_text(encoding="utf-8"))
            candidate = subject.Candidate(
                summary_path,
                data,
                "jtag",
                subject.classify_jtag_stage(data),
                subject.parse_time(data.get("generated_at_utc"), summary_path.stat().st_mtime),
            )
            candidates[epoch_name] = candidate
            if epoch_name.endswith("_r10_diag_suffix55"):
                inner_errors = subject._old_commit_1m_jtag_timeout_errors(candidate, evidence)
            elif epoch_name.endswith("_r11_diag_suffix55"):
                inner_errors = subject._old_commit_axi4lite_burst_failure_errors(candidate, evidence)
            elif epoch_name.endswith("_r12_diag_suffix55"):
                inner_errors = subject._old_commit_jtag_axi_queue_depth_failure_errors(candidate, evidence)
            elif epoch_name.endswith("_r9"):
                inner_errors = subject._old_commit_outer_deadline_abort_errors(candidate, evidence)
            elif epoch_name.endswith("_r8"):
                inner_errors = subject._old_commit_backend_retry_failure_errors(candidate, evidence)
            elif epoch_name.endswith("_r7"):
                inner_errors = subject._old_commit_shutdown_timeout_failure_errors(candidate, evidence)
            elif epoch_name.endswith("_r6"):
                inner_errors = subject._old_commit_shutdown_helper_exit_race_failure_errors(candidate, evidence)
            elif epoch_name.endswith("_r5"):
                inner_errors = subject._old_commit_backend_raw_pulse_failure_errors(candidate, evidence)
            elif epoch_name.endswith("_r4"):
                inner_errors = subject._old_commit_write_allowlist_failure_errors(candidate, evidence)
            elif epoch_name.endswith("_r3"):
                inner_errors = subject._old_commit_shutdown_tcl_failure_errors(candidate, evidence)
            else:
                inner_errors = subject._old_commit_read_only_preflight_errors(candidate, evidence)
            epoch, epoch_errors = subject._historical_epoch_record(candidate, evidence)
            self.assertEqual([], inner_errors, f"{epoch_name}: {inner_errors}")
            self.assertEqual([], epoch_errors, f"{epoch_name}: {epoch_errors}")
            self.assertEqual([], epoch["coverage_keys"])
            self.assertEqual("FAIL", epoch["result"])

        discovered = subject.RepositoryEvidence(
            ROOT,
            ROOT / "evidence" / "hardware" / "p7",
            ROOT / "evidence" / "generated",
        )
        subject.discover(discovered)
        collapsed = subject._collapse_historical_epoch_candidates(
            [item for item in discovered.candidates if subject.candidate_has_hardware_footprint(item)],
            "f" * 40,
        )
        for epoch_name in (
            "p7_20260711_stationary_app_r11_diag_suffix55",
            "p7_20260711_stationary_app_r12_diag_suffix55",
        ):
            epoch_candidates = [
                item
                for item in collapsed
                if item.path.parent.parent.name == epoch_name
            ]
            self.assertEqual(1, len(epoch_candidates), epoch_name)
            self.assertEqual(
                "002_p7_p6_frame_regression_m1",
                epoch_candidates[0].path.parent.name,
            )

        r5_source = subject._candidate_source_commit(candidates["p7_20260711_stationary_app_r5"])
        r5_prefix_path = (
            evidence.hardware_root
            / "authorized_sequence"
            / "p7_20260711_stationary_app_r5"
            / "001_p7_safe_idle"
            / "p7_jtag_axi_stage_summary.json"
        )
        r5_prefix_data = json.loads(r5_prefix_path.read_text(encoding="utf-8"))
        r5_prefix = subject.Candidate(
            r5_prefix_path,
            r5_prefix_data,
            "jtag",
            subject.classify_jtag_stage(r5_prefix_data),
            subject.parse_time(r5_prefix_data.get("generated_at_utc"), r5_prefix_path.stat().st_mtime),
        )
        active_errors, _ = subject.common_runner_errors(r5_prefix, evidence)
        self.assertIn("hardware source commit does not match current repository HEAD", active_errors)
        historical_errors, _ = subject.common_runner_errors(
            r5_prefix,
            evidence,
            accepted_historical_source=r5_source,
        )
        self.assertEqual([], historical_errors)
        mismatched_errors, _ = subject.common_runner_errors(
            r5_prefix,
            evidence,
            accepted_historical_source="0" * 40,
        )
        self.assertIn("hardware source commit does not match accepted historical source", mismatched_errors)

        r3 = candidates["p7_20260711_stationary_app_r3"]
        tamper_cases = (
            ("candidate programming", lambda data: data.__setitem__("programmed_candidate", True)),
            (
                "shutdown return code",
                lambda data: data["shutdown_after"].__setitem__("returncode", 0),
            ),
            (
                "post-fix provenance field",
                lambda data: data["shutdown_after"].__setitem__("programming_attempted", True),
            ),
            (
                "candidate child",
                lambda data: data.__setitem__("stage_process", {"returncode": 0}),
            ),
        )
        for label, mutate in tamper_cases:
            tampered_data = json.loads(json.dumps(r3.data))
            mutate(tampered_data)
            tampered = subject.Candidate(
                r3.path,
                tampered_data,
                r3.kind,
                r3.stage,
                r3.timestamp,
            )
            errors = subject._old_commit_shutdown_tcl_failure_errors(tampered, evidence)
            self.assertTrue(errors, f"r3 {label} tamper unexpectedly validated")

        r4 = candidates["p7_20260711_stationary_app_r4"]
        r4_tamper_cases = (
            ("candidate programming", lambda data: data.__setitem__("programmed_candidate", False)),
            ("candidate return code", lambda data: data["stage_process"].__setitem__("returncode", 0)),
            ("TFDU drive", lambda data: data.__setitem__("drove_tfdu_txd", True)),
            ("shutdown-after PASS", lambda data: data["shutdown_after"].__setitem__("passed", False)),
            ("candidate reap", lambda data: data.__setitem__("child_reaped_before_shutdown_after", False)),
        )
        for label, mutate in r4_tamper_cases:
            tampered_data = json.loads(json.dumps(r4.data))
            mutate(tampered_data)
            tampered = subject.Candidate(
                r4.path,
                tampered_data,
                r4.kind,
                r4.stage,
                r4.timestamp,
            )
            errors = subject._old_commit_write_allowlist_failure_errors(tampered, evidence)
            self.assertTrue(errors, f"r4 {label} tamper unexpectedly validated")

        r5 = candidates["p7_20260711_stationary_app_r5"]
        r5_tamper_cases = (
            ("backend failure", lambda data: data.__setitem__("backend_parse_failure", "")),
            ("inner stage return code", lambda data: data["stage_process"].__setitem__("returncode", 1)),
            ("TX footprint", lambda data: data.__setitem__("drove_tfdu_txd", False)),
            ("shutdown-after PASS", lambda data: data["shutdown_after"].__setitem__("passed", False)),
            ("stationary status", lambda data: data.__setitem__("hardware_acceptance", "PASS")),
        )
        for label, mutate in r5_tamper_cases:
            tampered_data = json.loads(json.dumps(r5.data))
            mutate(tampered_data)
            tampered = subject.Candidate(
                r5.path,
                tampered_data,
                r5.kind,
                r5.stage,
                r5.timestamp,
            )
            errors = subject._old_commit_backend_raw_pulse_failure_errors(tampered, evidence)
            self.assertTrue(errors, f"r5 {label} tamper unexpectedly validated")

        r6 = candidates["p7_20260711_stationary_app_r6"]
        r6_tamper_cases = (
            ("candidate result", lambda data: data["stage_process"].__setitem__("passed", False)),
            ("shutdown return code", lambda data: data["shutdown_after"].__setitem__("returncode", 0)),
            ("forced cleanup", lambda data: data["shutdown_after"].__setitem__("containment_cleanup_terminated", False)),
            ("exit-race query", lambda data: data["shutdown_after"].__setitem__("containment_query_error", "")),
            ("shutdown promotion", lambda data: data.__setitem__("programmed_shutdown_after", True)),
        )
        for label, mutate in r6_tamper_cases:
            tampered_data = json.loads(json.dumps(r6.data))
            mutate(tampered_data)
            tampered = subject.Candidate(
                r6.path,
                tampered_data,
                r6.kind,
                r6.stage,
                r6.timestamp,
            )
            errors = subject._old_commit_shutdown_helper_exit_race_failure_errors(tampered, evidence)
            self.assertTrue(errors, f"r6 {label} tamper unexpectedly validated")

        r7 = candidates["p7_20260711_stationary_app_r7"]
        r7_tamper_cases = (
            ("candidate result", lambda data: data["stage_process"].__setitem__("passed", False)),
            ("shutdown return code", lambda data: data["shutdown_after"].__setitem__("returncode", 0)),
            ("timeout fact", lambda data: data["shutdown_after"].__setitem__("timed_out", False)),
            ("programming promotion", lambda data: data["shutdown_after"].__setitem__("programming_attempted", True)),
            ("shutdown promotion", lambda data: data.__setitem__("programmed_shutdown_after", True)),
        )
        for label, mutate in r7_tamper_cases:
            tampered_data = json.loads(json.dumps(r7.data))
            mutate(tampered_data)
            tampered = subject.Candidate(
                r7.path,
                tampered_data,
                r7.kind,
                r7.stage,
                r7.timestamp,
            )
            errors = subject._old_commit_shutdown_timeout_failure_errors(tampered, evidence)
            self.assertTrue(errors, f"r7 {label} tamper unexpectedly validated")

        r8 = candidates["p7_20260711_stationary_app_r8"]
        r8_tamper_cases = (
            ("backend failure", lambda data: data.__setitem__("backend_parse_failure", "")),
            ("candidate result", lambda data: data["stage_process"].__setitem__("passed", False)),
            ("transaction count", lambda data: data["transaction_validation"].__setitem__("operation_count", 1)),
            ("shutdown-after", lambda data: data["shutdown_after"].__setitem__("passed", False)),
            ("hardware promotion", lambda data: data.__setitem__("hardware_acceptance", "PASS")),
        )
        for label, mutate in r8_tamper_cases:
            tampered_data = json.loads(json.dumps(r8.data))
            mutate(tampered_data)
            tampered = subject.Candidate(r8.path, tampered_data, r8.kind, r8.stage, r8.timestamp)
            errors = subject._old_commit_backend_retry_failure_errors(tampered, evidence)
            self.assertTrue(errors, f"r8 {label} tamper unexpectedly validated")

        r9 = candidates["p7_20260711_stationary_app_r9"]
        r9_tamper_cases = (
            ("abort fact", lambda data: data["stage_process"].__setitem__("abort_seen", False)),
            ("candidate return code", lambda data: data["stage_process"].__setitem__("returncode", 0)),
            ("candidate programming", lambda data: data.__setitem__("programmed_candidate", True)),
            ("shutdown-after", lambda data: data["shutdown_after"].__setitem__("passed", False)),
            ("hardware promotion", lambda data: data.__setitem__("hardware_acceptance", "PASS")),
        )
        for label, mutate in r9_tamper_cases:
            tampered_data = json.loads(json.dumps(r9.data))
            mutate(tampered_data)
            tampered = subject.Candidate(r9.path, tampered_data, r9.kind, r9.stage, r9.timestamp)
            errors = subject._old_commit_outer_deadline_abort_errors(tampered, evidence)
            self.assertTrue(errors, f"r9 {label} tamper unexpectedly validated")

        r10 = candidates["p7_20260711_stationary_app_r10_diag_suffix55"]
        r10_tamper_cases = (
            ("timeout fact", lambda data: data["stage_process"].__setitem__("timed_out", False)),
            ("candidate return code", lambda data: data["stage_process"].__setitem__("returncode", 0)),
            ("candidate programming", lambda data: data.__setitem__("programmed_candidate", False)),
            ("shutdown-after", lambda data: data["shutdown_after"].__setitem__("passed", False)),
            ("hardware promotion", lambda data: data.__setitem__("hardware_acceptance", "PASS")),
        )
        for label, mutate in r10_tamper_cases:
            tampered_data = json.loads(json.dumps(r10.data))
            mutate(tampered_data)
            tampered = subject.Candidate(r10.path, tampered_data, r10.kind, r10.stage, r10.timestamp)
            errors = subject._old_commit_1m_jtag_timeout_errors(tampered, evidence)
            self.assertTrue(errors, f"r10 {label} tamper unexpectedly validated")

        r11 = candidates["p7_20260711_stationary_app_r11_diag_suffix55"]
        r11_tamper_cases = (
            ("candidate return code", lambda data: data["stage_process"].__setitem__("returncode", 0)),
            ("burst groups", lambda data: data["transaction_validation"].__setitem__("burst_group_count", 0)),
            ("candidate programming", lambda data: data.__setitem__("programmed_candidate", False)),
            ("shutdown-after", lambda data: data["shutdown_after"].__setitem__("passed", False)),
            ("hardware promotion", lambda data: data.__setitem__("hardware_acceptance", "PASS")),
        )
        for label, mutate in r11_tamper_cases:
            tampered_data = json.loads(json.dumps(r11.data))
            mutate(tampered_data)
            tampered = subject.Candidate(r11.path, tampered_data, r11.kind, r11.stage, r11.timestamp)
            errors = subject._old_commit_axi4lite_burst_failure_errors(tampered, evidence)
            self.assertTrue(errors, f"r11 {label} tamper unexpectedly validated")

        r12 = candidates["p7_20260711_stationary_app_r12_diag_suffix55"]
        r12_tamper_cases = (
            ("candidate return code", lambda data: data["stage_process"].__setitem__("returncode", 0)),
            ("queue batch count", lambda data: data["transaction_validation"].__setitem__("multi_transaction_batch_count", 0)),
            ("candidate programming", lambda data: data.__setitem__("programmed_candidate", False)),
            ("shutdown-after", lambda data: data["shutdown_after"].__setitem__("passed", False)),
            ("hardware promotion", lambda data: data.__setitem__("hardware_acceptance", "PASS")),
        )
        for label, mutate in r12_tamper_cases:
            tampered_data = json.loads(json.dumps(r12.data))
            mutate(tampered_data)
            tampered = subject.Candidate(r12.path, tampered_data, r12.kind, r12.stage, r12.timestamp)
            errors = subject._old_commit_jtag_axi_queue_depth_failure_errors(tampered, evidence)
            self.assertTrue(errors, f"r12 {label} tamper unexpectedly validated")

    def test_two_historical_preflight_epochs_are_ordered_and_never_cover_safe_idle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture, r1_commit, r2_commit, active_commit = self._make_multi_historical_fixture(Path(temporary))
            ledger_path = fixture.hardware / "p7_run_sequence_ledger.json"
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            historical = [
                run
                for run in ledger["runs"]
                if run["checkpoint_relation"] == subject.CHECKPOINT_RELATION_OLD_DIAGNOSTIC
            ]
            self.assertEqual(ledger["precheckpoint_read_only_diagnostic_count"], 2)
            self.assertEqual([run["source_commit"] for run in historical], [r1_commit, r2_commit])
            self.assertEqual(
                [run["historical_epoch"]["preflight_failure_class"] for run in historical],
                [
                    subject.HISTORICAL_PREFLIGHT_PART_IDENTITY_REJECTED,
                    subject.HISTORICAL_PREFLIGHT_IDENTITY_PASS_HELPER_CONTAINMENT_REJECTED,
                ],
            )
            for run in historical:
                self.assertEqual(run["risk_index"], 5)
                self.assertEqual(run["result"], "FAIL")
                self.assertFalse(run["mutation_attempted"])
                self.assertFalse(run["eligible_for_checkpoint_coverage"])
                self.assertEqual(run["attempted_coverage_keys"], [])
                self.assertEqual(run["coverage_keys"], [])
            r2_epoch = historical[1]["historical_epoch"]
            self.assertEqual(r2_epoch["read_only_target_identity"]["P7_HW_PREFLIGHT_RESULT"], "PASS")
            self.assertEqual(r2_epoch["read_only_target_identity"]["P7_HW_PREFLIGHT_CANONICAL_PART"], PART)
            self.assertEqual(r2_epoch["read_only_target_identity"]["P7_HW_PREFLIGHT_LIVE_PART"], subject.CANONICAL_LIVE_PART)
            self.assertEqual(r2_epoch["read_only_target_identity"]["P7_HW_PREFLIGHT_LIVE_DEVICE"], subject.CANONICAL_LIVE_DEVICE)
            self.assertEqual(r2_epoch["read_only_target_identity"]["P7_HW_PREFLIGHT_LIVE_IDCODE"], subject.CANONICAL_LIVE_IDCODE_BINARY)
            self.assertEqual(r2_epoch["inner_preflight_containment"]["returncode"], 125)
            self.assertTrue(r2_epoch["inner_preflight_containment"]["process_tree_terminated"])
            self.assertFalse(r2_epoch["inner_preflight_containment"]["process_tree_reaped"])
            self.assertEqual(r2_epoch["inner_preflight_containment"]["expected_tool_daemon_classification"], "UNAPPROVED")
            self.assertEqual(len(r2_epoch["inner_preflight_containment"]["descendant_processes_seen"]), 6)
            self.assertTrue(r2_epoch["outer_process_containment"]["process_tree_reaped"])
            self.assertEqual(r2_epoch["effective_shutdown_recovery"]["shutdown_exit"], 0)
            self.assertEqual(r2_epoch["effective_shutdown_recovery"]["observed_raw_exit"], 125)
            safe_idle_coverage = [run for run in ledger["runs"] if "safe_idle" in run["coverage_keys"]]
            self.assertEqual(len(safe_idle_coverage), 1)
            self.assertEqual(safe_idle_coverage[0]["source_commit"], active_commit)
            status, errors, _metrics = self._validate_ledger(fixture)
            self.assertEqual(status, "PASS", "\n".join(errors))

    def test_r2_historical_epoch_tamper_recovery_order_and_nonancestor_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture, r1_commit, _r2_commit, _active_commit = self._make_multi_historical_fixture(Path(temporary))
            r1_epoch = fixture.hardware / "authorized_sequence/historical_epoch_r1"
            r2_epoch = fixture.hardware / "authorized_sequence/historical_epoch_r2"

            def assert_tamper_fails(path: Path, mutate, expected: str) -> None:
                original = path.read_bytes()
                try:
                    mutate(path)
                    status, errors, _metrics = self._validate_ledger(fixture)
                    self.assertEqual(status, "FAIL")
                    self.assertIn(expected, "\n".join(errors))
                finally:
                    path.write_bytes(original)

            r2_summary = r2_epoch / "001_p7_safe_idle/p7_jtag_axi_stage_summary.json"

            def tamper_helper_topology(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["preflight_process"]["descendant_processes_seen"][2]["parent_pid"] = 9999
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(r2_summary, tamper_helper_topology, "historical r2 cs_server pair is not a direct parent-child topology")

            def tamper_duplicate_root_parent(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                processes = value["preflight_process"]["descendant_processes_seen"]
                processes[3]["parent_pid"] = processes[1]["parent_pid"]
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(
                r2_summary,
                tamper_duplicate_root_parent,
                "historical r2 helper forest root parent PIDs are not positive/distinct",
            )

            def tamper_identity(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["target_identity"]["P7_HW_PREFLIGHT_LIVE_PART"] = "xc7z020"
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(r2_summary, tamper_identity, "historical r2 raw/summary exact identity records differ")

            def tamper_candidate_started(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["stage_process"] = {"returncode": 0}
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(r2_summary, tamper_candidate_started, "old-commit diagnostic contains a candidate child process")

            outer = r2_epoch / "sequence_execution_ledger.json"

            def tamper_outer_containment(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["attempts"][0]["process"]["process_tree_reaped"] = False
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(outer, tamper_outer_containment, "historical r2 outer process did not reap the inner wrapper tree")

            frozen_checkpoint = next((r2_epoch / "historical_preflight_inputs").glob("offline_checkpoint.json"))

            def tamper_frozen_checkpoint(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["source_commit"] = "0" * 40
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(frozen_checkpoint, tamper_frozen_checkpoint, "historical frozen offline checkpoint source mismatch")

            recovery_summary = next(r2_epoch.glob("recovery_shutdown_after_failed_preflight_*/program_tfdu_shutdown_safe.summary.txt"))

            def tamper_recovery(path: Path) -> None:
                path.write_text(path.read_text(encoding="utf-8").replace("SHUTDOWN_EXIT=0", "SHUTDOWN_EXIT=9"), encoding="utf-8")

            assert_tamper_fails(recovery_summary, tamper_recovery, "historical effective recovery lacks SHUTDOWN_EXIT=0")

            def tamper_recovery_raw_exit(path: Path) -> None:
                path.write_text(path.read_text(encoding="utf-8").replace("SHUTDOWN_RAW_EXIT=125", "SHUTDOWN_RAW_EXIT=0"), encoding="utf-8")

            assert_tamper_fails(
                recovery_summary,
                tamper_recovery_raw_exit,
                "historical r2 recovery does not prove normalized raw rc125 with SHUTDOWN_EXIT=0",
            )

            r1_recovery = sorted(r1_epoch.glob("recovery_shutdown_after_failed_preflight_*/program_tfdu_shutdown_safe.summary.txt"))[-1]

            def tamper_epoch_order(path: Path) -> None:
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "PROGRAM_TFDU_SHUTDOWN_SAFE_END 2026-07-10T00:14:00+00:00",
                        "PROGRAM_TFDU_SHUTDOWN_SAFE_END 2026-07-10T00:40:00+00:00",
                    ),
                    encoding="utf-8",
                )

            assert_tamper_fails(r1_recovery, tamper_epoch_order, "historical epoch order 0->1 overlaps or regresses")

            tree = self._git(fixture.root, "rev-parse", f"{r1_commit}^{{tree}}")
            orphan = subprocess.run(
                ["git", "commit-tree", tree],
                cwd=fixture.root,
                input="unrelated r2 source\n",
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            evidence = subject.RepositoryEvidence(fixture.root, fixture.hardware, fixture.output)
            ancestry_errors = subject._historical_epoch_order_errors(
                [
                    {"source_commit": r1_commit, "started_at_utc": "2026-07-10T00:00:00+00:00", "ended_at_utc": "2026-07-10T00:01:00+00:00"},
                    {"source_commit": orphan, "started_at_utc": "2026-07-10T00:02:00+00:00", "ended_at_utc": "2026-07-10T00:03:00+00:00"},
                ],
                evidence,
            )
            self.assertIn("historical source order 0->1", "\n".join(ancestry_errors))
            self.assertIn("not an ancestor", "\n".join(ancestry_errors))

    def test_historical_epoch_tamper_and_nonancestor_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture, old_commit, active_commit = self._make_historical_fixture(Path(temporary))
            epoch = fixture.hardware / "authorized_sequence/historical_epoch"

            def assert_tamper_fails(path: Path, mutate, expected: str) -> None:
                original = path.read_bytes()
                try:
                    mutate(path)
                    status, errors, _metrics = self._validate_ledger(fixture)
                    self.assertEqual(status, "FAIL")
                    self.assertIn(expected, "\n".join(errors))
                finally:
                    path.write_bytes(original)

            frozen_manifest = epoch / "historical_preflight_inputs/manifest.json"

            def tamper_role(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["files"][0]["role"] = "invented_role"
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(frozen_manifest, tamper_role, "historical preflight input role")

            def tamper_run_id(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["run_id"] = "different_epoch"
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(frozen_manifest, tamper_run_id, "run_id does not match epoch root")

            def tamper_original_path(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["files"][0]["original_path"] = "unrelated/offline.json"
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(frozen_manifest, tamper_original_path, "original_path does not bind recorded offline_checkpoint path")

            frozen_checkpoint = epoch / "historical_preflight_inputs/offline_checkpoint.json"

            def tamper_old_blob_hash(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["checkpoint_input_hashes"][subject.HISTORICAL_GIT_CRITICAL_SOURCES[0]] = "0" * 64
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(frozen_checkpoint, tamper_old_blob_hash, "historical old checkpoint Git blob hash mismatch")

            frozen_plan = epoch / "historical_preflight_inputs/sequence_plan.txt"

            def tamper_plan_command(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["stages"][0]["command"][0] = "different-executor"
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(frozen_plan, tamper_plan_command, "historical frozen sequence plan command does not bind outer attempt")

            frozen_generation = epoch / "historical_preflight_inputs/generation_manifest.json"

            def tamper_generation_binding(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["sequence_plan"]["sha256"] = "f" * 64
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(frozen_generation, tamper_generation_binding, "historical frozen generation manifest sequence-plan SHA mismatch")

            outer = epoch / "sequence_execution_ledger.json"

            def tamper_outer_containment(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["attempts"][0]["process"]["process_tree_reaped"] = False
                path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

            assert_tamper_fails(outer, tamper_outer_containment, "historical outer sequence process was not reaped")

            effective = epoch / "recovery_shutdown_after_failed_preflight_20260710T0013"
            recovery_auth = effective / "hardware_authorization.json"

            def tamper_recovery_auth(path: Path) -> None:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["BOARD_ID"] = "wrong-board"
                path.write_text(json.dumps(value) + "\n", encoding="utf-8")

            assert_tamper_fails(recovery_auth, tamper_recovery_auth, "historical recovery authorization board mismatch")

            recovery_stdout = effective / "program_tfdu_shutdown_safe.stdout.log"

            def tamper_target(path: Path) -> None:
                path.write_text(path.read_text(encoding="utf-8").replace(TARGET, "wrong-target"), encoding="utf-8")

            assert_tamper_fails(recovery_stdout, tamper_target, "historical effective recovery stdout target identity")

            recovery_summary = effective / "program_tfdu_shutdown_safe.summary.txt"

            def tamper_marker(path: Path) -> None:
                path.write_text(path.read_text(encoding="utf-8").replace("SHUTDOWN_EXIT=0", "SHUTDOWN_EXIT=9"), encoding="utf-8")

            assert_tamper_fails(recovery_summary, tamper_marker, "historical effective recovery lacks SHUTDOWN_EXIT=0")

            def tamper_chronology(path: Path) -> None:
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "PROGRAM_TFDU_SHUTDOWN_SAFE_END 2026-07-10T00:14:00+00:00",
                        "PROGRAM_TFDU_SHUTDOWN_SAFE_END 2026-07-10T02:14:00+00:00",
                    ),
                    encoding="utf-8",
                )

            assert_tamper_fails(recovery_summary, tamper_chronology, "superseded diagnostic/recovery epoch did not finish before")

            tree = self._git(fixture.root, "rev-parse", f"{old_commit}^{{tree}}")
            orphan = subprocess.run(
                ["git", "commit-tree", tree],
                cwd=fixture.root,
                input="unrelated source\n",
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            ancestry_errors = subject._git_source_ancestry_errors(
                subject.RepositoryEvidence(fixture.root, fixture.hardware, fixture.output),
                old_commit=orphan,
                active_commit=active_commit,
            )
            self.assertIn("not an ancestor", "\n".join(ancestry_errors))

    def test_failed_stationary_launch_intent_must_still_be_final(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = SyntheticEvidence(Path(temporary))
            fixture.full_pass()
            ledger_path = fixture.hardware / "p7_run_sequence_ledger.json"
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            duplicate = dict(ledger["runs"][0])
            duplicate["sequence"] = len(ledger["runs"]) + 1
            ledger["runs"].append(duplicate)
            ledger["run_count"] = len(ledger["runs"])
            ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
            status, errors, _metrics = self._validate_ledger(fixture)
            self.assertEqual(status, "FAIL")
            self.assertIn("stationary launch intent is not the final executed hardware stage", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
