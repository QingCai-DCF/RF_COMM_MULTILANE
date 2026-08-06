#!/usr/bin/env python3
"""Bounded P10.4 F2/R2 bidirectional raw-connectivity retest.

This runner is intentionally narrower than the P10.4 campaign.  It uses the
frozen P10.4 bitstreams/ELFs, lane mask 0x4, and exactly 64 then 1024 raw
pulses in each physical direction.  It is inert unless an exact committed
current-run authorization and both hardware environment gates are present.

require-user-hw-authorization
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import run_p10_3_ax7020_4lane_hardware as base
import run_p10_3_lane2_raw_retest as raw
import run_p10_4_hardware as p104


ROOT = p104.ROOT
BRANCH = "p10.4/autonomous-4lane-hardening"
SCOPE = (
    "P10_4_AUTONOMOUS_4LANE_PERFORMANCE_ROBUSTNESS_AND_2PLUS2_EXPERIMENT/"
    "LANE2_RAW_CONNECTIVITY_RETEST"
)
AUTH = ROOT / "config/p10_4_lane2_raw_retest_current_run_authorization.json"
BLOCKER = ROOT / "evidence/generated/p10_4_f2_to_r2_directional_blocker.json"
HW_ROOT = ROOT / "evidence/hardware/p10_4_raw_connectivity"
GENERATED = ROOT / "evidence/generated/p10_4_lane2_raw_connectivity_retest"
REPORTS = ROOT / "reports"
RUN_RE = re.compile(
    r"^p10_4_l2raw_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}_"
    r"[0-9a-f]{8}_[0-9a-f]{8}$"
)
AUTHORIZATION_ID = "P10_4-LANE2-RAW-RETEST-CURRENT-RUN-IMMUTABLE"
USER_STATEMENT = "重新测试一下F2-R2 连通性"
TRIGGER = (
    "The user explicitly requested a fresh F2/R2 connectivity retest after "
    "the prior P10.4 F2-to-R2 directional blocker."
)
LANE = 2
LANE_MASK = 0x4
DIRECTIONS = ("f2_to_r2", "r2_to_f2")
STAGE_TIMEOUT_SECONDS = 300
MAXIMUM_ACTIVE_RUNTIME_SECONDS = 600
MAXIMUM_WRAPPER_RUNTIME_SECONDS = 900
TCL_STAGE = "P10_4-BASELINE_SMOKE"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def configure_raw_helpers() -> None:
    """Bind the proven raw evaluator to the P10.4 artifact identity."""
    raw.configure_lane(LANE)
    raw.AUTH = AUTH
    raw.PREVIOUS_BLOCKER = BLOCKER
    raw.OUTPUT_STEM = "p10_4_lane2_raw_connectivity_retest"
    raw.SCOPE = SCOPE
    raw.TCL_STAGE = TCL_STAGE
    raw.TITLE = "F2/R2 bidirectional raw-connectivity retest"
    raw.TRIGGER = TRIGGER
    raw.USER_STATEMENT = USER_STATEMENT
    raw.AUTHORIZATION_ID = AUTHORIZATION_ID
    raw.RUN_RE = RUN_RE
    raw.STAGE_TIMEOUT_SECONDS = STAGE_TIMEOUT_SECONDS
    raw.MAXIMUM_ACTIVE_RUNTIME_SECONDS = MAXIMUM_ACTIVE_RUNTIME_SECONDS
    raw.MAXIMUM_WRAPPER_RUNTIME_SECONDS = MAXIMUM_WRAPPER_RUNTIME_SECONDS

    # The raw parser and safety checks are shared with P10.3, but build and
    # register identities must be the exact frozen P10.4 values.
    raw.p103.GOAL = p104.GOAL
    raw.p103.GOAL_SHA256 = p104.GOAL_SHA256
    raw.p103.FREEZE = p104.FREEZE
    raw.p103.BRANCH = BRANCH
    raw.p103.SCOPE = SCOPE
    raw.p103.EXPECTED_PL_BUILD = dict(p104.EXPECTED_BUILD)
    expected_role = deepcopy(raw.p103.EXPECTED_ROLE)
    for role in ("fixed", "rotating"):
        expected_role[role]["firmware"] = p104.EXPECTED_BUILD[role]
        expected_role[role]["build"] = p104.EXPECTED_BUILD[role]
    raw.p103.EXPECTED_ROLE = expected_role


def auth_input_paths() -> tuple[Path, ...]:
    return (
        p104.GOAL,
        p104.FREEZE,
        BLOCKER,
        ROOT / "PROJECT_CONSTRAINTS.txt",
        ROOT / "AGENTS.md",
        ROOT / "config/register_map/ir_axi_regs.yaml",
        base.WIRING,
        base.INVENTORY,
        ROOT / "config/hardware/p10_2_ax7020_4lane_wiring.yaml",
        ROOT / "board_profiles/ax7020_fixed_4lane/profile.yaml",
        ROOT / "board_profiles/ax7020_rotating_4lane/profile.yaml",
        ROOT / "board_profiles/ax7020_fixed_4lane/ax7020_fixed_4lane.generated.xdc",
        ROOT / "board_profiles/ax7020_rotating_4lane/ax7020_rotating_4lane.generated.xdc",
        ROOT / "scripts/hw/p10_program_dual_shutdown.tcl",
        p104.STAGE_TCL,
        p104.FORENSIC_TCL,
        ROOT / "scripts/p10_hardware_runtime.py",
        ROOT / "scripts/run_p10_3_ax7020_4lane_hardware.py",
        ROOT / "scripts/run_p10_3_lane2_raw_retest.py",
        ROOT / "scripts/run_p10_4_hardware.py",
        Path(__file__).resolve(),
    )


def expected_inputs() -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for path in auth_input_paths():
        if not path.is_file():
            raise FileNotFoundError(path)
        output[p104.rel(path)] = {
            "sha256": p104.sha256(path),
            "bytes": path.stat().st_size,
        }
    return output


def validate_static_inputs() -> tuple[dict[str, Any], dict[str, Path], list[str]]:
    configure_raw_helpers()
    errors: list[str] = []
    try:
        freeze = p104.load_json(p104.FREEZE)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, {}, [f"P10.4 freeze unreadable: {exc}"]
    if p104.sha256(p104.GOAL) != p104.GOAL_SHA256:
        errors.append("P10.4 Goal SHA256 mismatch")
    if freeze.get("status") != "PASS" or freeze.get("acceptance_eligible") is not True:
        errors.append("P10.4 artifact freeze is not acceptance eligible")
    if freeze.get("source_commit") != "6ff17d33a0ea111fbd796899c49decbfa339e2c1":
        errors.append("unexpected P10.4 artifact source commit")
    try:
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", str(freeze["source_commit"]), "HEAD"],
            cwd=ROOT,
            check=False,
        ).returncode != 0:
            errors.append("P10.4 artifact source commit is not an ancestor of HEAD")
    except (KeyError, OSError):
        errors.append("P10.4 artifact source ancestry cannot be verified")

    artifacts: dict[str, Path] = {}
    entries = {
        p104.artifact_key(item): item
        for item in freeze.get("artifacts", [])
        if isinstance(item, dict)
    }
    required = {
        f"{role}:{kind}"
        for role in ("fixed", "rotating")
        for kind in ("shutdown_bitstream", "functional_bitstream", "xsa", "bsp", "elf")
    }
    if set(entries) != required:
        errors.append("P10.4 frozen artifact set mismatch")
    for key, item in entries.items():
        try:
            path = (ROOT / str(item["path"])).resolve()
            if not base.inside(path, ROOT) or not path.is_file() or \
                    path.stat().st_size != int(item["bytes"]) or \
                    p104.sha256(path) != item["sha256"]:
                errors.append(f"frozen artifact changed: {key}")
            else:
                artifacts[key] = path
        except (KeyError, OSError, TypeError, ValueError):
            errors.append(f"malformed frozen artifact: {key}")

    try:
        wiring = base.load_yaml(base.WIRING)
        inventory = base.load_yaml(base.INVENTORY)
        modules = inventory.get("p10_3_current_installation", {}).get("modules", {})
        if modules.get("F2", {}).get("small_board_id") != "B0001" or \
                modules.get("R2", {}).get("small_board_id") != "B0023":
            errors.append("F2/R2 module identity mismatch")
        if wiring.get("lane_pairs", {}).get("lane2") != "F2-R2":
            errors.append("lane2 wiring pair mismatch")
        boards = wiring.get("boards", {})
        if boards.get("fixed", {}).get("jtag_cable_serial") != base.EXPECTED_FIXED_SERIAL or \
                boards.get("rotating", {}).get("jtag_cable_serial") != base.EXPECTED_ROTATING_SERIAL:
            errors.append("board/JTAG role binding mismatch")
    except (OSError, ValueError) as exc:
        errors.append(f"wiring/inventory intake failed: {exc}")

    errors.extend(raw.validate_plans())
    try:
        expected_inputs()
    except OSError as exc:
        errors.append(f"authorization input missing: {exc}")
    if git("branch", "--show-current") != BRANCH:
        errors.append("P10.4 branch mismatch")
    return freeze, artifacts, errors


def expected_run_id(freeze: dict[str, Any]) -> str:
    entries = {p104.artifact_key(item): item for item in freeze["artifacts"]}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        f"p10_4_l2raw_{stamp}_{freeze['source_commit'][:8]}_"
        f"{entries['fixed:functional_bitstream']['sha256'][:8]}_"
        f"{entries['rotating:functional_bitstream']['sha256'][:8]}"
    )


def prepare_authorization(run_id: str | None) -> dict[str, Any]:
    configure_raw_helpers()
    raw.auth_input_paths = auth_input_paths
    raw.expected_inputs = expected_inputs
    raw.validate_static_inputs = validate_static_inputs
    raw.expected_run_id = expected_run_id
    record = raw.prepare_authorization(run_id)
    record.update({
        "authorization_source": "direct_current_user_request",
        "authorization_source_statement": USER_STATEMENT,
        "user_authorization_received_on": "2026-08-06",
        "campaign_standing_authorization": (
            "The current user request authorizes exactly one bounded F2/R2 "
            "bidirectional RAW retest; it does not reactivate the terminated "
            "P10.4 campaign or authorize stress traffic."
        ),
        "authorization_interpretation": (
            "One immutable run ID; F2-to-R2 and R2-to-F2; receive-only startup "
            "plus 64 and 1024 raw pulses; lane mask exactly 0x4; no framed traffic."
        ),
        "prior_p10_4_terminal_state": {
            "status": "FAIL_CLOSED",
            "blocker": p104.rel(BLOCKER),
            "blocker_sha256": p104.sha256(BLOCKER),
            "not_overwritten_by_this_retest": True,
        },
        "pulse_exposure": {
            "per_direction_requested_pulses": 1088,
            "requested_txd_high_cycles_per_pulse": 8,
            "phy_clock_hz": 64_000_000,
            "requested_high_time_ns_per_pulse": 125,
            "aggregate_requested_high_time_us_per_direction": 136.0,
            "spacing_cycles": 1024,
            "nominal_pulse_duty_percent": 0.78125,
        },
    })
    base.write_json(AUTH, record)
    return record


def validate_authorization(path: Path, run_id: str) -> tuple[
        dict[str, Any], dict[str, Path], list[str]]:
    configure_raw_helpers()
    raw.auth_input_paths = auth_input_paths
    raw.expected_inputs = expected_inputs
    raw.validate_static_inputs = validate_static_inputs
    raw.expected_run_id = expected_run_id
    record, artifacts, errors = raw.validate_authorization(path, run_id)
    if record.get("authorization_source_statement") != USER_STATEMENT:
        errors.append("current user authorization statement mismatch")
    if record.get("authorization_source") != "direct_current_user_request":
        errors.append("current authorization provenance mismatch")
    if record.get("pulse_exposure", {}).get(
            "aggregate_requested_high_time_us_per_direction") != 136.0:
        errors.append("bounded pulse exposure mismatch")
    return record, artifacts, errors


def invoke_direction(
    name: str,
    run_root: Path,
    auth: Path,
    artifacts: dict[str, Path],
    ps7: dict[str, Path],
    env: dict[str, str],
) -> dict[str, Any]:
    stage_dir = run_root / "stages" / name
    dump_dir = stage_dir / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=False)
    plan = stage_dir / "immutable.plan"
    base.write_text(plan, base.plan_text(raw.build_plans()[name]))
    result_file = stage_dir / "xsdb.result.txt"
    command = [
        str(p104.XSDB), str(p104.STAGE_TCL), "tcp:localhost:3121",
        base.EXPECTED_FIXED_SERIAL, base.EXPECTED_ROTATING_SERIAL,
        str(artifacts["fixed:functional_bitstream"]),
        str(artifacts["rotating:functional_bitstream"]),
        str(artifacts["fixed:elf"]), str(artifacts["rotating:elf"]),
        str(ps7["fixed"]), str(ps7["rotating"]), str(plan), str(dump_dir),
        str(run_root / "authorization/ABORT_NOW.txt"), str(result_file),
        TCL_STAGE, str(auth), run_root.name,
        f"0x{p104.EXPECTED_BUILD['fixed']:08X}",
        f"0x{p104.EXPECTED_BUILD['rotating']:08X}",
        f"0x{p104.REGISTER_MAP_VERSION:08X}",
        f"0x{p104.REGISTER_MAP_HASH_LOW:08X}",
    ]
    process = base.run_bounded(
        command,
        stage_dir / "xsdb.stdout.log",
        stage_dir / "xsdb.stderr.log",
        STAGE_TIMEOUT_SECONDS,
        env,
    )
    direction = raw.evaluate_direction(name, stage_dir, process)
    direction["test_id"] = f"P10_4-HW-LANE2-RAW-{name.upper()}"
    forensic = p104.capture_and_archive(name, run_root, auth, env)
    direction["forensics"] = forensic
    if forensic.get("status") != "PASS" or forensic.get("frozen_roles"):
        direction["status"] = "FAIL"
        direction.setdefault("errors", []).append(
            "first-fault forensic capture failed or unexpectedly froze"
        )
    base.write_json(stage_dir / "stage_summary.json", direction)
    return direction


def render_report(summary: dict[str, Any]) -> str:
    rows: list[str] = []
    for direction in summary.get("directions", []):
        for result in direction.get("case_results", {}).values():
            if result.get("command") == 2:
                rows.append(
                    f"| {direction['direction']} | {result['requested_raw_pulses']} | "
                    f"{result['status']} | {result.get('sender_physical_tx_count', '-')} | "
                    f"{result.get('receiver_raw_rx_count', '-')} | "
                    f"{result.get('tx_high_max_cycles', '-')} |"
                )
    return "\n".join([
        "# P10.4 F2/R2 RAW connectivity retest",
        "",
        f"- Result: `{summary['status']}`",
        f"- Run ID: `{summary['run_id']}`",
        "- Evidence class: `RAW_PHYSICAL_ONLY`",
        "- Pair: `F2=B0001` ↔ `R2=B0023`",
        "- Lane mask: `0x4`",
        "- Traffic: receive-only startup, then exactly 64 and 1024 raw pulses per direction",
        "",
        "| Direction | Requested | Result | Physical TX | Remote raw RX | Max TX-high cycles |",
        "|---|---:|---|---:|---:|---:|",
        *rows,
        "",
        f"- Shutdown fixed: `{summary['SHUTDOWN_FIXED']}`",
        f"- Shutdown rotating: `{summary['SHUTDOWN_ROTATING']}`",
        "- Current-run hardware authorization: `false` (consumed)",
        "",
        "This is only a fresh static RAW physical-connectivity result. It does not "
        "replace the prior P10.4 FAIL_CLOSED evidence or prove framed data, streaming, "
        "performance, four-lane robustness, external electrical behavior, rotation, or P11.",
        "",
    ])


def execute(run_id: str, auth_path: Path) -> int:
    record, artifacts, errors = validate_authorization(auth_path, run_id)
    if os.environ.get("NO_HARDWARE") != "0" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "true":
        errors.append("NO_HARDWARE=0 and CURRENT_RUN_HARDWARE_AUTHORIZATION=true required")
    run_root = HW_ROOT / run_id
    if run_root.exists():
        errors.append("run-id evidence directory already exists")
    if errors:
        print(json.dumps({"status": "FAIL_PRECONDITION", "errors": errors},
                         indent=2, ensure_ascii=False), file=sys.stderr)
        return 3

    ps7 = p104.initialize_run(run_root, auth_path, artifacts)
    base.write_text(
        run_root / "authorization/RAW_SCOPE_ATTESTATION.txt",
        "PAIR=F2:B0001,R2:B0023\nLANE_MASK=0x4\n"
        "DIRECTIONS=F2_TO_R2,R2_TO_F2\nFRAMED_TRAFFIC=false\n"
        "ETHERNET=false\nMOVEMENT=false\nROTATION=false\nREALIGNMENT=false\n"
        "REWIRING=false\nMODULE_REPLACEMENT=false\nEXTERNAL_INSTRUMENTATION=false\n",
    )
    env = {
        **os.environ,
        "NO_HARDWARE": "0",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": "true",
        "RF_COMM_P10_HW_AUTH": "P10_4_IMMUTABLE_AUTHORIZED",
    }
    server_proc = None
    shutdowns: list[dict[str, Any]] = []
    direction_results: list[dict[str, Any]] = []
    campaign_errors: list[str] = []
    hardware_actions = False
    try:
        server_proc, server = p104.start_hw_server(run_root / "raw_logs")
        p104.write_json(run_root / "raw_logs/hw_server.json", server)
        if server.get("status") != "PASS":
            raise RuntimeError(server.get("reason", "hw_server unavailable"))
        hardware_actions = True
        initial = p104.guarded_shutdown(run_root, auth_path, artifacts, "initial", env)
        shutdowns.append(initial)
        if initial.get("status") != "PASS":
            raise RuntimeError("initial dual shutdown unconfirmed")
        for name in DIRECTIONS:
            before = p104.guarded_shutdown(
                run_root, auth_path, artifacts, f"{name}_before", env
            )
            shutdowns.append(before)
            if before.get("status") != "PASS":
                raise RuntimeError(f"{name}: shutdown-before unconfirmed")
            direction: dict[str, Any] | None = None
            stage_exception: BaseException | None = None
            try:
                direction = invoke_direction(
                    name, run_root, auth_path, artifacts, ps7, env
                )
                direction_results.append(direction)
            except BaseException as exc:
                stage_exception = exc
            finally:
                after = p104.guarded_shutdown(
                    run_root, auth_path, artifacts, f"{name}_after", env
                )
                shutdowns.append(after)
            if after.get("status") != "PASS":
                raise RuntimeError(f"{name}: shutdown-after unconfirmed")
            if stage_exception is not None:
                if isinstance(stage_exception, KeyboardInterrupt):
                    raise KeyboardInterrupt from stage_exception
                raise RuntimeError(f"{name}: wrapper exception: {stage_exception}")
            # Continue to the reverse direction after a contained RAW failure.
            assert direction is not None
        final = p104.guarded_shutdown(run_root, auth_path, artifacts, "final", env)
        shutdowns.append(final)
        if final.get("status") != "PASS":
            raise RuntimeError("final dual shutdown unconfirmed")
    except KeyboardInterrupt:
        campaign_errors.append("Ctrl+C")
    except Exception as exc:
        campaign_errors.append(str(exc))
    finally:
        if hardware_actions:
            emergency = p104.guarded_shutdown(
                run_root, auth_path, artifacts, "finally", env
            )
            shutdowns.append(emergency)
            if emergency.get("status") != "PASS":
                campaign_errors.append("finally dual shutdown unconfirmed")
        if server_proc is not None:
            try:
                p104.terminate_tree(server_proc)
            except Exception as exc:
                campaign_errors.append(f"owned hw_server termination failed: {exc}")

    all_shutdown = bool(shutdowns) and all(
        item.get("status") == "PASS" for item in shutdowns
    )
    directions_pass = len(direction_results) == 2 and all(
        item.get("status") == "PASS" for item in direction_results
    )
    status = "PASS" if all_shutdown and directions_pass and not campaign_errors else "FAIL"
    summary: dict[str, Any] = {
        "schema_version": 1,
        "test_id": "P10_4-HW-LANE2-RAW-CONNECTIVITY-RETEST",
        "status": status,
        "evidence_class": "RAW_PHYSICAL_ONLY",
        "run_id": run_id,
        "scope": SCOPE,
        "goal_sha256": p104.GOAL_SHA256,
        "artifact_source_commit": record["artifact_source_commit"],
        "artifact_freeze_sha256": record["artifact_freeze_sha256"],
        "artifacts": record["artifacts"],
        "board_binding": record["board_binding"],
        "module_binding": {"F2": "B0001", "R2": "B0023"},
        "lane": 2,
        "lane_pair": "F2-R2",
        "maximum_lane_mask_authorized": "0x4",
        "maximum_lane_mask_used": "0x4" if direction_results else "0x0",
        "directions": direction_results,
        "pulse_exposure": record["pulse_exposure"],
        "hardware_actions_executed": hardware_actions,
        "current_run_hardware_authorization": False,
        "authorization_consumed": True,
        "network_used": False,
        "hardware_moved": False,
        "rotation_executed": False,
        "realignment_executed": False,
        "wiring_changed": False,
        "module_replaced": False,
        "external_instrumentation_used": False,
        "framed_traffic": False,
        "shutdowns": shutdowns,
        "SHUTDOWN_FIXED": "PASS" if all_shutdown and all(
            item.get("SHUTDOWN_FIXED") == "PASS" for item in shutdowns
        ) else "FAIL",
        "SHUTDOWN_ROTATING": "PASS" if all_shutdown and all(
            item.get("SHUTDOWN_ROTATING") == "PASS" for item in shutdowns
        ) else "FAIL",
        "prior_p10_4_fail_closed_overwritten": False,
        "errors": campaign_errors,
        "generated_at_utc": utc_now(),
    }
    final_path = run_root / "final/orchestrator_result.json"
    p104.write_json(final_path, summary)
    p104.evidence_manifest(run_root)
    manifest_errors = p104.verify_evidence_manifest(
        run_root,
        p104.load_json(run_root / "final/run_evidence_sha256_manifest.json"),
    )
    if manifest_errors:
        summary["status"] = "FAIL"
        summary["errors"].extend(manifest_errors)
        p104.write_json(final_path, summary)
        p104.evidence_manifest(run_root)
        manifest_errors = p104.verify_evidence_manifest(
            run_root,
            p104.load_json(run_root / "final/run_evidence_sha256_manifest.json"),
        )
    manifest_path = run_root / "final/run_evidence_sha256_manifest.json"
    generated = dict(summary)
    generated.update({
        "status": summary["status"],
        "raw_result": p104.rel(final_path),
        "raw_result_sha256": p104.sha256(final_path),
        "run_evidence_manifest": p104.rel(manifest_path),
        "run_evidence_manifest_sha256": p104.sha256(manifest_path),
        "manifest_verification": "PASS" if not manifest_errors else "FAIL",
        "manifest_errors": manifest_errors,
    })
    p104.write_json(GENERATED.with_suffix(".json"), generated)
    report_text = render_report(generated)
    base.write_text(GENERATED.with_suffix(".md"), report_text)
    REPORTS.mkdir(parents=True, exist_ok=True)
    base.write_text(REPORTS / f"lane2_connectivity_probe_{run_id}.md", report_text)

    consumed = dict(record)
    consumed.update({
        "status": f"CONSUMED_AFTER_P10_4_LANE2_RAW_RETEST_{summary['status']}",
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": hardware_actions,
        "consumed": True,
        "consumed_at_utc": utc_now(),
        "result": p104.rel(GENERATED.with_suffix(".json")),
        "run_evidence": p104.rel(final_path),
    })
    base.write_json(AUTH, consumed)
    print(f"P10_4_LANE2_RAW_CONNECTIVITY={summary['status']}")
    print(f"P10_4_LANE2_RAW_RUN_ID={run_id}")
    print(f"SHUTDOWN_FIXED={summary['SHUTDOWN_FIXED']}")
    print(f"SHUTDOWN_ROTATING={summary['SHUTDOWN_ROTATING']}")
    return 0 if summary["status"] == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-authorization", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--authorization", type=Path, default=AUTH)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    args = parser.parse_args(argv)
    configure_raw_helpers()
    if args.prepare_authorization:
        try:
            record = prepare_authorization(args.run_id)
        except Exception as exc:
            print(f"P10_4_LANE2_RAW_AUTHORIZATION=FAIL\nERROR={exc}", file=sys.stderr)
            return 2
        print("P10_4_LANE2_RAW_AUTHORIZATION=PASS")
        print(f"P10_4_LANE2_RAW_RUN_ID={record['run_id']}")
        print(f"P10_4_LANE2_RAW_AUTHORIZATION_PATH={p104.rel(AUTH)}")
        print(f"P10_4_LANE2_RAW_AUTHORIZATION_SHA256={p104.sha256(AUTH)}")
        return 0
    if not args.run_id:
        print("P10_4_LANE2_RAW_RUNNER_REFUSED=RUN_ID_REQUIRED", file=sys.stderr)
        return 3
    record, _, errors = validate_authorization(args.authorization.resolve(), args.run_id)
    if args.validate_only:
        print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors},
                         indent=2, ensure_ascii=False))
        return 0 if not errors else 3
    if not args.execute_hardware:
        print("P10_4_LANE2_RAW_RUNNER_REFUSED=EXPLICIT_HARDWARE_FLAG_REQUIRED",
              file=sys.stderr)
        return 3
    if not record:
        print(json.dumps({"status": "FAIL_PRECONDITION", "errors": errors},
                         indent=2, ensure_ascii=False), file=sys.stderr)
        return 3
    return execute(args.run_id, args.authorization.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
