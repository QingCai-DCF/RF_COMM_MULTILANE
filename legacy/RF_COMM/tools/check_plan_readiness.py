#!/usr/bin/env python3
"""Generate a stage readiness gate from current RF_COMM plan evidence.

This script is intentionally read-only with respect to design sources. It turns
the evidence audits into a concise GO/BLOCK report so hardware work does not
accidentally skip JTAG, RX, ACK, PC, soak, or DRC prerequisites.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from classify_2lane_physical_matrix import apply_required_links, classify_one


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
REQUIRED_2LANE_LINKS = ["A_TO_B_LANE0", "A_TO_B_LANE1", "B_TO_A_LANE0", "B_TO_A_LANE1"]


@dataclass
class Gate:
    gate_id: str
    status: str
    requirement: str
    evidence: str
    action: str


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="ignore")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="ignore")
    if data[:4096].count(b"\x00") > max(4, len(data[:4096]) // 10):
        return data.decode("utf-16le", errors="ignore")
    return data.decode("utf-8", errors="ignore")


def latest(pattern: str) -> Path | None:
    paths = list(ROOT.glob(pattern))
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def latest_any(*patterns: str) -> Path | None:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(ROOT.glob(pattern))
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path | None) -> object:
    if path is None or not path.exists():
        return None
    return json.loads(read_text(path))


def latest_physical_matrix_rows() -> tuple[list[dict[str, object]], str, str]:
    json_paths = sorted(
        REPORTS.glob("2lane_matrix_safe_*.ila_matrix.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    latest_by_link: dict[str, dict[str, object]] = {}
    used_sources: list[Path] = []

    for path in json_paths:
        analyses = load_json(path)
        if not isinstance(analyses, list):
            continue
        source_used = False
        for item in analyses:
            if not isinstance(item, dict):
                continue
            row = classify_one(item)
            expected = str(row.get("expected", "")).upper()
            if expected not in REQUIRED_2LANE_LINKS or expected in latest_by_link:
                continue
            row["source"] = str(path)
            latest_by_link[expected] = row
            source_used = True
        if source_used:
            used_sources.append(path)
        if all(link in latest_by_link for link in REQUIRED_2LANE_LINKS):
            break

    rows = [latest_by_link[link] for link in REQUIRED_2LANE_LINKS if link in latest_by_link]
    gated_rows, physical_overall = apply_required_links(rows, REQUIRED_2LANE_LINKS)
    details = []
    for row in gated_rows:
        details.append(
            "{expected}:{classification}:tx={tx}:rx={rx}".format(
                expected=row.get("expected", ""),
                classification=row.get("classification", ""),
                tx=row.get("tx_pulses", ""),
                rx=row.get("rx_pulses", ""),
            )
        )
    return gated_rows, physical_overall, "; ".join([rel(path) for path in used_sources] + details)


def physical_gate_selftest_status() -> tuple[bool, str, str]:
    path = REPORTS / "physical_matrix_gate_selftest_current.json"
    payload = load_json(path)
    if not isinstance(payload, dict):
        return False, "MISSING", rel(path)
    overall = str(payload.get("overall", "MISSING"))
    failures = int(payload.get("failures") or 0)
    cases = int(payload.get("cases") or 0)
    checks = int(payload.get("checks") or 0)
    no_side_effects = (
        bool(payload.get("no_hardware_programming"))
        and bool(payload.get("no_uart_write"))
        and bool(payload.get("no_tfdu_drive"))
    )
    passed = overall == "PASS" and failures == 0 and cases >= 4 and checks >= 8 and no_side_effects
    evidence = f"{rel(path)}:overall={overall}:cases={cases}:checks={checks}:failures={failures}:no_side_effects={int(no_side_effects)}"
    return passed, overall, evidence


def ila_analyzer_selftest_status() -> tuple[bool, str, str]:
    path = REPORTS / "ila_analyzer_selftest_current.json"
    payload = load_json(path)
    if not isinstance(payload, dict):
        return False, "MISSING", rel(path)
    overall = str(payload.get("overall", "MISSING"))
    failures = int(payload.get("failures") or 0)
    cases = int(payload.get("cases") or 0)
    no_side_effects = (
        bool(payload.get("no_hardware_programming"))
        and bool(payload.get("no_uart_write"))
        and bool(payload.get("no_tfdu_drive"))
    )
    passed = overall == "PASS" and failures == 0 and cases >= 4 and no_side_effects
    evidence = f"{rel(path)}:overall={overall}:cases={cases}:failures={failures}:no_side_effects={int(no_side_effects)}"
    return passed, overall, evidence


def physical_failure_snapshot_status() -> tuple[str, str]:
    path = REPORTS / "2lane_physical_failure_snapshot_current.json"
    payload = load_json(path)
    if not isinstance(payload, dict):
        return "MISSING", rel(path)
    overall = str(payload.get("overall", "MISSING"))
    failures = int(payload.get("failures") or 0)
    far_rx_missing_with_near_echo = int(payload.get("far_rx_missing_with_near_echo") or 0)
    no_side_effects = (
        bool(payload.get("no_hardware_programming"))
        and bool(payload.get("no_uart_write"))
        and bool(payload.get("no_tfdu_drive"))
    )
    evidence = (
        f"{rel(path)}:overall={overall}:failures={failures}:"
        f"far_rx_missing_with_near_echo={far_rx_missing_with_near_echo}:"
        f"no_side_effects={int(no_side_effects)}"
    )
    return overall, evidence


def active_artifact_guard_status() -> tuple[bool, str, str, str]:
    path = latest("reports/active_artifact_guard_current_*.json")
    payload = load_json(path)
    if not isinstance(payload, dict):
        return False, "MISSING", "MISSING", rel(path)
    stage = str(payload.get("stage", "MISSING"))
    result = str(payload.get("result", "MISSING"))
    reason = str(payload.get("reason", ""))
    passed = result == "PASS" and stage == "P1_2LANE_ILA_BASELINE"
    evidence = f"{rel(path)}:stage={stage}:result={result}:reason={reason}"
    return passed, stage, result, evidence


def item_map(items: object) -> dict[str, dict[str, str]]:
    if not isinstance(items, list):
        return {}
    out: dict[str, dict[str, str]] = {}
    for item in items:
        if isinstance(item, dict):
            key = item.get("item_id") or item.get("id")
            if key:
                out[str(key)] = {str(k): str(v) for k, v in item.items()}
    return out


def item_status(items: dict[str, dict[str, str]], key: str) -> str:
    return items.get(key, {}).get("status", "MISSING")


def item_evidence(items: dict[str, dict[str, str]], key: str) -> str:
    return items.get(key, {}).get("evidence", "")


def contains(text: str, pattern: str) -> bool:
    return re.search(pattern, text, re.MULTILINE | re.DOTALL) is not None


def hw_preflight_pass(text: str) -> bool:
    return (
        contains(text, r"(?m)^VIVADO_MATCH=HW_PREFLIGHT_RESULT PASS\b")
        and contains(text, r"(?m)^VIVADO_MATCH=HW_PREFLIGHT_ZYNQ\b")
    )


def hw_preflight_fail(text: str) -> bool:
    return contains(
        text,
        r"(?m)^(?:VIVADO_MATCH=HW_PREFLIGHT_RESULT FAIL_NO_TARGET|P1_LANE_MAPPING_BLOCKED_NO_PROGRAMMING=1|PREFLIGHT_PASS_PARSED=0)\b",
    )


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join("" if cell is None else str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def collect_gates() -> tuple[list[Gate], dict[str, str]]:
    completion_path = latest("reports/plan_completion_audit_current_*.json")
    item_path = latest("reports/plan_item_audit_current_*.json")
    drc_path = latest("reports/drc_triage_current_*.json")
    drc_release_gate_path = latest("reports/drc_release_gate_current.json")
    latest_preflight = latest("reports/hw_target_preflight_*.summary.txt")
    latest_p1 = latest("reports/p1_lane_mapping_matrix_safe_*.summary.txt")
    latest_jtag_diag = latest("reports/jtag_usb_diag_*.summary.txt")
    latest_jtag_blocker = latest_any("reports/jtag_blocker_current_*.md", "reports/jtag_blocker_analysis_current_*.md")
    latest_jtag_checklist = latest("reports/jtag_recovery_checklist_current_*.md")
    physical_rows, physical_overall, physical_evidence = latest_physical_matrix_rows()
    physical_selftest_pass, physical_selftest_overall, physical_selftest_evidence = physical_gate_selftest_status()
    analyzer_selftest_pass, analyzer_selftest_overall, analyzer_selftest_evidence = ila_analyzer_selftest_status()
    physical_failure_snapshot_overall, physical_failure_snapshot_evidence = physical_failure_snapshot_status()
    active_guard_pass, active_guard_stage, active_guard_result, active_guard_evidence = active_artifact_guard_status()

    completion = item_map(load_json(completion_path))
    items = item_map(load_json(item_path))
    drc = load_json(drc_path)
    drc_release_gate = load_json(drc_release_gate_path)

    preflight_text = "\n".join(read_text(path) for path in (latest_preflight, latest_p1) if path is not None)
    jtag_pass = hw_preflight_pass(preflight_text)
    jtag_fail = hw_preflight_fail(preflight_text)

    drc_blocking: list[str] = []
    if isinstance(drc, dict) and isinstance(drc.get("rules"), list):
        for rule in drc["rules"]:
            if not isinstance(rule, dict):
                continue
            disposition = str(rule.get("disposition", ""))
            if disposition in {
                "BLOCK_RELEASE",
                "FIX_CONSTRAINTS_BEFORE_RELEASE",
                "OPTIMIZE_BEFORE_4_OR_8_LANE",
                "REVIEW_DMA_FIFO_COLLISION",
            }:
                drc_blocking.append(f"{rule.get('rule')}:{disposition}")
    else:
        drc_blocking.append("NO_DRC_TRIAGE_JSON")
    drc_release_metadata = drc_release_gate.get("metadata") if isinstance(drc_release_gate, dict) else {}
    drc_release_overall = str(drc_release_metadata.get("overall", "NO_DRC_RELEASE_GATE"))
    drc_release_ready = str(drc_release_metadata.get("release_ready", "0"))
    drc_release_debug_can_continue = str(drc_release_metadata.get("debug_can_continue", "0"))

    offline_required = [
        "C0",
        "P0-1",
        "SIM-2L",
        "PG-2L-ILA",
        "ARTIFACTS",
        "BOOT-AUDIT",
        "P1-1-TOOLS",
        "P0-RX-TOOL",
        "P2-OFFLINE",
        "ACTIVE-ARTIFACT-GUARD",
    ]
    offline_missing = [key for key in offline_required if item_status(completion, key) != "PASS"]

    gates: list[Gate] = []
    gates.append(
        Gate(
            "G0_OFFLINE_BASELINE",
            "PASS" if (not offline_missing and active_guard_pass) else "BLOCK",
            "Constraint, evidence freeze, simulation, current build, artifacts, boot audit, and safe runners are ready.",
            f"{rel(completion_path)}; active_guard={active_guard_stage}/{active_guard_result}; {active_guard_evidence}",
            (
                "Keep offline gates green after any RTL/PS/host/tooling change."
                if (not offline_missing and active_guard_pass)
                else (
                    "Restore or rebuild the P1 2-lane ILA baseline so tools/check_active_artifact_stage.py passes before any P1 hardware matrix run."
                    if not active_guard_pass
                    else f"Fix non-PASS audit items: {', '.join(offline_missing)}."
                )
            ),
        )
    )
    gates.append(
        Gate(
            "G1_JTAG_ACCESS",
            "PASS" if jtag_pass else ("BLOCK" if jtag_fail else "UNKNOWN"),
            "Vivado Hardware Manager must enumerate the Zynq target before programming or TFDU drive.",
            "; ".join(rel(path) for path in (latest_preflight, latest_p1, latest_jtag_diag, latest_jtag_blocker, latest_jtag_checklist) if path is not None),
            (
                "Run tools/run_p1_lane_mapping_matrix_safe.ps1 -StopOnFail after JTAG recovery."
                if not jtag_pass
                else (
                    "JTAG is available; restore/rebuild the P1 baseline before programming a P1 lane matrix."
                    if not active_guard_pass
                    else "Run P1 lane mapping matrix first."
                )
            ),
        )
    )

    p1_hw = item_status(completion, "P1-1-HW")
    physical_gate_pass = physical_selftest_pass and physical_overall == "PASS_REQUIRED_LINKS"
    physical_gate_missing = physical_overall in {"NO_EVIDENCE", "BLOCK_REQUIRED_LINK_EVIDENCE_MISSING"}
    physical_gate_blocked = physical_overall.startswith("BLOCK_") or physical_overall.startswith("FAIL_")
    physical_failed = [
        f"{row.get('expected')}:{row.get('classification')} tx={row.get('tx_pulses')} rx={row.get('rx_pulses')}"
        for row in physical_rows
        if row.get("classification") != "PASS_PHYSICAL_RAW_PULSE"
    ]
    gates.append(
        Gate(
            "G2_LANE_MAPPING",
            "PASS"
            if physical_gate_pass
            else ("BLOCK" if (not active_guard_pass or not physical_selftest_pass or not analyzer_selftest_pass or not jtag_pass or physical_gate_blocked or p1_hw.startswith("FAIL")) else "READY"),
            "Fresh lane0/lane1 A->B and B->A physical matrix must be captured and classified by self-tested analyzer/gate tooling.",
            f"active_guard={active_guard_stage}/{active_guard_result}; {active_guard_evidence}; analyzer_selftest={analyzer_selftest_overall}; {analyzer_selftest_evidence}; gate_selftest={physical_selftest_overall}; {physical_selftest_evidence}; failure_snapshot={physical_failure_snapshot_overall}; {physical_failure_snapshot_evidence}; physical_overall={physical_overall}; {physical_evidence}"
            if not physical_gate_missing
            else f"active_guard={active_guard_stage}/{active_guard_result}; {active_guard_evidence}; analyzer_selftest={analyzer_selftest_overall}; {analyzer_selftest_evidence}; gate_selftest={physical_selftest_overall}; {physical_selftest_evidence}; failure_snapshot={physical_failure_snapshot_overall}; {physical_failure_snapshot_evidence}; " + (item_evidence(completion, "P1-1-HW") or rel(latest_p1)),
            (
                "Restore or rebuild the P1 2-lane ILA baseline before rerunning the full P1 lane matrix."
                if not active_guard_pass
                else (
                    "Fix ILA analyzer self-test before using lane-mapping evidence."
                    if not analyzer_selftest_pass
                    else (
                        "Fix physical matrix gate self-test before using lane-mapping evidence."
                        if not physical_selftest_pass
                        else (
                            "Use reports/2lane_physical_failure_snapshot_current.md, physically adjust the failed optical path, then run tools/run_failed_2lane_links_safe.ps1 -AllowTraffic -PhysicalAdjusted -PhysicalAdjustmentNote \"describe_adjustment\" to retest only failed links before protocol restore: " + ", ".join(physical_failed)
                            if physical_failed
                            else (
                                "Capture fresh A->B/B->A lane0/lane1 ILA matrices, then classify with tools/classify_2lane_physical_matrix.py."
                                if physical_gate_missing
                                else "Do not run 2-lane protocol restore until mapping matrix has fresh PASS evidence."
                            )
                        )
                    )
                )
            ),
        )
    )

    m6 = item_status(completion, "M6")
    gates.append(
        Gate(
            "G3_2LANE_PROTOCOL",
            "PASS" if m6 == "PASS" else ("BLOCK" if not physical_gate_pass else "READY"),
            "Current 2-lane protocol must pass on real hardware with low loss and no deadlock.",
            item_evidence(completion, "M6"),
            "After mapping PASS, run RX root-cause/ACK-only before declaring 2-lane restored.",
        )
    )

    p2_board = item_status(completion, "P2-BOARD")
    p2_end = item_status(completion, "P2-END2END")
    gates.append(
        Gate(
            "G4_PS_PC_END_TO_END",
            "PASS" if p2_board == "PASS" and p2_end == "PASS" else ("BLOCK" if m6 != "PASS" else "READY"),
            "Real AX7010 PS/PC TCP/DHCP smoke and PC->PS->PL/IR->PS->PC loop must pass.",
            "; ".join(filter(None, [item_evidence(completion, "P2-BOARD"), item_evidence(completion, "P2-END2END")])),
            "Keep using offline PS/PC gates, but do not claim real TCP/DHCP until board smoke passes.",
        )
    )

    m8 = item_status(completion, "M8")
    gates.append(
        Gate(
            "G5_SOAK",
            "PASS" if m8 == "PASS" else ("BLOCK" if p2_end != "PASS" else "READY"),
            "Stationary soak must prove sustained communication before rotation or expansion.",
            item_evidence(completion, "M8"),
            "Respect the active TFDU <=600 s continuous-run cap; program shutdown after each run.",
        )
    )

    gates.append(
        Gate(
            "G6_DRC_RELEASE",
            "PASS" if not drc_blocking else "BLOCK",
            "DRC/methodology issues must be fixed or formally waived before release/4-or-8-lane expansion.",
            f"{rel(drc_path)}; {rel(drc_release_gate_path)}:{drc_release_overall}:release_ready={drc_release_ready}:debug_can_continue={drc_release_debug_can_continue}",
            "Resolve or formally waive: "
            + (", ".join(drc_blocking) if drc_blocking else "none")
            + f"; release_gate={drc_release_overall}",
        )
    )

    expansion_ready = all(gate.status == "PASS" for gate in gates)
    if not active_guard_pass:
        next_hardware_command = "BLOCKED_UNTIL_ACTIVE_ARTIFACT_GUARD_PASS; restore/rebuild P1_2LANE_ILA_BASELINE, then powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_p1_lane_mapping_matrix_safe.ps1 -StopOnFail"
    elif physical_failed:
        next_hardware_command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_failed_2lane_links_safe.ps1 -AllowTraffic -PhysicalAdjusted -PhysicalAdjustmentNote \"describe_adjustment\""
    else:
        next_hardware_command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_p1_lane_mapping_matrix_safe.ps1 -StopOnFail"
    metadata = {
        "overall": "READY_FOR_EXPANSION" if expansion_ready else "BLOCKED_BY_PREREQUISITES",
        "next_hardware_command": next_hardware_command,
        "latest_completion_audit": rel(completion_path),
        "latest_item_audit": rel(item_path),
        "latest_drc_triage": rel(drc_path),
        "latest_drc_release_gate": rel(drc_release_gate_path),
        "drc_release_gate_overall": drc_release_overall,
        "active_artifact_guard_stage": active_guard_stage,
        "active_artifact_guard_result": active_guard_result,
        "active_artifact_guard_evidence": active_guard_evidence,
        "jtag_pass": str(int(jtag_pass)),
        "jtag_fail": str(int(jtag_fail)),
        "physical_matrix_overall": physical_overall,
        "physical_matrix_evidence": physical_evidence,
        "physical_matrix_gate_selftest": physical_selftest_overall,
        "physical_matrix_gate_selftest_evidence": physical_selftest_evidence,
        "ila_analyzer_selftest": analyzer_selftest_overall,
        "ila_analyzer_selftest_evidence": analyzer_selftest_evidence,
        "physical_failure_snapshot": physical_failure_snapshot_overall,
        "physical_failure_snapshot_evidence": physical_failure_snapshot_evidence,
    }
    return gates, metadata


def render_markdown(gates: list[Gate], metadata: dict[str, str]) -> str:
    status_counts: dict[str, int] = {}
    for gate in gates:
        status_counts[gate.status] = status_counts.get(gate.status, 0) + 1

    next_block = next((gate for gate in gates if gate.status != "PASS"), None)

    parts = [
        "# RF_COMM Plan Readiness Gate",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{metadata['overall']}`",
        f"- Next blocking gate: `{next_block.gate_id if next_block else 'none'}`",
        f"- Next hardware command after JTAG recovery: `{metadata['next_hardware_command']}`",
        "- This gate did not modify RTL, XDC, block design, PS software, host software, project constraints, or bitstreams.",
        "",
        "## Status Counts",
        "",
        md_table(["status", "count"], [[key, value] for key, value in sorted(status_counts.items())]),
        "",
        "## Gate Table",
        "",
        md_table(
            ["gate", "status", "requirement", "evidence", "action"],
            [[gate.gate_id, gate.status, gate.requirement, gate.evidence, gate.action] for gate in gates],
        ),
        "",
        "## Metadata",
        "",
        md_table(["key", "value"], [[key, value] for key, value in metadata.items()]),
        "",
        "PLAN_READINESS_SUMMARY "
        + " ".join(f"{key.lower()}={value}" for key, value in sorted(status_counts.items()))
        + f" overall={metadata['overall']}",
        "",
    ]
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="Markdown output path")
    parser.add_argument("--json-out", type=Path, help="JSON output path")
    parser.add_argument("--fail-on-block", action="store_true", help="Exit non-zero when readiness is blocked")
    args = parser.parse_args()

    gates, metadata = collect_gates()
    markdown = render_markdown(gates, metadata)
    output = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "metadata": metadata,
        "gates": [asdict(gate) for gate in gates],
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(output, indent=2), encoding="utf-8")

    if args.fail_on_block and metadata["overall"] != "READY_FOR_EXPANSION":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
