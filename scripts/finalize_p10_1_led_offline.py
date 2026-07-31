#!/usr/bin/env python3
"""Freeze the AX7020 PL activity LED offline checkpoint and evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
REQUIREMENTS = ROOT / "config/project_requirements.yaml"
STATE = ROOT / "config/project_state.json"
TRACEABILITY = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"
DETERMINISTIC_TIMESTAMP = "2026-07-31T00:00:00Z"

INPUTS = {
    "led_xsim_and_static": GENERATED / "p10_1_led_offline/summary.json",
    "dual_endpoint_regression": (
        GENERATED / "p10_1_led_dual_endpoint_regression/summary.json"
    ),
    "fixed_rotating_routed_build": (
        GENERATED / "p10_1_ax7020_pl_activity_led_build_summary.json"
    ),
    "fixed_rotating_runtime_build": (
        GENERATED / "p10_1_ax7020_pl_activity_led_runtime_build_summary.json"
    ),
    "tfdu_safety_regression": (
        GENERATED / "p10_1_led_p8c_safety/p8c_final_summary.json"
    ),
    "full_offline_gate_replay": (
        GENERATED / "p10_1_led_full_offline_gate_replay/summary.json"
    ),
}

OFFLINE_REQUIREMENTS = ("OBS-LED-001", "OBS-LED-002", "OBS-LED-003", "OBS-LED-004")
HARDWARE_REQUIREMENT = "OBS-LED-HW-001"
FINALIZATION_OUTPUTS = (
    "p10_1_led_artifact_manifest.json",
    "p10_1_led_offline_acceptance_leaf.json",
    "p10_1_led_offline_acceptance_leaf.md",
    "p10_1_led_evidence_consistency.json",
    "p10_1_led_evidence_consistency.md",
    "p10_1_led_final_summary.json",
    "p10_1_led_final_summary.md",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def record(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{rel(path)} must contain a JSON object")
    return value


def offline_execution_fields(payload: dict[str, Any]) -> tuple[Any, Any]:
    hardware_actions = payload.get("hardware_actions_executed")
    if (
        hardware_actions is None
        and payload.get("NO_HARDWARE_ACTIONS_EXECUTED") is True
    ):
        hardware_actions = False
    current_authorization = payload.get("current_run_hardware_authorization")
    if current_authorization is None:
        current_authorization = payload.get("CURRENT_RUN_HARDWARE_AUTHORIZATION")
    return hardware_actions, current_authorization


def archive_existing_finalization() -> str | None:
    final_path = GENERATED / "p10_1_led_final_summary.json"
    if not final_path.is_file():
        return None
    try:
        previous = load_json(final_path)
    except (OSError, ValueError, json.JSONDecodeError):
        previous = {}
    stamp = re.sub(
        r"[^0-9A-Za-z]+",
        "",
        str(previous.get("generated_at_utc", "undated")),
    )
    status = re.sub(r"[^0-9A-Za-z]+", "", str(previous.get("status", "UNKNOWN")))
    archive_root = GENERATED / "p10_1_led_finalization_attempts"
    archive_root.mkdir(parents=True, exist_ok=True)
    destination = archive_root / f"{stamp}_{status}"
    suffix = 1
    while destination.exists():
        suffix += 1
        destination = archive_root / f"{stamp}_{status}_{suffix}"
    destination.mkdir()
    for name in FINALIZATION_OUTPUTS:
        source = GENERATED / name
        if source.exists():
            shutil.move(str(source), str(destination / name))
    return rel(destination)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_md(path: Path, title: str, payload: dict[str, Any], lines: list[str]) -> None:
    content = [
        f"# {title}",
        "",
        f"- Status: `{payload['status']}`",
        f"- Test ID: `{payload['test_id']}`",
        "- Hardware actions executed: `false`",
        "- Current-run hardware authorization: `false`",
        "",
        *lines,
    ]
    if payload.get("errors"):
        content += ["", "## Errors", ""]
        content.extend(f"- {item}" for item in payload["errors"])
    path.write_text("\n".join(content).rstrip() + "\n", encoding="utf-8", newline="\n")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def run_check(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "NO_HARDWARE": "1",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
        },
        errors="replace",
    )
    return {
        "command": subprocess.list2cmdline(command),
        "return_code": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }


def verify_content_addressed(item: dict[str, Any], errors: list[str], label: str) -> Path | None:
    path_value = item.get("path")
    digest = str(item.get("sha256", "")).lower()
    if not isinstance(path_value, str) or len(digest) != 64:
        errors.append(f"{label}: malformed artifact record")
        return None
    path = (ROOT / path_value).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        errors.append(f"{label}: artifact escapes repository")
        return None
    if not path.is_file():
        errors.append(f"{label}: missing {path_value}")
        return None
    actual = sha256(path)
    if actual != digest:
        errors.append(f"{label}: SHA256 mismatch for {path_value}")
    if digest not in path.parts:
        errors.append(f"{label}: SHA256 is absent from content-addressed path")
    if item.get("read_only") is not True:
        errors.append(f"{label}: artifact is not declared read-only")
    return path


def update_requirements(leaf: Path) -> None:
    document = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("requirements"), list):
        raise ValueError("config/project_requirements.yaml has invalid structure")
    by_id = {
        item.get("requirement_id"): item
        for item in document["requirements"]
        if isinstance(item, dict)
    }
    leaf_hash = sha256(leaf)
    binding = {"path": rel(leaf), "sha256": leaf_hash}
    for requirement_id in OFFLINE_REQUIREMENTS:
        item = by_id.get(requirement_id)
        if not isinstance(item, dict):
            raise ValueError(f"missing requirement {requirement_id}")
        item["verification_scope"] = (
            "P10_1_AX7020_PL_ACTIVITY_LED_OFFLINE_VALIDATED_PENDING_HARDWARE"
        )
        item["evidence_path"] = rel(leaf)
        item["status"] = "PASS"
        item["artifact_hash"] = leaf_hash
        item["artifact_hashes"] = [binding.copy()]
        item["hardware_followup"] = (
            "The LED-enabled artifacts still require direct current-run hardware "
            "validation; LED indication remains monitor-only and is not safety or "
            "optical-success evidence."
        )
    hardware = by_id.get(HARDWARE_REQUIREMENT)
    if not isinstance(hardware, dict):
        raise ValueError(f"missing requirement {HARDWARE_REQUIREMENT}")
    hardware["status"] = "PENDING"
    hardware["test_id"] = None
    hardware["artifact_hashes"] = []
    mutable_canonical_hashes = {
        rel(STATE): sha256(STATE),
        rel(PROJECT_STATUS): sha256(PROJECT_STATUS),
    }
    for item in document["requirements"]:
        if not isinstance(item, dict):
            continue
        artifact_hashes = item.get("artifact_hashes")
        if not isinstance(artifact_hashes, list):
            continue
        for artifact in artifact_hashes:
            if not isinstance(artifact, dict):
                continue
            path_value = artifact.get("path")
            if path_value in mutable_canonical_hashes:
                artifact["sha256"] = mutable_canonical_hashes[path_value]
        if (
            artifact_hashes
            and isinstance(artifact_hashes[0], dict)
            and artifact_hashes[0].get("path") in mutable_canonical_hashes
        ):
            item["artifact_hash"] = artifact_hashes[0]["sha256"]
    REQUIREMENTS.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
        newline="\n",
    )


def update_state(leaf: Path, manifest: Path, payloads: dict[str, dict[str, Any]]) -> None:
    state = load_json(STATE)
    build = payloads["fixed_rotating_routed_build"]
    runtime = payloads["fixed_rotating_runtime_build"]
    replay = payloads["full_offline_gate_replay"]
    roles: dict[str, dict[str, Any]] = {}
    for role in build["roles"]:
        roles.setdefault(role["role"], {}).update(
            {
                "profile": role["profile"],
                "bitstream": role["artifacts"]["bitstream"],
                "xsa": role["artifacts"]["xsa"],
                "wns_ns": float(role["markers"]["P10_WNS_NS"]),
                "whs_ns": float(role["markers"]["P10_WHS_NS"]),
                "tns_ns": float(role["markers"]["P10_TNS_NS"]),
            }
        )
    for role in runtime["roles"]:
        roles.setdefault(role["role"], {}).update(
            {
                "bsp": role["artifacts"]["bsp"],
                "elf": role["artifacts"]["elf"],
            }
        )
    state["p10_1_pl_activity_leds"] = {
        "status": "OFFLINE_PASS_HARDWARE_PENDING",
        "verification_scope": (
            "P10_1_AX7020_PL_ACTIVITY_LED_OFFLINE_VALIDATED_PENDING_HARDWARE"
        ),
        "implementation_source_commit": build["source_commit"],
        "runtime_build_source_commit": runtime["source_commit"],
        "evidence_foundation_commit": replay["source_commit"],
        "evidence_path": rel(leaf),
        "evidence_sha256": sha256(leaf),
        "artifact_manifest_path": rel(manifest),
        "artifact_manifest_sha256": sha256(manifest),
        "mapping": "LED1_LANE0_TX_LED2_LANE0_RX_LED3_LANE1_TX_LED4_LANE1_RX",
        "active_low": True,
        "monitor_only": True,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "new_hardware_validation_status": "PENDING",
        "roles": roles,
    }
    STATE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")
    archived_previous = archive_existing_finalization()

    payloads: dict[str, dict[str, Any]] = {}
    for name, path in INPUTS.items():
        if not path.is_file():
            errors.append(f"missing input: {rel(path)}")
            continue
        try:
            payload = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid input {rel(path)}: {exc}")
            continue
        payloads[name] = payload
        if payload.get("status") != "PASS":
            errors.append(f"{name}: status is not PASS")
        hardware_actions, current_authorization = offline_execution_fields(payload)
        if hardware_actions is not False:
            errors.append(f"{name}: hardware_actions_executed is not false")
        if current_authorization is not False:
            errors.append(f"{name}: current_run_hardware_authorization is not false")
        if payload.get("source_worktree_dirty") not in (False, None):
            errors.append(f"{name}: source worktree was dirty")

    durable_artifacts: list[Path] = []
    if "fixed_rotating_routed_build" in payloads:
        build = payloads["fixed_rotating_routed_build"]
        if {role.get("role") for role in build.get("roles", [])} != {"fixed", "rotating"}:
            errors.append("routed build does not contain exactly fixed and rotating roles")
        for role in build.get("roles", []):
            markers = role.get("markers", {})
            expected_markers = {
                "P10_FUNCTIONAL_BUILD": "PASS",
                "P10_ETHERNET_ENABLED": "false",
                "P10_NETWORK_USED": "false",
                "P10_HARDWARE_ADMISSION": "false",
                "P10_PL_ACTIVITY_LED_ACTIVE_LOW": "true",
                "P10_PL_ACTIVITY_LED_HOLD_MS": "200",
                "P10_PL_ACTIVITY_LED_SAFETY_ROLE": "MONITOR_ONLY",
                "P10_DRC_CRITICAL_COUNT": "0",
                "P10_DRC_ERROR_COUNT": "0",
                "P10_METHODOLOGY_CRITICAL_COUNT": "0",
                "P10_CDC_CRITICAL_COUNT": "0",
                "P10_REQP_1839_COUNT": "0",
                "P10_TNS_NS": "0.0",
            }
            for key, expected in expected_markers.items():
                if markers.get(key) != expected:
                    errors.append(
                        f"{role.get('role')} routed marker {key} != {expected}"
                    )
            if float(markers.get("P10_WNS_NS", "-1")) <= 0.0:
                errors.append(f"{role.get('role')} routed WNS is not positive")
            if float(markers.get("P10_WHS_NS", "-1")) <= 0.0:
                errors.append(f"{role.get('role')} routed WHS is not positive")
            for kind in ("bitstream", "xsa"):
                path = verify_content_addressed(
                    role.get("artifacts", {}).get(kind, {}),
                    errors,
                    f"{role.get('role')} {kind}",
                )
                if path is not None:
                    durable_artifacts.append(path)

    if "fixed_rotating_runtime_build" in payloads:
        runtime = payloads["fixed_rotating_runtime_build"]
        if runtime.get("native_crypto_protocol_test") != "PASS":
            errors.append("native crypto protocol test is not PASS")
        if {role.get("role") for role in runtime.get("roles", [])} != {
            "fixed",
            "rotating",
        }:
            errors.append("runtime build does not contain exactly fixed and rotating roles")
        for role in runtime.get("roles", []):
            if role.get("inspection", {}).get("elf_end_address", "0xffffffff") >= role.get(
                "inspection", {}
            ).get("ocm_boundary", "0x00000000"):
                errors.append(f"{role.get('role')} ELF exceeds OCM boundary")
            for kind in ("bsp", "elf"):
                path = verify_content_addressed(
                    role.get("artifacts", {}).get(kind, {}),
                    errors,
                    f"{role.get('role')} {kind}",
                )
                if path is not None:
                    durable_artifacts.append(path)

    config_path = ROOT / "config/hardware/p10_1_ax7020_pl_activity_leds.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    expected_pins = [
        ("LED1", 0, "M14", "lane0 TX"),
        ("LED2", 1, "M15", "lane0 RX"),
        ("LED3", 2, "K16", "lane1 TX"),
        ("LED4", 3, "J16", "lane1 RX"),
    ]
    actual_pins = [
        (
            item.get("led"),
            item.get("rtl_bit"),
            item.get("package_pin"),
            item.get("role_independent_meaning"),
        )
        for item in config.get("pins", [])
    ]
    if actual_pins != expected_pins:
        errors.append("canonical LED pin/semantic mapping mismatch")
    if config.get("electrical", {}).get("fpga_bank") != 35:
        errors.append("LED FPGA bank is not 35")
    if config.get("electrical", {}).get("vcco_volts") != 3.3:
        errors.append("LED VCCO is not 3.3 V")
    if config.get("electrical", {}).get("iostandard") != "LVCMOS33":
        errors.append("LED IOSTANDARD is not LVCMOS33")
    if config.get("isolation", {}).get("classification") != "PURE_MONITOR_TAP":
        errors.append("LED isolation is not PURE_MONITOR_TAP")

    manifest_path = GENERATED / "p10_1_led_artifact_manifest.json"
    manifest_inputs = [
        *INPUTS.values(),
        config_path,
        ROOT / "docs/hardware/P10_1_AX7020_PL_ACTIVITY_LED_DESIGN.md",
        ROOT / "rtl/p10_lane_activity_leds.sv",
        ROOT / "sim/tb/tb_p10_lane_activity_leds.sv",
        ROOT / "board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc",
        ROOT / "board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc",
        *durable_artifacts,
    ]
    unique_manifest_inputs = sorted(
        {path.resolve() for path in manifest_inputs if path.is_file()},
        key=lambda path: rel(path),
    )
    manifest = {
        "schema_version": 1,
        "test_id": "P10_1-LED-IMMUTABLE-ARTIFACT-MANIFEST",
        "generated_at_utc": DETERMINISTIC_TIMESTAMP,
        "status": "PASS" if not errors else "FAIL",
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "file_count": len(unique_manifest_inputs),
        "files": [record(path) for path in unique_manifest_inputs],
        "errors": errors.copy(),
    }
    write_json(manifest_path, manifest)

    leaf_path = GENERATED / "p10_1_led_offline_acceptance_leaf.json"
    leaf = {
        "schema_version": 1,
        "test_id": "P10_1-LED-OFFLINE-ACCEPTANCE-LEAF",
        "generated_at_utc": DETERMINISTIC_TIMESTAMP,
        "status": "PASS" if not errors else "FAIL",
        "branch": git("branch", "--show-current"),
        "base_checkpoint_commit": "8c34d60f064b01b95dc9c35b664ffbe43efb0b1f",
        "implementation_source_commit": payloads.get(
            "fixed_rotating_routed_build", {}
        ).get("source_commit"),
        "runtime_build_source_commit": payloads.get(
            "fixed_rotating_runtime_build", {}
        ).get("source_commit"),
        "evidence_foundation_commit": payloads.get(
            "full_offline_gate_replay", {}
        ).get("source_commit"),
        "no_hardware": True,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "network_used": False,
        "mapping": {
            "LED1": "lane0 TX / F0 or R0 TX",
            "LED2": "lane0 RX / F0 or R0 RX",
            "LED3": "lane1 TX / F1 or R1 TX",
            "LED4": "lane1 RX / F1 or R1 RX",
        },
        "semantics": {
            "active_low": True,
            "shared_tick_ms": 1,
            "visual_hold_ms": 200,
            "tx_source": "final role-local physical Txd event",
            "rx_source": "completed CRC-valid role-local frame event",
            "receive_only_observable": True,
            "reset_fault_full_shutdown_all_off": True,
            "monitor_only": True,
        },
        "input_evidence": {
            name: record(path)
            for name, path in INPUTS.items()
            if path.is_file()
        },
        "artifact_manifest": record(manifest_path),
        "durable_artifacts": [record(path) for path in durable_artifacts],
        "historical_hardware_results_reused": False,
        "new_hardware_validation_required": True,
        "errors": errors.copy(),
    }
    write_json(leaf_path, leaf)
    write_md(
        GENERATED / "p10_1_led_offline_acceptance_leaf.md",
        "P10.1 AX7020 PL activity LED offline acceptance leaf",
        leaf,
        [
            "The fixed and rotating roles use the same active-low mapping: "
            "LED1 lane0 TX, LED2 lane0 RX, LED3 lane1 TX, LED4 lane1 RX.",
            "",
            "This is offline acceptance only. The LED outputs are pure monitor taps "
            "and do not establish safety, electrical, protocol, or optical success.",
        ],
    )

    if not errors:
        update_state(leaf_path, manifest_path, payloads)
        project_status_write = run_check(
            [sys.executable, "scripts/generate_project_status.py", "--write"]
        )
        generation_checks = [project_status_write]
        if project_status_write["status"] == "PASS":
            update_requirements(leaf_path)
            generation_checks.append(
                run_check(
                    [
                        sys.executable,
                        "scripts/generate_requirement_traceability.py",
                        "--write",
                    ]
                )
            )
    else:
        generation_checks = []

    checks = [
        *generation_checks,
        run_check([sys.executable, "scripts/generate_requirement_traceability.py", "--check"]),
        run_check([sys.executable, "scripts/generate_project_status.py", "--check"]),
        run_check([sys.executable, "scripts/check_p8a_consistency.py", "--check"]),
        run_check([sys.executable, "scripts/check_no_hardware_calls.py"]),
        run_check(["git", "diff", "--check"]),
    ]
    for item in checks:
        if item["status"] != "PASS":
            errors.append(f"consistency command failed: {item['command']}")

    consistency_path = GENERATED / "p10_1_led_evidence_consistency.json"
    consistency = {
        "schema_version": 1,
        "test_id": "P10_1-LED-EVIDENCE-CONSISTENCY",
        "generated_at_utc": DETERMINISTIC_TIMESTAMP,
        "status": "PASS" if not errors else "FAIL",
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "leaf": record(leaf_path),
        "artifact_manifest": record(manifest_path),
        "canonical_files": [
            record(REQUIREMENTS),
            record(STATE),
            record(TRACEABILITY),
            record(PROJECT_STATUS),
        ],
        "checks": checks,
        "offline_requirements": {
            requirement_id: "PASS" for requirement_id in OFFLINE_REQUIREMENTS
        },
        "hardware_requirement": {HARDWARE_REQUIREMENT: "PENDING"},
        "errors": errors.copy(),
    }
    write_json(consistency_path, consistency)
    write_md(
        GENERATED / "p10_1_led_evidence_consistency.md",
        "P10.1 AX7020 PL activity LED evidence consistency",
        consistency,
        [
            "All offline LED requirements are bound to the non-self-referential "
            "acceptance leaf. The direct-hardware requirement remains pending.",
        ],
    )

    final_path = GENERATED / "p10_1_led_final_summary.json"
    final = {
        "schema_version": 1,
        "test_id": "P10_1-LED-FINAL-OFFLINE-CHECKPOINT",
        "generated_at_utc": DETERMINISTIC_TIMESTAMP,
        "status": "PASS" if not errors else "FAIL",
        "branch": git("branch", "--show-current"),
        "no_hardware": True,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "offline_acceptance_leaf": record(leaf_path),
        "evidence_consistency": record(consistency_path),
        "artifact_manifest": record(manifest_path),
        "routed_build": record(INPUTS["fixed_rotating_routed_build"]),
        "runtime_build": record(INPUTS["fixed_rotating_runtime_build"]),
        "full_offline_gate_replay": record(INPUTS["full_offline_gate_replay"]),
        "offline_requirement_status": "PASS",
        "new_bitstream_hardware_status": "PENDING",
        "old_p10_p10_1_hardware_results_applicable_to_new_artifacts": False,
        "archived_previous_finalization": archived_previous,
        "next_stage": (
            "CREATE_HASH_BOUND_CURRENT_RUN_AUTHORIZATION_THEN_RUN_DIRECT_HARDWARE"
        ),
        "errors": errors.copy(),
    }
    write_json(final_path, final)
    write_md(
        GENERATED / "p10_1_led_final_summary.md",
        "P10.1 AX7020 PL activity LED final offline checkpoint",
        final,
        [
            "Offline implementation, simulation, fixed/rotating routed builds, "
            "software builds, safety regression, and isolated complete-gate replay "
            "are closed.",
            "",
            "The new bitstreams have no hardware PASS yet. Direct current-run "
            "hardware validation must use a separate authorization bound to the exact "
            "artifact hashes.",
        ],
    )
    print(f"P10_1_LED_OFFLINE_FINAL={final['status']}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
    if args.json_summary:
        print(json.dumps(final, sort_keys=True))
    return 0 if final["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
