#!/usr/bin/env python3
"""Self-test the 2-lane physical matrix classifier and gate without hardware."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
CASE_DIR = REPORTS / "physical_matrix_gate_selftest_current"
CLASSIFIER = ROOT / "tools" / "classify_2lane_physical_matrix.py"
GATE = ROOT / "tools" / "check_physical_matrix_gate.ps1"
REQUIRED_LINKS = ["A_TO_B_LANE0", "A_TO_B_LANE1", "B_TO_A_LANE0", "B_TO_A_LANE1"]


@dataclass(frozen=True)
class CaseResult:
    case: str
    tool: str
    expected_exit: int
    actual_exit: int
    expected_marker: str
    marker_present: int
    status: str
    evidence: str


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT)).replace("\\", "/")


def write_json(path: Path, analyses: list[dict[str, object]], mtime: int) -> None:
    path.write_text(json.dumps(analyses, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.utime(path, (mtime, mtime))


def analysis(expected: str, tx_pulses: int, rx_pulses: int) -> dict[str, object]:
    link_pass = tx_pulses > 0 and rx_pulses > 0
    return {
        "trigger_mode": f"synthetic_{expected.lower()}",
        "expected": expected,
        "verdict": "PASS_SYNTHETIC_CAPTURE" if link_pass else "FAIL_SYNTHETIC_CAPTURE",
        "links": {
            expected: {
                "verdict": "PASS_SYNTHETIC_LINK" if link_pass else "FAIL_SYNTHETIC_LINK",
                "tx_pulses": tx_pulses,
                "rx_pulses": rx_pulses,
                "tx_edges": tx_pulses * 2,
                "rx_edges": rx_pulses * 2,
            }
        },
    }


def complete_matrix(tx_pulses: int = 12, rx_pulses: int = 11) -> list[dict[str, object]]:
    return [analysis(link, tx_pulses, rx_pulses) for link in REQUIRED_LINKS]


def run_command(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return proc.returncode, proc.stdout


def run_classifier(paths: list[Path]) -> tuple[int, str]:
    return run_command(
        [
            sys.executable,
            str(CLASSIFIER),
            *[str(path) for path in paths],
            "--require-links",
            ",".join(REQUIRED_LINKS),
            "--latest-by-link",
        ]
    )


def run_gate(paths: list[Path]) -> tuple[int, str]:
    return run_command(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(GATE),
            "-RequiredLinks",
            ",".join(REQUIRED_LINKS),
            "-JsonPaths",
            ",".join(str(path) for path in paths),
        ]
    )


def add_result(
    rows: list[CaseResult],
    case: str,
    tool: str,
    expected_exit: int,
    actual_exit: int,
    expected_marker: str,
    output: str,
    evidence: Path,
) -> None:
    marker_present = int(expected_marker in output)
    rows.append(
        CaseResult(
            case=case,
            tool=tool,
            expected_exit=expected_exit,
            actual_exit=actual_exit,
            expected_marker=expected_marker,
            marker_present=marker_present,
            status="PASS" if actual_exit == expected_exit and marker_present else "FAIL",
            evidence=rel(evidence),
        )
    )


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    CASE_DIR.mkdir(parents=True, exist_ok=True)

    cases: dict[str, list[Path]] = {}

    pass_all = CASE_DIR / "pass_all.json"
    write_json(pass_all, complete_matrix(), 1_800_000_001)
    cases["pass_all"] = [pass_all]

    fail_rx = CASE_DIR / "fail_one_rx_missing.json"
    fail_rx_analyses = complete_matrix()
    fail_rx_analyses[1] = analysis("A_TO_B_LANE1", 12, 0)
    write_json(fail_rx, fail_rx_analyses, 1_800_000_002)
    cases["fail_one_rx_missing"] = [fail_rx]

    missing = CASE_DIR / "missing_required_link.json"
    write_json(missing, complete_matrix()[:-1], 1_800_000_003)
    cases["missing_required_link"] = [missing]

    older_fail = CASE_DIR / "latest_by_link_older_fail.json"
    older_fail_analyses = complete_matrix()
    older_fail_analyses[2] = analysis("B_TO_A_LANE0", 12, 0)
    write_json(older_fail, older_fail_analyses, 1_800_000_004)
    newer_pass = CASE_DIR / "latest_by_link_newer_pass.json"
    write_json(newer_pass, complete_matrix(), 1_800_000_005)
    cases["latest_by_link_newer_pass"] = [older_fail, newer_pass]

    expectations = {
        "pass_all": (0, "PASS_REQUIRED_LINKS", "PHYSICAL_MATRIX_GATE_RESULT=PASS"),
        "fail_one_rx_missing": (2, "BLOCK_REQUIRED_LINK_NOT_PASSING", "PHYSICAL_MATRIX_GATE_RESULT=BLOCK"),
        "missing_required_link": (2, "BLOCK_REQUIRED_LINK_EVIDENCE_MISSING", "PHYSICAL_MATRIX_GATE_RESULT=BLOCK"),
        "latest_by_link_newer_pass": (0, "PASS_REQUIRED_LINKS", "PHYSICAL_MATRIX_GATE_RESULT=PASS"),
    }

    rows: list[CaseResult] = []
    outputs: dict[str, str] = {}
    for case, paths in cases.items():
        expected_exit, classifier_marker, gate_marker = expectations[case]

        classifier_exit, classifier_output = run_classifier(paths)
        outputs[f"{case}.classifier"] = classifier_output
        classifier_log = CASE_DIR / f"{case}.classifier.log"
        classifier_log.write_text(classifier_output, encoding="utf-8")
        add_result(
            rows,
            case,
            "classifier",
            expected_exit,
            classifier_exit,
            f"PHYSICAL_MATRIX_OVERALL={classifier_marker}",
            classifier_output,
            classifier_log,
        )

        gate_exit, gate_output = run_gate(paths)
        outputs[f"{case}.gate"] = gate_output
        gate_log = CASE_DIR / f"{case}.gate.log"
        gate_log.write_text(gate_output, encoding="utf-8")
        add_result(rows, case, "gate", expected_exit, gate_exit, gate_marker, gate_output, gate_log)

    failures = [row for row in rows if row.status != "PASS"]
    overall = "PASS" if not failures else "FAIL"
    generated = datetime.now().isoformat(timespec="seconds")

    csv_path = REPORTS / "physical_matrix_gate_selftest_current.csv"
    json_path = REPORTS / "physical_matrix_gate_selftest_current.json"
    md_path = REPORTS / "physical_matrix_gate_selftest_current.md"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    payload = {
        "generated": generated,
        "overall": overall,
        "cases": len(cases),
        "checks": len(rows),
        "failures": len(failures),
        "required_links": REQUIRED_LINKS,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "case_dir": rel(CASE_DIR),
        "rows": [asdict(row) for row in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md_lines = [
        "# Physical Matrix Gate Self-Test",
        "",
        f"Generated: {generated}",
        "",
        f"- Overall: `{overall}`",
        f"- Cases: `{len(cases)}`",
        f"- Checks: `{len(rows)}`",
        f"- Failures: `{len(failures)}`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "",
        "| case | tool | status | expected exit | actual exit | marker | evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        md_lines.append(
            f"| {row.case} | {row.tool} | {row.status} | {row.expected_exit} | "
            f"{row.actual_exit} | {row.expected_marker} | {row.evidence} |"
        )
    md_lines.extend(
        [
            "",
            "```text",
            f"RF_COMM_PHYSICAL_MATRIX_GATE_SELFTEST overall={overall} cases={len(cases)} checks={len(rows)} failures={len(failures)}",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            "```",
        ]
    )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_PHYSICAL_MATRIX_GATE_SELFTEST overall={overall} cases={len(cases)} checks={len(rows)} failures={len(failures)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
