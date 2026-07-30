#!/usr/bin/env python3
"""Consolidate final P10 offline build evidence without touching hardware."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GOAL = ROOT / "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md"
GOAL_SHA256 = "b7cf8f1e10d737ce587f81160df592c8f863825b009760bd32845e019c3b7603"
BRANCH = "p10/ax7020-dual-node-2lane"
INPUTS = {
    "preflight": ROOT / "evidence/generated/p10_fasttrack_concise_preflight.json",
    "regression": ROOT / "evidence/generated/p10_dual_endpoint_regression/summary.json",
    "shutdown": ROOT / "evidence/generated/p10_ax7020_shutdown_build_summary.json",
    "functional": ROOT / "evidence/generated/p10_ax7020_functional_build_summary.json",
    "runtime": ROOT / "evidence/generated/p10_ax7020_ps_runtime_build_summary.json",
    "blocker": ROOT / "evidence/generated/p10_severe_hardware_blocker.json",
}
ARCH_DOC = ROOT / "docs/hardware/P10_AX7020_DUAL_ENDPOINT_ARCHITECTURE.md"
ARCH_JSON = ROOT / "evidence/generated/p10_dual_endpoint_architecture_audit.json"
ARCH_MD = ROOT / "evidence/generated/p10_dual_endpoint_architecture_audit.md"
CDC_JSON = ROOT / "evidence/generated/p10_cdc_methodology_audit.json"
CDC_MD = ROOT / "evidence/generated/p10_cdc_methodology_audit.md"
MANIFEST_JSON = ROOT / "evidence/generated/p10_offline_artifact_manifest.json"
FINAL_JSON = ROOT / "evidence/generated/p10_fasttrack_final_summary.json"
FINAL_MD = ROOT / "evidence/generated/p10_fasttrack_final_summary.md"
NO_HW_LOG = ROOT / "evidence/generated/p10_final_no_hardware_static_scan.txt"
BUS_SKEW_SOURCES = {
    "fixed": Path(
        "C:/p10_vivado/fixed/project/"
        "p10_ax7020_fixed_functional.runs/impl_1/"
        "p10_ps_system_wrapper_bus_skew_routed.rpt"
    ),
    "rotating": Path(
        "C:/p10_vivado/rotating/project/"
        "p10_ax7020_rotating_functional.runs/impl_1/"
        "p10_ps_system_wrapper_bus_skew_routed.rpt"
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def is_ancestor(reference: str, head: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", reference, head], cwd=ROOT,
        text=True, capture_output=True, check=False,
    ).returncode == 0


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def summary_report(role_record: dict[str, Any], filename: str,
                   errors: list[str]) -> Path:
    matches = [
        item for item in role_record.get("reports", [])
        if Path(item.get("path", "")).name == filename
    ]
    require(len(matches) == 1,
            f"expected one {filename} record for {role_record.get('role')}", errors)
    if len(matches) != 1:
        return ROOT / "__missing_report__"
    record = matches[0]
    path = ROOT / record.get("path", "__missing_report__")
    require(path.is_file(), f"missing report: {path}", errors)
    if path.is_file():
        require(sha256(path) == record.get("sha256"),
                f"report hash mismatch: {path}", errors)
    return path


def issue_blocks(text: str, rule_id: str) -> list[str]:
    """Return complete Vivado methodology detail blocks for one rule."""
    lines = text.splitlines()
    header = re.compile(
        r"^[A-Z][A-Z0-9-]*#\d+\s+(?:Critical|Error|Warning|Info)$"
    )
    starts = [index for index, line in enumerate(lines) if header.match(line.strip())]
    blocks: list[str] = []
    for position, start in enumerate(starts):
        if not lines[start].strip().startswith(f"{rule_id}#"):
            continue
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        blocks.append("\n".join(lines[start:end]).strip())
    return blocks


def methodology_counts(text: str) -> dict[str, int]:
    expected = {"LUTAR-1", "PDRC-190", "TIMING-9", "TIMING-18"}
    counts: dict[str, int] = {}
    for line in text.splitlines():
        match = re.match(
            r"^\|\s*([A-Z][A-Z0-9-]*)\s*\|\s*Warning\s*\|.*\|\s*(\d+)\s*\|$",
            line,
        )
        if match and match.group(1) in expected:
            counts[match.group(1)] = int(match.group(2))
    return counts


def cdc_summary_counts(text: str) -> dict[str, dict[str, Any]]:
    counts: dict[str, dict[str, Any]] = {}
    for match in re.finditer(
            r"^(CDC-\d+)\s+(Info|Warning|Critical|Error)\s+(\d+)\s+",
            text, re.MULTILINE):
        counts[match.group(1)] = {
            "severity": match.group(2),
            "count": int(match.group(3)),
        }
    return counts


def artifact_records(inputs: dict[str, dict[str, Any]], errors: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def add(kind: str, role: str, record: dict[str, Any]) -> None:
        path = ROOT / record.get("path", "__missing__")
        expected = record.get("sha256")
        require(path.is_file(), f"missing {kind} artifact for {role}: {path}", errors)
        actual = sha256(path) if path.is_file() else None
        require(actual == expected, f"{kind} hash mismatch for {role}", errors)
        records.append({
            "kind": kind,
            "role": role,
            "path": record.get("path"),
            "sha256": expected,
            "bytes": path.stat().st_size if path.is_file() else None,
            "verified": path.is_file() and actual == expected,
        })

    for role in inputs["shutdown"].get("roles", []):
        if role.get("artifact"):
            add("shutdown_bitstream", role["role"], role["artifact"])
    for role in inputs["functional"].get("roles", []):
        for name, record in role.get("artifacts", {}).items():
            add("functional_bitstream" if name == "bitstream" else "xsa",
                role["role"], record)
    for role in inputs["runtime"].get("roles", []):
        for name, record in role.get("artifacts", {}).items():
            add(name, role["role"], record)
    return records


def main() -> int:
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P10_EVIDENCE_REFUSED: offline environment required", file=sys.stderr)
        return 2
    require(GOAL.is_file() and sha256(GOAL) == GOAL_SHA256,
            "fast-track goal hash mismatch", errors)
    require(git("branch", "--show-current") == BRANCH, "branch mismatch", errors)
    source_commit = git("rev-parse", "HEAD")
    require(is_ancestor("main", source_commit), "main is not an ancestor", errors)
    require(is_ancestor("p8e-pass", source_commit), "p8e-pass is not an ancestor", errors)
    require(is_ancestor("p9-z7010-2lane-pass", source_commit),
            "p9-z7010-2lane-pass is not an ancestor", errors)
    require(ARCH_DOC.is_file(), "architecture document missing", errors)
    for name, path in INPUTS.items():
        require(path.is_file(), f"missing input summary: {name}", errors)
    if errors:
        for error in errors:
            print(f"P10_EVIDENCE_ERROR: {error}", file=sys.stderr)
        return 1

    no_hw = subprocess.run(
        [sys.executable, "scripts/check_no_hardware_calls.py"], cwd=ROOT,
        text=True, capture_output=True, timeout=120,
        env={**os.environ, "NO_HARDWARE": "1",
             "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
    )
    no_hw_text = (
        f"RETURN_CODE={no_hw.returncode}\nSTDOUT_BEGIN\n{no_hw.stdout}\nSTDOUT_END\n"
        f"STDERR_BEGIN\n{no_hw.stderr}\nSTDERR_END\n"
    )
    NO_HW_LOG.write_text(no_hw_text, encoding="utf-8", errors="replace", newline="\n")
    require(no_hw.returncode == 0 and "NO_HARDWARE_ACTIONS_EXECUTED=1" in no_hw.stdout,
            "final no-hardware static scan failed", errors)

    inputs = {name: load(path) for name, path in INPUTS.items()}
    for name in ("regression", "shutdown", "functional", "runtime"):
        summary = inputs[name]
        require(summary.get("status") == "PASS", f"{name} status is not PASS", errors)
        require(summary.get("source_commit") == source_commit,
                f"{name} source commit mismatch", errors)
        require(summary.get("source_worktree_dirty") is False,
                f"{name} was generated from tracked-dirty source", errors)
        require(summary.get("hardware_actions_executed") is False,
                f"{name} reports a hardware action", errors)
    require(inputs["preflight"].get("status") == "PASS", "preflight is not PASS", errors)
    require(inputs["preflight"].get("ancestors", {}).get("main") is True,
            "main is not an ancestor", errors)
    require(inputs["preflight"].get("ancestors", {}).get("p8e-pass") is True,
            "p8e-pass is not an ancestor", errors)
    require(inputs["preflight"].get("ancestors", {}).get("p9-z7010-2lane-pass") is True,
            "p9-z7010-2lane-pass is not an ancestor", errors)
    require(inputs["blocker"].get("blocker_id") == "P10-SAFETY-POWERUP-001",
            "severe blocker identity mismatch", errors)

    regression = {item["test_id"]: item for item in inputs["regression"].get("results", [])}
    for test_id in (
        "P10-RTL-DUAL-INDEPENDENT-ENDPOINT",
        "P10-REGRESSION-P9-LEGACY-MONOLITHIC",
        "P10-REGRESSION-P9-RUNNER-UNIT",
        "P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY",
    ):
        require(regression.get(test_id, {}).get("status") == "PASS",
                f"missing/failing regression {test_id}", errors)

    functional_roles = {item["role"]: item for item in inputs["functional"].get("roles", [])}
    runtime_roles = {item["role"]: item for item in inputs["runtime"].get("roles", [])}
    shutdown_roles = {item["role"]: item for item in inputs["shutdown"].get("roles", [])}
    for role, value in (("fixed", "1"), ("rotating", "2")):
        require(functional_roles.get(role, {}).get("markers", {}).get("P10_ENDPOINT_ROLE_VALUE") == value,
                f"functional role binding mismatch: {role}", errors)
        require(runtime_roles.get(role, {}).get("role_value") == int(value),
                f"runtime role binding mismatch: {role}", errors)
        require(shutdown_roles.get(role, {}).get("status") == "PASS",
                f"shutdown build missing: {role}", errors)
    records = artifact_records(inputs, errors)
    require(len(records) == 10, f"expected 10 frozen artifacts, got {len(records)}", errors)
    require(len({item["path"] for item in records}) == len(records),
            "artifact paths are not unique", errors)

    source_checks = {
        "role_separated_wrapper": "ENDPOINT_ROLE" in (
            ROOT / "rtl/p10_axi_dma_endpoint_peripheral_bd.v").read_text(encoding="utf-8"),
        "two_endpoint_testbench": all(token in (
            ROOT / "sim/tb/tb_p10_dual_endpoint_pair.sv").read_text(encoding="utf-8")
            for token in ("fixed_endpoint", "rotating_endpoint")),
        "local_dma_per_xsa": all(
            role.get("xsa_audit", {}).get("checks", {}).get("dma_base") is True
            for role in functional_roles.values()),
        "ethernet_disabled": all(
            role.get("xsa_audit", {}).get("checks", {}).get("ethernet_disabled") is True
            for role in functional_roles.values()),
        "role_build_ids_differ": functional_roles.get("fixed", {}).get("markers", {}).get(
            "P10_ENDPOINT_ROLE_VALUE") != functional_roles.get("rotating", {}).get(
            "markers", {}).get("P10_ENDPOINT_ROLE_VALUE"),
        "runtime_artifacts_role_distinct": runtime_roles.get("fixed", {}).get(
            "artifacts", {}).get("elf", {}).get("sha256") != runtime_roles.get(
            "rotating", {}).get("artifacts", {}).get("elf", {}).get("sha256"),
    }
    for name, passed in source_checks.items():
        require(passed, f"architecture source check failed: {name}", errors)

    expected_methodology = {
        "LUTAR-1": 3,
        "PDRC-190": 32,
        "TIMING-9": 1,
        "TIMING-18": 6,
    }
    cdc_audit_roles: dict[str, dict[str, Any]] = {}
    bus_skew_material: dict[str, tuple[Path, Path]] = {}
    for role in ("fixed", "rotating"):
        role_record = functional_roles.get(role, {})
        cdc_path = summary_report(role_record, "post_route_cdc.rpt", errors)
        methodology_path = summary_report(
            role_record, "post_route_methodology.rpt", errors)
        cdc_text = cdc_path.read_text(
            encoding="utf-8", errors="replace") if cdc_path.is_file() else ""
        methodology_text = methodology_path.read_text(
            encoding="utf-8", errors="replace") if methodology_path.is_file() else ""

        cdc_counts = cdc_summary_counts(cdc_text)
        require(set(cdc_counts) == {"CDC-3", "CDC-15"},
                f"unexpected CDC summary rows for {role}: {sorted(cdc_counts)}", errors)
        require(cdc_counts.get("CDC-3") == {"severity": "Info", "count": 68},
                f"unexpected CDC-3 summary for {role}", errors)
        require(cdc_counts.get("CDC-15") == {"severity": "Warning", "count": 74},
                f"unexpected CDC-15 summary for {role}", errors)
        cdc15_rows = [
            line.strip() for line in cdc_text.splitlines()
            if re.match(r"^\s*\d+\s+CDC-15\s+Warning\s+", line)
        ]
        require(len(cdc15_rows) == cdc_counts.get("CDC-15", {}).get("count"),
                f"CDC-15 detail count mismatch for {role}", errors)
        non_vendor_cdc15 = [
            line for line in cdc15_rows
            if "axis_clock_converter" not in line or "xpm_fifo_async" not in line
        ]
        critical_or_error_count = sum(
            item["count"] for item in cdc_counts.values()
            if item["severity"] in {"Critical", "Error"}
        )
        unexpected_warning_count = sum(
            item["count"] for rule, item in cdc_counts.items()
            if item["severity"] == "Warning" and rule != "CDC-15"
        )
        unsafe_cdc_count = (
            critical_or_error_count + unexpected_warning_count + len(non_vendor_cdc15)
        )
        require(unsafe_cdc_count == 0, f"unsafe CDC found for {role}", errors)

        method_counts = methodology_counts(methodology_text)
        require(method_counts == expected_methodology,
                f"methodology warning inventory mismatch for {role}: {method_counts}", errors)
        lutar_blocks = issue_blocks(methodology_text, "LUTAR-1")
        pdrc_blocks = issue_blocks(methodology_text, "PDRC-190")
        timing9_blocks = issue_blocks(methodology_text, "TIMING-9")
        timing18_blocks = issue_blocks(methodology_text, "TIMING-18")
        require(len(lutar_blocks) == expected_methodology["LUTAR-1"],
                f"LUTAR-1 detail count mismatch for {role}", errors)
        require(len(pdrc_blocks) == expected_methodology["PDRC-190"],
                f"PDRC-190 detail count mismatch for {role}", errors)
        require(len(timing9_blocks) == expected_methodology["TIMING-9"],
                f"TIMING-9 detail count mismatch for {role}", errors)
        require(len(timing18_blocks) == expected_methodology["TIMING-18"],
                f"TIMING-18 detail count mismatch for {role}", errors)
        lutar_vendor_only = all(
            "hp0_interconnect" in block
            and "axi3_conv_inst" in block
            and "p10_endpoint_0" not in block
            for block in lutar_blocks
        )
        pdrc_vendor_only = all("/axi_dma_0/" in block for block in pdrc_blocks)
        require(lutar_vendor_only,
                f"non-vendor or endpoint-local LUTAR-1 warning for {role}", errors)
        require(pdrc_vendor_only,
                f"non-AXI-DMA PDRC-190 warning for {role}", errors)
        external_ports = sorted(set(re.findall(
            r"(?:input|output) delay is missing on (\S+) relative",
            "\n".join(timing18_blocks),
        )))
        require(len(external_ports) == expected_methodology["TIMING-18"],
                f"external I/O timing port inventory mismatch for {role}", errors)
        markers = role_record.get("markers", {})
        require(markers.get("P10_CDC_CRITICAL_COUNT") == "0",
                f"functional CDC critical marker is not zero for {role}", errors)
        require(markers.get("P10_METHODOLOGY_CRITICAL_COUNT") == "0",
                f"methodology critical marker is not zero for {role}", errors)
        require(markers.get("P10_REQP_1839_COUNT") == "0",
                f"REQP-1839 marker is not zero for {role}", errors)

        bus_source = BUS_SKEW_SOURCES[role]
        bus_destination = (
            ROOT / "evidence/generated/vivado/p10_ax7020_functional"
            / role / "post_route_bus_skew.rpt"
        )
        require(bus_source.is_file(),
                f"missing routed bus-skew report for {role}: {bus_source}", errors)
        bus_text = bus_source.read_text(
            encoding="utf-8", errors="replace") if bus_source.is_file() else ""
        bus_entries = [
            {"result": match.group(1), "slack_ns": float(match.group(2))}
            for match in re.finditer(
                r"Slack \((MET|VIOLATED)\)\s*:\s*(-?\d+(?:\.\d+)?)ns",
                bus_text,
            )
        ]
        require(len(bus_entries) == 9,
                f"expected 9 bus-skew constraints for {role}, got {len(bus_entries)}",
                errors)
        require(bus_entries and all(item["result"] == "MET" for item in bus_entries),
                f"bus-skew violation for {role}", errors)
        minimum_bus_skew_slack = min(
            (item["slack_ns"] for item in bus_entries), default=float("-inf"))
        require(minimum_bus_skew_slack >= 0.0,
                f"negative bus-skew slack for {role}", errors)
        require("Design       : p10_ps_system_wrapper" in bus_text,
                f"unexpected bus-skew design for {role}", errors)
        bus_skew_material[role] = (bus_source, bus_destination)

        cdc_audit_roles[role] = {
            "status": "PASS_WITH_DOCUMENTED_VENDOR_WARNINGS_AND_EXTERNAL_IO_GAP",
            "cdc": {
                "summary": cdc_counts,
                "cdc_15_detail_count": len(cdc15_rows),
                "cdc_15_vendor_axis_clock_converter_xpm_fifo_count": (
                    len(cdc15_rows) - len(non_vendor_cdc15)
                ),
                "non_vendor_cdc_15_count": len(non_vendor_cdc15),
                "critical_or_error_count": critical_or_error_count,
                "unexpected_warning_count": unexpected_warning_count,
                "unsafe_cdc_count": unsafe_cdc_count,
                "report": {
                    "path": rel(cdc_path) if cdc_path.is_file() else None,
                    "sha256": sha256(cdc_path) if cdc_path.is_file() else None,
                },
            },
            "methodology": {
                "warning_counts": method_counts,
                "warning_total": sum(method_counts.values()),
                "critical_count": int(markers.get(
                    "P10_METHODOLOGY_CRITICAL_COUNT", "-1")),
                "reqp_1839_count": int(markers.get("P10_REQP_1839_COUNT", "-1")),
                "lutar_1_classification": (
                    "AMD_HP0_AXI4_TO_AXI3_INTERCONNECT_GENERATED_STRUCTURE"
                ),
                "lutar_1_vendor_only": lutar_vendor_only,
                "p10_endpoint_lutar_1_count": sum(
                    "p10_endpoint_0" in block for block in lutar_blocks),
                "pdrc_190_classification": "AMD_AXI_DMA_GENERATED_STRUCTURE",
                "pdrc_190_vendor_only": pdrc_vendor_only,
                "timing_9_classification": "COVERED_BY_DETAILED_REPORT_CDC_AUDIT",
                "timing_18_classification": "OPEN_EXTERNAL_TFDU_IO_TIMING_GAP",
                "external_io_ports_without_delay_constraints": external_ports,
                "report": {
                    "path": rel(methodology_path) if methodology_path.is_file() else None,
                    "sha256": (
                        sha256(methodology_path) if methodology_path.is_file() else None
                    ),
                },
            },
            "bus_skew": {
                "constraint_count": len(bus_entries),
                "all_constraints_met": bool(bus_entries) and all(
                    item["result"] == "MET" for item in bus_entries),
                "minimum_slack_ns": minimum_bus_skew_slack,
                "entries": bus_entries,
                "scratch_source_path": str(bus_source),
            },
            "external_io_timing_closed": False,
            "hardware_timing_admission": False,
        }

    if errors:
        for error in errors:
            print(f"P10_EVIDENCE_ERROR: {error}", file=sys.stderr)
        return 1

    generated_at = datetime.now(timezone.utc).isoformat()
    for role, (source, destination) in bus_skew_material.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        cdc_audit_roles[role]["bus_skew"]["report"] = {
            "path": rel(destination),
            "sha256": sha256(destination),
            "bytes": destination.stat().st_size,
        }

    cdc_audit = {
        "schema_version": 1,
        "test_id": "P10-CDC-METHODOLOGY-BUS-SKEW-AUDIT",
        "status": "PASS_WITH_DOCUMENTED_VENDOR_WARNINGS_AND_EXTERNAL_IO_GAP",
        "scope": "OFFLINE_POST_ROUTE_REPORT_AUDIT_ONLY",
        "generated_at_utc": generated_at,
        "source_commit": source_commit,
        "source_worktree_dirty": False,
        "hardware_actions_executed": False,
        "hardware_scope_promoted": False,
        "unsafe_cdc_count": sum(
            role["cdc"]["unsafe_cdc_count"] for role in cdc_audit_roles.values()),
        "all_bus_skew_constraints_met": all(
            role["bus_skew"]["all_constraints_met"]
            for role in cdc_audit_roles.values()),
        "external_io_timing_closed": False,
        "roles": cdc_audit_roles,
        "boundary": (
            "All detailed CDC warnings are confined to generated AXI-Stream clock-"
            "converter XPM asynchronous FIFOs, and all routed bus-skew constraints "
            "have positive slack. Generated HP0 interconnect and AXI DMA methodology "
            "warnings are retained. TFDU external input/output delays remain undefined, "
            "so this audit does not admit hardware or close external I/O timing."
        ),
    }
    CDC_JSON.write_text(json.dumps(cdc_audit, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    cdc_rows = "\n".join(
        "| {role} | {info} | {warning} | {unsafe} | {lutar} | {pdrc} | {timing9} | "
        "{timing18} | {skew:.3f} |".format(
            role=role,
            info=data["cdc"]["summary"]["CDC-3"]["count"],
            warning=data["cdc"]["summary"]["CDC-15"]["count"],
            unsafe=data["cdc"]["unsafe_cdc_count"],
            lutar=data["methodology"]["warning_counts"]["LUTAR-1"],
            pdrc=data["methodology"]["warning_counts"]["PDRC-190"],
            timing9=data["methodology"]["warning_counts"]["TIMING-9"],
            timing18=data["methodology"]["warning_counts"]["TIMING-18"],
            skew=data["bus_skew"]["minimum_slack_ns"],
        )
        for role, data in cdc_audit_roles.items()
    )
    CDC_MD.write_text(
        "# P10 CDC, methodology, and bus-skew audit\n\n"
        "Scoped result: "
        "`PASS_WITH_DOCUMENTED_VENDOR_WARNINGS_AND_EXTERNAL_IO_GAP`.\n\n"
        "| Role | CDC-3 info | CDC-15 warning | Unsafe CDC | LUTAR-1 | PDRC-190 | "
        "TIMING-9 | TIMING-18 | Minimum bus-skew slack (ns) |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
        f"{cdc_rows}\n\n"
        "- Every CDC-15 detail is inside the generated AXI-Stream clock converter's "
        "XPM asynchronous FIFO; no non-vendor CDC-15 or critical/error CDC was found.\n"
        "- The three LUTAR-1 warnings per role are confined to the generated HP0 "
        "AXI4-to-AXI3 interconnect. No endpoint-local LUT async-reset warning remains.\n"
        "- The 32 PDRC-190 warnings per role are confined to generated AXI DMA "
        "register synchronization placement.\n"
        "- TIMING-9 is bounded by the detailed CDC audit and positive routed bus-skew "
        "results.\n"
        "- TIMING-18 remains open for six external TFDU ports per role. This is an "
        "explicit external-I/O timing gap and does not authorize hardware.\n"
        "- Hardware actions executed: `false`; hardware admission: `false`.\n",
        encoding="utf-8", newline="\n")
    current_paths = {item["path"] for item in records}
    superseded = []
    for path in sorted(p for p in (ROOT / "artifacts/p10").rglob("*") if p.is_file()):
        relative = rel(path)
        if relative not in current_paths:
            superseded.append({
                "path": relative,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "classification": "SUPERSEDED_INTERMEDIATE_OFFLINE_ARTIFACT_NOT_AUTHORIZED",
            })
    manifest = {
        "schema_version": 1,
        "manifest_id": "P10-OFFLINE-CONTENT-ADDRESSED-ARTIFACTS",
        "status": "PASS",
        "generated_at_utc": generated_at,
        "source_commit": source_commit,
        "hardware_actions_executed": False,
        "artifacts": records,
        "superseded_intermediate_artifacts": superseded,
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8", newline="\n")

    architecture = {
        "schema_version": 1,
        "test_id": "P10-DUAL-INDEPENDENT-ENDPOINT-ARCHITECTURE-AUDIT",
        "status": "PASS",
        "scope": "OFFLINE_RTL_SIMULATION_AND_ROLE_BOUND_BUILD_ONLY",
        "generated_at_utc": generated_at,
        "source_commit": source_commit,
        "source_worktree_dirty": False,
        "hardware_actions_executed": False,
        "hardware_scope_promoted": False,
        "requirement": {
            "requirement_id": "SYS-ARCH-001",
            "canonical_status": "PENDING",
            "offline_design_evidence": "PASS",
            "hardware_followup": "PENDING_P10_REMEDIATION_AND_HARDWARE_RUN",
        },
        "role_binding": {
            "fixed": {"logical_board_id": "AX7020-F", "deployment_role": 1,
                      "modules": ["F0", "F1"]},
            "rotating": {"logical_board_id": "AX7020-R", "deployment_role": 2,
                         "modules": ["R0", "R1"]},
        },
        "lanes": {"lane0": "F0-R0", "lane1": "F1-R1"},
        "independent_local_resources": [
            "PS", "DDR controller and DDR", "scatter-gather AXI DMA",
            "descriptor/session/retry state", "payload storage", "two TFDU paths",
        ],
        "cross_node_transport": "OPTICAL_DATA_AND_ACK_FRAMES_ONLY",
        "shared_ram": False,
        "ethernet": False,
        "source_checks": source_checks,
        "final_no_hardware_static_scan": {
            "status": "PASS",
            "path": rel(NO_HW_LOG),
            "sha256": sha256(NO_HW_LOG),
        },
        "portable_regression": rel(INPUTS["regression"]),
        "functional_build": rel(INPUTS["functional"]),
        "runtime_build": rel(INPUTS["runtime"]),
        "cdc_methodology_audit": {
            "status": cdc_audit["status"],
            "unsafe_cdc_count": cdc_audit["unsafe_cdc_count"],
            "all_bus_skew_constraints_met": (
                cdc_audit["all_bus_skew_constraints_met"]
            ),
            "external_io_timing_closed": cdc_audit["external_io_timing_closed"],
            "path": rel(CDC_JSON),
            "sha256": sha256(CDC_JSON),
        },
        "artifact_manifest": rel(MANIFEST_JSON),
        "artifact_manifest_sha256": sha256(MANIFEST_JSON),
        "architecture_document": rel(ARCH_DOC),
        "architecture_document_sha256": sha256(ARCH_DOC),
        "hardware_admission": False,
        "blocking_condition": "P10-SAFETY-POWERUP-001",
        "limitations": [
            "No physical fixed/rotating board identity was bound.",
            "No FPGA was programmed and no ELF was run.",
            "No real DDR, DMA, optical, reset-recovery, throughput, or duration result exists.",
            "No passive power-up Txd-low/SD-high guarantee is established.",
            "External TFDU input/output delay constraints remain undefined.",
        ],
    }
    ARCH_JSON.write_text(json.dumps(architecture, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    ARCH_MD.write_text(
        "# P10 dual-independent-endpoint architecture audit\n\n"
        "- Scoped result: `PASS` (`OFFLINE_RTL_SIMULATION_AND_ROLE_BOUND_BUILD_ONLY`)\n"
        "- `SYS-ARCH-001`: remains `PENDING` for physical dual-node evidence.\n"
        "- Fixed role: `AX7020-F`, `DEPLOYMENT_ROLE=1`, F0/F1.\n"
        "- Rotating role: `AX7020-R`, `DEPLOYMENT_ROLE=2`, R0/R1.\n"
        "- No shared RAM or Ethernet path exists between endpoint instances.\n"
        "- Portable P10 and legacy P9 regressions: `PASS`.\n"
        "- Fixed/rotating functional bit/XSA and BSP/ELF builds: `PASS`.\n"
        "- Detailed CDC audit: unsafe CDC `0`; every routed bus-skew constraint has "
        "positive slack.\n"
        "- External TFDU I/O timing: `OPEN` (six TIMING-18 warnings per role).\n"
        "- Hardware actions executed: `false`.\n"
        "- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).\n\n"
        f"Artifact manifest: `{rel(MANIFEST_JSON)}` (`{sha256(MANIFEST_JSON)}`)\n",
        encoding="utf-8", newline="\n")

    mandatory = {
        "four_direction_raw": "NOT_RUN_SEVERE_BLOCKER",
        "lane0_4mbps": "NOT_RUN_SEVERE_BLOCKER",
        "lane1_4mbps": "NOT_RUN_SEVERE_BLOCKER",
        "two_lane_8mbps_raw": "NOT_RUN_SEVERE_BLOCKER",
        "selective_repeat_sack": "PASS_OFFLINE_SIMULATION_ONLY_HARDWARE_NOT_RUN",
        "dma_ddr_cache_fixed": "NOT_RUN_SEVERE_BLOCKER",
        "dma_ddr_cache_rotating": "NOT_RUN_SEVERE_BLOCKER",
        "dual_independent_ps": "PASS_OFFLINE_BUILD_ONLY_HARDWARE_NOT_RUN",
        "no_shared_ram": "PASS_OFFLINE_ARCHITECTURE_AND_SIMULATION_HARDWARE_NOT_RUN",
        "f_to_r_object": "NOT_RUN_SEVERE_BLOCKER",
        "r_to_f_object": "NOT_RUN_SEVERE_BLOCKER",
        "object_sha256": "NONE_NO_HARDWARE_RUN",
        "endpoint_reboot_recovery": "NOT_RUN_SEVERE_BLOCKER",
        "stationary_30min": "NOT_RUN_SEVERE_BLOCKER",
        "application_goodput_f_to_r_bps": "NOT_MEASURED_NO_HARDWARE_RUN",
        "application_goodput_r_to_f_bps": "NOT_MEASURED_NO_HARDWARE_RUN",
        "shutdown_fixed": "NOT_EXECUTED_SEVERE_BLOCKER_OFFLINE_IMAGE_BUILD_PASS",
        "shutdown_rotating": "NOT_EXECUTED_SEVERE_BLOCKER_OFFLINE_IMAGE_BUILD_PASS",
    }
    generated_evidence = [
        rel(INPUTS["preflight"]), rel(INPUTS["regression"]),
        rel(INPUTS["shutdown"]), rel(INPUTS["functional"]),
        rel(INPUTS["runtime"]), rel(CDC_JSON), rel(CDC_MD),
        *[
            data["bus_skew"]["report"]["path"]
            for data in cdc_audit_roles.values()
        ],
        rel(ARCH_JSON), rel(ARCH_MD),
        rel(MANIFEST_JSON), rel(INPUTS["blocker"]), rel(NO_HW_LOG),
        rel(FINAL_MD), rel(FINAL_JSON),
    ]
    final = {
        "schema_version": 2,
        "test_id": "P10-FASTTRACK-FINAL-SUMMARY",
        "generated_at_utc": generated_at,
        "stage": "P10_FASTTRACK_AX7020_DUAL_NODE_2LANE_NO_ETHERNET",
        "status": "PARTIAL",
        "source_commit": source_commit,
        "evidence_checkpoint": "COMMIT_CONTAINING_THIS_SUMMARY",
        "tag": None,
        "branch": BRANCH,
        "worktree": str(ROOT),
        "worktree_clean_after_evidence_commit_expected": True,
        "wiring_already_confirmed": True,
        "current_run_hardware_authorization": True,
        "offline_build_environment": {"NO_HARDWARE": 1,
                                      "CURRENT_RUN_HARDWARE_AUTHORIZATION": False},
        "hardware_actions_executed": False,
        "network_used": False,
        "no_hardware_movement": True,
        "max_lane_mask_used": "NONE_NO_HARDWARE_RUN",
        "allowed_lane_masks": ["0x1", "0x2", "0x3"],
        "fixed_board_id": "PENDING_PHYSICAL_ROLE_BINDING",
        "rotating_board_id": "PENDING_PHYSICAL_ROLE_BINDING",
        "logical_image_roles": {"fixed": "AX7020-F", "rotating": "AX7020-R"},
        "hardware_admission": False,
        "blocking_condition": "P10-SAFETY-POWERUP-001",
        "mandatory_results": mandatory,
        "offline_pass": [
            "Repository/main/P8E/P9 ancestry and concise preflight",
            "Confirmed independent AX7020 J10 wiring profiles and XDCs",
            "Two-instance dual-endpoint RTL simulation including both directions, both lanes, SACK, wrap, and retry",
            "Legacy P9 transport and P9 runner regressions",
            "Register-map P9-3 single-source verification",
            "Fixed and rotating shutdown bitstream builds",
            "Fixed and rotating functional synthesis/route/timing/DRC/CDC-severity builds",
            "Detailed CDC audit with unsafe CDC zero and positive routed bus-skew slack; external TFDU I/O timing remains open",
            "Role-bound fixed and rotating XSA/BSP/ELF builds",
            "Offline independent-node/no-shared-RAM architecture audit",
        ],
        "fail": [
            "P10-SAFETY-POWERUP-001: passive Txd-low and SD-high are not established for unconfigured/reset/open/partial-power states",
            "P10-RX-B-R29-001: J10-26/U13 1-kohm pull-down exceeds the supplied TFDU VOH guaranteed test load",
            "Physical board/module revision identity and unique F/R JTAG binding remain unverified",
            "All mandatory hardware acceptance stages are not run",
        ],
        "nonblocking_extensions": "NOT_RUN_BECAUSE_MANDATORY_HARDWARE_ADMISSION_FAILED",
        "generated_evidence": generated_evidence,
        "unchanged_pending_scopes": [
            "ETHERNET: DEFERRED", "SPI: PENDING",
            "PHYSICAL_GLOBAL_PERMIT: PENDING_D17", "EXTERNAL_TFDU_DUTY: PENDING",
            "HANDOVER: PENDING_P11", "8X32: PENDING_P12", "600RPM: PENDING_P13",
            "PRODUCT_FINAL: PENDING",
        ],
        "required_user_resolution": [
            "Provide as-built evidence and component values proving a passive pull-down on every Txd and passive pull-up on every SD, including any existing harness bias; or authorize a documented fail-safe hardware revision/rewire.",
            "Resolve or electrically validate the J10-26/U13 Rxd 1-kohm pull-down against the exact TFDU small-board output.",
            "Provide physical revision/marking evidence that uniquely binds AX7020-F and AX7020-R before any programming.",
        ],
        "next_recommended_stage": "P10_REMEDIATION",
    }
    FINAL_JSON.write_text(json.dumps(final, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8", newline="\n")
    FINAL_MD.write_text(
        "# P10 fast-track final summary\n\n"
        "```text\n"
        "P10_FASTTRACK_AX7020_DUAL_NODE_2LANE_NO_ETHERNET:\nPARTIAL\n\n"
        f"P10_SOURCE_COMMIT:\n{source_commit}\n\n"
        "P10_EVIDENCE_CHECKPOINT:\nCOMMIT_CONTAINING_THIS_SUMMARY\n\n"
        "P10_TAG:\nNONE\n\nWORKTREE_CLEAN:\nEXPECTED_AFTER_EVIDENCE_COMMIT\n\n"
        "WIRING_ALREADY_CONFIRMED: true\nCURRENT_RUN_HARDWARE_AUTHORIZATION: true\n"
        "HARDWARE_ACTIONS_EXECUTED: false\nNETWORK_USED: false\nNO_HARDWARE_MOVEMENT: true\n"
        "MAX_LANE_MASK_USED: NONE_NO_HARDWARE_RUN\n\n"
        "FIXED_BOARD_ID:\nPENDING_PHYSICAL_ROLE_BINDING\n\n"
        "ROTATING_BOARD_ID:\nPENDING_PHYSICAL_ROLE_BINDING\n\n"
        "FOUR_DIRECTION_RAW:\nNOT_RUN_SEVERE_BLOCKER\n"
        "LANE0_4MBPS:\nNOT_RUN_SEVERE_BLOCKER\n"
        "LANE1_4MBPS:\nNOT_RUN_SEVERE_BLOCKER\n"
        "TWO_LANE_8MBPS_RAW:\nNOT_RUN_SEVERE_BLOCKER\n\n"
        "SELECTIVE_REPEAT_SACK:\nPASS_OFFLINE_SIMULATION_ONLY_HARDWARE_NOT_RUN\n"
        "DMA_DDR_CACHE_FIXED:\nNOT_RUN_SEVERE_BLOCKER\n"
        "DMA_DDR_CACHE_ROTATING:\nNOT_RUN_SEVERE_BLOCKER\n"
        "DUAL_INDEPENDENT_PS:\nPASS_OFFLINE_BUILD_ONLY_HARDWARE_NOT_RUN\n"
        "NO_SHARED_RAM:\nPASS_OFFLINE_ARCHITECTURE_AND_SIMULATION_HARDWARE_NOT_RUN\n"
        "F_TO_R_OBJECT:\nNOT_RUN_SEVERE_BLOCKER\nR_TO_F_OBJECT:\nNOT_RUN_SEVERE_BLOCKER\n"
        "OBJECT_SHA256:\nNONE_NO_HARDWARE_RUN\nENDPOINT_REBOOT_RECOVERY:\nNOT_RUN_SEVERE_BLOCKER\n"
        "STATIONARY_30MIN:\nNOT_RUN_SEVERE_BLOCKER\n\n"
        "APPLICATION_GOODPUT_F_TO_R_BPS:\nNOT_MEASURED_NO_HARDWARE_RUN\n"
        "APPLICATION_GOODPUT_R_TO_F_BPS:\nNOT_MEASURED_NO_HARDWARE_RUN\n\n"
        "SHUTDOWN_FIXED:\nNOT_EXECUTED_SEVERE_BLOCKER_OFFLINE_IMAGE_BUILD_PASS\n"
        "SHUTDOWN_ROTATING:\nNOT_EXECUTED_SEVERE_BLOCKER_OFFLINE_IMAGE_BUILD_PASS\n\n"
        "PASS:\nOFFLINE_BUILD_SIMULATION_AND_ARCHITECTURE_ITEMS_IN_JSON\n"
        "FAIL:\nP10-SAFETY-POWERUP-001; P10-RX-B-R29-001; MANDATORY_HARDWARE_NOT_RUN\n"
        "NONBLOCKING_EXTENSIONS:\nNOT_RUN_BECAUSE_MANDATORY_HARDWARE_ADMISSION_FAILED\n"
        "GENERATED_EVIDENCE:\nevidence/generated/p10_fasttrack_final_summary.json\n"
        "UNCHANGED_PENDING_SCOPES:\nETHERNET; SPI; PHYSICAL_GLOBAL_PERMIT; EXTERNAL_TFDU_DUTY; HANDOVER; 8X32; 600RPM; PRODUCT_FINAL\n\n"
        "NEXT_RECOMMENDED_STAGE:\nP10_REMEDIATION\n"
        "```\n\n"
        "The fast-track authorization was recognized, but hardware admission failed closed at the severe "
        "power-up safety blocker.  Offline role-separated builds and portable regressions were completed; "
        "no hardware action, Ethernet use, movement, or optical emission occurred.\n",
        encoding="utf-8", newline="\n")
    print("P10_OFFLINE_EVIDENCE=PASS")
    print("P10_FASTTRACK_RESULT=PARTIAL")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
