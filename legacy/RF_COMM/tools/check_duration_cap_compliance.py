from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
MAX_CONTINUOUS_SECONDS = 600


@dataclass(frozen=True)
class CheckRow:
    check: str
    status: str
    evidence: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def find_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if path.is_file() and sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def contains_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


def add(rows: list[CheckRow], check: str, ok: bool, evidence: Path | None, pass_note: str, fail_note: str) -> None:
    rows.append(CheckRow(check, "PASS" if ok else "FAIL", rel(evidence), pass_note if ok else fail_note))


def latest_containing(pattern: str, needles: Iterable[str]) -> Path | None:
    candidates = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        text = read_text(path)
        if contains_all(text, needles):
            return path
    return None


def no_live_7200_commands(text: str) -> bool:
    forbidden = [
        r"--duration\s+7200",
        r"--min-duration\s+7200",
        r"-DurationSeconds\s+7200",
        r"-MinDurationSeconds\s+7200",
    ]
    return not any(re.search(pattern, text, re.IGNORECASE) for pattern in forbidden)


def wrapper_caps_600(text: str, require_shutdown_after: bool = True, require_shutdown_before: bool = False) -> bool:
    ok = (
        "$maxContinuousRunSeconds = 600" in text
        and "if ($effectiveDurationSeconds -gt $maxContinuousRunSeconds)" in text
        and "$effectiveDurationSeconds = $maxContinuousRunSeconds" in text
        and 'Write-SummaryLine "DURATION_SECONDS_EFFECTIVE=$effectiveDurationSeconds"' in text
        and "continuous runtime capped to 600 s" in text
        and "[switch]$AllowTraffic" in text
    )
    if require_shutdown_after:
        ok = ok and "[switch]$ProgramShutdownAfterRun" in text and "program_shutdown_after_run_not_set" in text
    if require_shutdown_before:
        ok = ok and "[switch]$ProgramShutdownBeforeRun" in text and "program_shutdown_before_run_not_set" in text
    return ok


def build_rows() -> tuple[list[CheckRow], dict[str, str]]:
    constraint = find_constraint()
    host_run_acceptance = ROOT / "software" / "host_client" / "run_acceptance.ps1"
    software_readme = ROOT / "software" / "README.md"
    ps_lwip_readme = ROOT / "software" / "ps_lwip_bridge" / "README.md"
    full_model = ROOT / "tools" / "model_full_system_capped_soak.py"
    rotating_fixture_validator = ROOT / "tools" / "validate_rotating_fixture_log.py"
    real_acceptance_validator = ROOT / "tools" / "validate_real_acceptance_evidence.py"
    two_ax_wrapper = ROOT / "tools" / "run_two_ax7010_end_to_end_acceptance_safe.ps1"
    product_loop_wrapper = ROOT / "tools" / "run_product_loop_acceptance_safe.ps1"
    rotating_wrapper = ROOT / "tools" / "run_rotating_shaft_acceptance_safe.ps1"
    eightlane_wrapper = ROOT / "tools" / "run_8lane_hardware_acceptance_safe.ps1"
    runbook_md = REPORTS / "real_acceptance_runbook_current.md"
    runbook_csv = REPORTS / "real_acceptance_runbook_current.csv"
    sequence_md = REPORTS / "real_acceptance_sequence_safe_current.md"
    sequence_summary = REPORTS / "real_acceptance_sequence_safe_current.summary.txt"
    sequence_csv = REPORTS / "real_acceptance_sequence_safe_current.stages.csv"
    promotion_gate_md = REPORTS / "real_acceptance_promotion_gate_current.md"
    remaining_readiness_md = REPORTS / "remaining_acceptance_readiness_current.md"
    remaining_readiness_csv = REPORTS / "remaining_acceptance_readiness_current.csv"

    rotating_dryrun = latest_containing("reports/rotating_shaft_acceptance_safe_*.summary.txt", ["ROTATING_SHAFT_DRY_RUN=1"])
    product_loop_dryrun = latest_containing("reports/product_loop_acceptance_safe_*.summary.txt", ["PRODUCT_LOOP_DRY_RUN=1"])
    eightlane_dryrun = latest_containing("reports/8lane_hardware_acceptance_safe_*.summary.txt", ["EIGHT_LANE_HARDWARE_DRY_RUN=1"])

    host_text = read_text(host_run_acceptance)
    sw_readme_text = read_text(software_readme)
    ps_lwip_readme_text = read_text(ps_lwip_readme)
    full_model_text = read_text(full_model)
    rotating_fixture_text = read_text(rotating_fixture_validator)
    real_validator_text = read_text(real_acceptance_validator)
    two_ax_text = read_text(two_ax_wrapper)
    product_text = read_text(product_loop_wrapper)
    rotating_text = read_text(rotating_wrapper)
    eightlane_text = read_text(eightlane_wrapper)
    runbook_text = read_text(runbook_md) + "\n" + read_text(runbook_csv)
    sequence_text = read_text(sequence_md) + "\n" + read_text(sequence_summary) + "\n" + read_text(sequence_csv)
    promotion_text = read_text(promotion_gate_md)
    remaining_text = read_text(remaining_readiness_md) + "\n" + read_text(remaining_readiness_csv)
    rotating_dryrun_text = read_text(rotating_dryrun)
    product_dryrun_text = read_text(product_loop_dryrun)
    eightlane_dryrun_text = read_text(eightlane_dryrun)

    rows: list[CheckRow] = []
    add(
        rows,
        "hard_constraint_unchanged",
        constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256,
        constraint,
        f"sha256={sha256(constraint)}",
        "hard constraint file is missing or changed",
    )
    add(
        rows,
        "host_acceptance_caps_soak_2h_to_600",
        contains_all(
            host_text,
            [
                "$MaxContinuousRunSeconds = 600",
                "[Math]::Min($requestedDurationSeconds, $MaxContinuousRunSeconds)",
                'Write-Host "Continuous runtime cap seconds: $MaxContinuousRunSeconds"',
                'Invoke-Traffic -Name "soak_2h" -DefaultDurationSeconds $MaxContinuousRunSeconds',
            ],
        ),
        host_run_acceptance,
        "host acceptance wrapper caps all requested continuous traffic modes to 600 s and keeps soak_2h as a capped compatibility name",
        "host acceptance wrapper does not prove 600 s capping for soak_2h",
    )
    add(
        rows,
        "software_readme_documents_600_cap",
        "600 seconds" in sw_readme_text and "--min-duration 600" in sw_readme_text and no_live_7200_commands(sw_readme_text),
        software_readme,
        "software README documents the 600 s physical cap and contains no live 7200 s command",
        "software README is missing the 600 s cap or still contains a live 7200 s command",
    )
    add(
        rows,
        "ps_lwip_readme_documents_600_cap",
        contains_all(
            ps_lwip_readme_text,
            [
                "physical continuous",
                "capped at 600 seconds",
                "--duration 600",
                "--min-duration 600",
            ],
        )
        and no_live_7200_commands(ps_lwip_readme_text),
        ps_lwip_readme,
        "PS lwIP bridge README now documents 600 s physical cap and no longer tells users to run 7200 s live acceptance",
        "PS lwIP bridge README still has stale 7200 s live-run guidance or lacks the 600 s cap",
    )
    add(
        rows,
        "full_system_model_separates_7200_target_from_600_cap",
        contains_all(
            full_model_text,
            [
                "ORIGINAL_TARGET_SECONDS = 2 * 60 * 60",
                "RUNTIME_CAP_SECONDS = 10 * 60",
                "EFFECTIVE_SECONDS = min(ORIGINAL_TARGET_SECONDS, RUNTIME_CAP_SECONDS)",
                "OFFLINE_MODEL_NOT_HARDWARE",
            ],
        ),
        full_model,
        "offline model may remember the historical 2 h target only while capping effective modeled physical window to 600 s and labeling as not hardware",
        "full-system model does not clearly separate 2 h target metadata from the 600 s cap",
    )
    add(
        rows,
        "real_acceptance_validator_enforces_600",
        "MAX_CONTINUOUS_SECONDS = 600.0" in real_validator_text
        and "DURATION_SECONDS_EFFECTIVE" in real_validator_text
        and "exceeds cap" in real_validator_text
        and "--max-continuous-seconds" in real_validator_text,
        real_acceptance_validator,
        "real-acceptance validator rejects over-cap real evidence",
        "real-acceptance validator does not expose the 600 s cap",
    )
    add(
        rows,
        "rotating_fixture_validator_enforces_600",
        "--max-continuous-seconds" in rotating_fixture_text
        and "default=600.0" in rotating_fixture_text
        and "sample_seconds per continuous segment must not exceed 600" in rotating_fixture_text,
        rotating_fixture_validator,
        "rotating fixture validator caps each continuous segment at 600 s",
        "rotating fixture validator does not prove the 600 s segment cap",
    )
    add(rows, "two_ax7010_wrapper_caps_600", wrapper_caps_600(two_ax_text), two_ax_wrapper, "two-AX7010 safe wrapper caps real traffic at 600 s and requires shutdown-after-run", "two-AX7010 safe wrapper cap/shutdown guard is incomplete")
    add(rows, "product_loop_wrapper_caps_600", wrapper_caps_600(product_text), product_loop_wrapper, "product-loop safe wrapper caps real traffic at 600 s and requires shutdown-after-run", "product-loop safe wrapper cap/shutdown guard is incomplete")
    add(rows, "rotating_shaft_wrapper_caps_600", wrapper_caps_600(rotating_text), rotating_wrapper, "rotating-shaft safe wrapper caps real traffic at 600 s and requires shutdown-after-run", "rotating-shaft safe wrapper cap/shutdown guard is incomplete")
    add(rows, "eightlane_wrapper_caps_600", wrapper_caps_600(eightlane_text, require_shutdown_before=True), eightlane_wrapper, "8-lane safe wrapper caps real traffic at 600 s and requires shutdown before/after run", "8-lane safe wrapper cap/shutdown guard is incomplete")
    add(
        rows,
        "real_acceptance_runbook_uses_600",
        "Continuous physical run cap: `600 seconds`" in runbook_text
        and "-DurationSeconds 600" in runbook_text
        and no_live_7200_commands(runbook_text),
        runbook_md,
        "real acceptance runbook uses 600 s commands and contains no live 7200 s command",
        "real acceptance runbook is stale or lacks 600 s commands",
    )
    add(
        rows,
        "real_acceptance_sequence_uses_600",
        "Duration cap: `600 / 600 s`" in sequence_text
        and "MAX_CONTINUOUS_RUN_SECONDS=600" in sequence_text
        and "-DurationSeconds 600" in sequence_text
        and no_live_7200_commands(sequence_text),
        sequence_md,
        "top-level real-acceptance sequence stays capped at 600 s",
        "top-level real-acceptance sequence does not prove the 600 s cap",
    )
    add(
        rows,
        "promotion_gate_requires_real_evidence_without_running",
        contains_all(
            promotion_text,
            [
                "RF_COMM_REAL_ACCEPTANCE_PROMOTION_GATE overall=BLOCKED_NOT_PROMOTABLE items=5 promotable=0",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
                "REAL_ACCEPTANCE_EVIDENCE_REQUIRED=1",
            ],
        ),
        promotion_gate_md,
        "promotion gate reads evidence only and does not create real acceptance evidence",
        "promotion gate no-side-effect boundary is missing",
    )
    add(
        rows,
        "remaining_readiness_mentions_shutdown_and_600",
        "safety_requirement" in remaining_text
        and "shutdown" in remaining_text.lower()
        and "600" in remaining_text,
        remaining_readiness_csv,
        "remaining readiness records safety requirements including shutdown and 600 s cap",
        "remaining readiness does not record safety requirements clearly",
    )
    add(
        rows,
        "dryrun_wrappers_cap_7200_request_to_600",
        contains_all(rotating_dryrun_text, ["DURATION_SECONDS_REQUESTED=7200", "DURATION_SECONDS_EFFECTIVE=600", "MAX_CONTINUOUS_RUN_SECONDS=600", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"])
        and contains_all(product_dryrun_text, ["DURATION_SECONDS_REQUESTED=7200", "DURATION_SECONDS_EFFECTIVE=600", "MAX_CONTINUOUS_RUN_SECONDS=600", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"])
        and contains_all(eightlane_dryrun_text, ["DURATION_SECONDS_REQUESTED=7200", "DURATION_SECONDS_EFFECTIVE=600", "MAX_CONTINUOUS_RUN_SECONDS=600", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"]),
        rotating_dryrun or product_loop_dryrun or eightlane_dryrun,
        "latest rotating/product/8-lane dry-runs demonstrate a 7200 s request is capped to 600 s without TFDU drive",
        "latest dry-run cap evidence is missing or incomplete",
    )

    meta = {
        "constraint": rel(constraint),
        "constraint_sha256": sha256(constraint),
        "max_continuous_seconds": str(MAX_CONTINUOUS_SECONDS),
        "host_run_acceptance": rel(host_run_acceptance),
        "software_readme": rel(software_readme),
        "ps_lwip_readme": rel(ps_lwip_readme),
        "full_system_model": rel(full_model),
        "real_acceptance_validator": rel(real_acceptance_validator),
        "rotating_fixture_validator": rel(rotating_fixture_validator),
        "two_ax7010_wrapper": rel(two_ax_wrapper),
        "product_loop_wrapper": rel(product_loop_wrapper),
        "rotating_shaft_wrapper": rel(rotating_wrapper),
        "eightlane_wrapper": rel(eightlane_wrapper),
        "real_acceptance_runbook": rel(runbook_md),
        "real_acceptance_sequence": rel(sequence_md),
        "promotion_gate": rel(promotion_gate_md),
        "rotating_dryrun": rel(rotating_dryrun),
        "product_loop_dryrun": rel(product_loop_dryrun),
        "eightlane_dryrun": rel(eightlane_dryrun),
    }
    return rows, meta


def md_table(rows: list[CheckRow]) -> str:
    lines = [
        "| check | status | evidence | note |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [row.check, row.status, row.evidence, row.note]
            ).replace("\n", " ").replace("|", "/")
            + " |"
        )
    return "\n".join(lines)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows, meta = build_rows()
    failures = [row for row in rows if row.status == "FAIL"]
    overall = "PASS_DURATION_CAP_600S" if not failures else "FAIL_DURATION_CAP_COMPLIANCE"
    generated = datetime.now().isoformat(timespec="seconds")

    md_path = REPORTS / "duration_cap_compliance_current.md"
    json_path = REPORTS / "duration_cap_compliance_current.json"
    csv_path = REPORTS / "duration_cap_compliance_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    md = [
        "# Duration Cap Compliance",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Checks: `{len(rows)}`",
        f"- Failures: `{len(failures)}`",
        f"- Max continuous physical run seconds: `{MAX_CONTINUOUS_SECONDS}`",
        "- Real physical run >600 s allowed: `0`",
        "- Legacy `soak_2h` name requires 600 s cap: `1`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "",
        "This report checks the active 600-second physical run cap and keeps historical 2-hour language from becoming a live hardware command.",
        "",
        "## Checks",
        "",
        md_table(rows),
        "",
        "```text",
        f"RF_COMM_DURATION_CAP_COMPLIANCE overall={overall} checks={len(rows)} failures={len(failures)}",
        f"MAX_CONTINUOUS_RUN_SECONDS={MAX_CONTINUOUS_SECONDS}",
        "REAL_PHYSICAL_RUN_GT_600_ALLOWED=0",
        "LEGACY_2H_NAME_REQUIRES_600S_CAP=1",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "REAL_ACCEPTANCE_EVIDENCE_PRODUCED=0",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "checks": len(rows),
        "failures": len(failures),
        "max_continuous_run_seconds": MAX_CONTINUOUS_SECONDS,
        "real_physical_run_gt_600_allowed": False,
        "legacy_2h_name_requires_600s_cap": True,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "real_acceptance_evidence_produced": False,
        "meta": meta,
        "rows": [asdict(row) for row in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_DURATION_CAP_COMPLIANCE overall={overall} checks={len(rows)} failures={len(failures)}")
    print(f"MAX_CONTINUOUS_RUN_SECONDS={MAX_CONTINUOUS_SECONDS}")
    print("REAL_PHYSICAL_RUN_GT_600_ALLOWED=0")
    print("LEGACY_2H_NAME_REQUIRES_600S_CAP=1")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("REAL_ACCEPTANCE_EVIDENCE_PRODUCED=0")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
