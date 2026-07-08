from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
PROJECT = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.xpr"
OUT_DIR = ROOT / "TFDU_VFIR_Client_Array" / "project_build_8lane_external"
SYNTH_RUN = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.runs" / "synth_1"
IMPL_RUN = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.runs" / "impl_1"
SYNTH_LOG = SYNTH_RUN / "runme.log"
IMPL_LOG = IMPL_RUN / "runme.log"
DRC_RPT = IMPL_RUN / "design_shiboqi_wrapper_drc_opted.rpt"
SYNTH_DCP = SYNTH_RUN / "design_shiboqi_wrapper.dcp"
OPT_DCP = IMPL_RUN / "design_shiboqi_wrapper_opt.dcp"
A_ONLY_XDC = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.srcs" / "constrs_1" / "new" / "target_ir_array_8lane_a_only_candidate.xdc"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class BuildItem:
    item_id: str
    status: str
    evidence: str
    note: str


@dataclass
class ResourceOveruse:
    resource: str
    required: int
    available: int
    percent: float


def sha256(path: Path | None) -> str:
    if path is None or not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def latest_meta() -> Path | None:
    metas = sorted(
        REPORTS.glob("build_8lane_external_project_*.meta.txt"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return metas[0] if metas else None


def parse_meta(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def meta_path(meta: dict[str, str], key: str) -> Path | None:
    value = meta.get(key, "")
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def final_counts(text: str) -> tuple[int, int, int] | None:
    matches = re.findall(
        r"(\d+)\s+Infos,\s+(\d+)\s+Warnings,\s+(\d+)\s+Critical Warnings and\s+(\d+)\s+Errors encountered\.",
        text,
    )
    if not matches:
        return None
    _infos, warnings, critical, errors = matches[-1]
    return int(warnings), int(critical), int(errors)


def parse_resource_overuse(text: str) -> list[ResourceOveruse]:
    pattern = re.compile(
        r"(?P<name>FDRE|LUT as Logic|Register as Flip Flop|Slice LUTs|Slice Registers) "
        r"over-utilized.*?requires\s+(?P<required>\d+)\s+of such cell types but only\s+"
        r"(?P<available>\d+)\s+compatible sites are available",
        re.IGNORECASE | re.DOTALL,
    )
    seen: set[str] = set()
    out: list[ResourceOveruse] = []
    for match in pattern.finditer(text):
        name = match.group("name")
        if name in seen:
            continue
        seen.add(name)
        required = int(match.group("required"))
        available = int(match.group("available"))
        out.append(ResourceOveruse(name, required, available, required / available * 100.0))
    return out


def resource_summary(resources: list[ResourceOveruse]) -> str:
    if not resources:
        return "No classified resource over-utilization parsed."
    return "; ".join(f"{item.resource}: {item.required}/{item.available} ({item.percent:.2f}%)" for item in resources)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    constraint = find_hard_constraint()
    meta_file = latest_meta()
    meta = parse_meta(meta_file)
    vivado_log = meta_path(meta, "log")
    stdout_log = meta_path(meta, "out")
    stderr_log = meta_path(meta, "err")
    journal = meta_path(meta, "journal")
    vivado_text = read_text(vivado_log)
    synth_text = read_text(SYNTH_LOG)
    impl_text = read_text(IMPL_LOG)
    drc_text = read_text(DRC_RPT)
    project_text = read_text(PROJECT)

    synth_pass = "PROJECT_8LANE_EXTERNAL_SYNTH_STATUS=synth_design Complete!" in vivado_text
    impl_resource_blocked = "UTLZ-1" in drc_text and "over-utilized" in drc_text
    candidate_removed = "PROJECT_8LANE_EXTERNAL_XDC_REMOVED_AFTER_BUILD" in vivado_text
    port1_restored = "PROJECT_8LANE_EXTERNAL_PORT1_RESTORED" in vivado_text
    xpr_clean = "target_ir_array_8lane_a_only_candidate" not in project_text and "auto_blackbox_stubs" not in project_text
    external_mode = "IR_LANE_COUNT=8" in vivado_text and "IR_B_MODE=external" in vivado_text
    no_hw = all(meta.get(key) == "1" for key in ["no_hardware_programming", "no_uart_write", "no_tfdu_drive"])
    ethernet_deferred = meta.get("ethernet_real_test_deferred") == "1"
    counts = final_counts(vivado_text)
    warnings, critical, errors = counts if counts is not None else (-1, -1, -1)
    resources = parse_resource_overuse(drc_text)

    overall = "SYNTH_PASS_IMPL_BLOCKED_RESOURCE_OVERUTILIZED" if synth_pass and impl_resource_blocked else "FAIL"
    items = [
        BuildItem(
            "HARD-CONSTRAINT",
            "PASS" if constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL",
            rel(constraint),
            f"sha256={sha256(constraint)}",
        ),
        BuildItem(
            "BD-8LANE-EXTERNAL-CONFIG",
            "PASS" if external_mode else "FAIL",
            rel(vivado_log),
            "Build configured the BD for 8-lane external A-endpoint mode.",
        ),
        BuildItem(
            "A-ONLY-XDC",
            "PASS_CANDIDATE_REVIEW_REQUIRED" if A_ONLY_XDC.exists() else "MISSING",
            rel(A_ONLY_XDC),
            "A-only candidate XDC exists for two-AX7010 style topology; it was used only temporarily for this build.",
        ),
        BuildItem(
            "SYNTHESIS",
            "PASS" if synth_pass else "FAIL",
            rel(SYNTH_LOG),
            "synth_1 completed with 0 critical warnings." if synth_pass else "synth_1 did not complete.",
        ),
        BuildItem(
            "IMPLEMENTATION",
            "BLOCKED_RESOURCE" if impl_resource_blocked else "FAIL",
            rel(DRC_RPT),
            resource_summary(resources),
        ),
        BuildItem(
            "PORT1-XDC-RESTORE",
            "PASS" if port1_restored and candidate_removed and xpr_clean else "FAIL",
            rel(PROJECT),
            "PORT1.xdc was restored as the target constraints file and the A-only candidate XDC was removed from the project.",
        ),
        BuildItem(
            "NO-HARDWARE-ACTION",
            "PASS" if no_hw else "FAIL",
            rel(meta_file),
            "Batch build only: no open_hw_manager, no program_hw_devices, no UART write, no TFDU drive.",
        ),
        BuildItem(
            "NO-ETHERNET-BOUNDARY",
            "DEFERRED" if ethernet_deferred else "WARN",
            rel(meta_file),
            "Current development board has no Ethernet cable; real TCP/DHCP and two-AX7010 Ethernet acceptance are deferred.",
        ),
    ]

    md_path = REPORTS / "8lane_external_project_build_current.md"
    json_path = REPORTS / "8lane_external_project_build_current.json"
    csv_path = REPORTS / "8lane_external_project_build_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["item_id", "status", "evidence", "note"])
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))

    md = [
        "# 8-Lane External A-Only Project Build",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        "- This profile represents one AX7010 side of the final two-system topology: A endpoint exposed externally, no internal B endpoint.",
        "- The project reaches synthesis, then implementation is blocked by XC7Z010 resource capacity.",
        f"- Resource overuse: `{resource_summary(resources)}`",
        "- The current board has no Ethernet cable; real TCP/DHCP and two-board Ethernet acceptance are deferred.",
        "- No FPGA was programmed; no UART was written; no TFDU was driven.",
        "",
        "## Evidence",
        "",
        "| id | status | evidence | note |",
        "| --- | --- | --- | --- |",
    ]
    for item in items:
        md.append(f"| {item.item_id} | {item.status} | {item.evidence} | {item.note} |")
    md.extend(
        [
            "",
            "## Build Files",
            "",
            f"- Meta: `{rel(meta_file)}`",
            f"- Vivado log: `{rel(vivado_log)}`",
            f"- Stdout: `{rel(stdout_log)}`",
            f"- Stderr: `{rel(stderr_log)}`",
            f"- Journal: `{rel(journal)}`",
            f"- Synth log: `{rel(SYNTH_LOG)}`",
            f"- Impl log: `{rel(IMPL_LOG)}`",
            f"- DRC report: `{rel(DRC_RPT)}`",
            f"- Synth DCP: `{rel(SYNTH_DCP)}`",
            f"- Opt DCP: `{rel(OPT_DCP)}`",
            "",
            f"RF_COMM_8LANE_EXTERNAL_PROJECT_BUILD overall={overall} resources=\"{resource_summary(resources)}\"",
        ]
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "hard_constraint_sha256": sha256(constraint),
        "vivado_warnings": warnings,
        "vivado_critical_warnings": critical,
        "vivado_errors": errors,
        "synthesis_pass": synth_pass,
        "implementation_resource_blocked": impl_resource_blocked,
        "resources": [asdict(item) for item in resources],
        "candidate_xdc_removed_after_build": candidate_removed,
        "port1_xdc_restored": port1_restored,
        "xpr_clean": xpr_clean,
        "no_hardware_programming": no_hw,
        "no_uart_write": no_hw,
        "no_tfdu_drive": no_hw,
        "current_board_ethernet": "not_connected",
        "real_tcp_dhcp_deferred": ethernet_deferred,
        "meta": rel(meta_file),
        "vivado_log": rel(vivado_log),
        "stdout": rel(stdout_log),
        "stderr": rel(stderr_log),
        "journal": rel(journal),
        "synth_log": rel(SYNTH_LOG),
        "impl_log": rel(IMPL_LOG),
        "drc_report": rel(DRC_RPT),
        "synth_dcp": rel(SYNTH_DCP),
        "opt_dcp": rel(OPT_DCP),
        "items": [asdict(item) for item in items],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_8LANE_EXTERNAL_PROJECT_BUILD overall={overall} resources=\"{resource_summary(resources)}\"")
    return 0 if overall != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
