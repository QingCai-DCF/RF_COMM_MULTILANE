#!/usr/bin/env python3
"""Create a strict manifest for the current P1 2-lane ILA baseline.

This script is intentionally read-only for the Vivado design and hardware. It
records hashes for the active bit/LTX/XSA/ELF/BOOT/shutdown artifacts and
checks the source shape needed before a P1 physical lane-mapping retry.
"""

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
EVIDENCE_MANIFEST = ROOT / "evidence" / "manifest"

EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
STAGE = "P1_2LANE_ILA_BASELINE_CURRENT"
PASS_OVERALL = "PASS_READY_FOR_P1_MATRIX"
FAIL_OVERALL = "FAIL_NEEDS_REBUILD_OR_REVIEW"


REPORT_JSON = REPORTS / "p1_2lane_ila_baseline_manifest_current.json"
REPORT_MD = REPORTS / "p1_2lane_ila_baseline_manifest_current.md"
REPORT_CSV = REPORTS / "p1_2lane_ila_baseline_manifest_current.csv"
REPORT_SUMMARY = REPORTS / "p1_2lane_ila_baseline_manifest_current.summary.txt"

EVIDENCE_JSON = EVIDENCE_MANIFEST / "current_baseline_manifest.json"
EVIDENCE_MD = EVIDENCE_MANIFEST / "current_baseline_manifest.md"
EVIDENCE_CSV = EVIDENCE_MANIFEST / "current_baseline_manifest.csv"


ARTIFACTS = {
    "active_bit": {
        "path": ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/impl_1/design_shiboqi_wrapper.bit",
        "role": "active FPGA bitstream for P1 2-lane ILA lane mapping",
        "required": True,
    },
    "active_ltx": {
        "path": ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/impl_1/design_shiboqi_wrapper.ltx",
        "role": "active ILA probes for P1 2-lane physical matrix",
        "required": True,
    },
    "active_xsa": {
        "path": ROOT / "TFDU_VFIR_Client_Array/design_shiboqi_wrapper.xsa",
        "role": "active hardware platform exported from current design",
        "required": True,
    },
    "active_bit_copy": {
        "path": ROOT / "TFDU_VFIR_Client_Array/design_shiboqi_wrapper.bit",
        "role": "top-level convenience copy of active bitstream",
        "required": True,
    },
    "active_boot": {
        "path": ROOT / "software/_boot/BOOT.BIN",
        "role": "current BOOT.BIN recorded to avoid stage mix-ups",
        "required": True,
    },
    "ps_loopback_elf": {
        "path": ROOT / "software/_vitis_ws_ps_ps_loopback/rf_comm_ps_ps_loopback/Debug/rf_comm_ps_ps_loopback.elf",
        "role": "PS loopback/control ELF used by board-side tests",
        "required": True,
    },
    "shutdown_bit": {
        "path": ROOT / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit",
        "role": "post-test TFDU shutdown bitstream",
        "required": True,
    },
    "constraint": {
        "path": ROOT / "\u9879\u76ee\u7ea6\u675f(\u76ee\u6807\uff09.txt",
        "role": "hard project constraint",
        "required": True,
    },
    "project_xpr": {
        "path": ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.xpr",
        "role": "Vivado project file",
        "required": True,
    },
    "port_xdc": {
        "path": ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/PORT1.xdc",
        "role": "active TFDU port constraints",
        "required": True,
    },
    "block_design": {
        "path": ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/sources_1/bd/design_shiboqi/design_shiboqi.bd",
        "role": "active block design",
        "required": True,
    },
    "ila_xci": {
        "path": ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/sources_1/bd/design_shiboqi/ip/design_shiboqi_ila_2lane_phy_0/design_shiboqi_ila_2lane_phy_0.xci",
        "role": "2-lane physical ILA IP configuration",
        "required": True,
    },
    "ir_array_xci": {
        "path": ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/sources_1/bd/design_shiboqi/ip/design_shiboqi_ir_array_top_axi_0_0/design_shiboqi_ir_array_top_axi_0_0.xci",
        "role": "active IR array IP packet/lane configuration",
        "required": True,
    },
    "ir_loopback_b0_xci": {
        "path": ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/sources_1/bd/design_shiboqi/ip/design_shiboqi_ir_loopback_b0_2/design_shiboqi_ir_loopback_b0_2.xci",
        "role": "active B-side loopback IP packet/lane configuration",
        "required": True,
    },
    "ps_makefile": {
        "path": ROOT / "software/_vitis_ws_ps_ps_loopback/rf_comm_ps_ps_loopback/Debug/src/subdir.mk",
        "role": "actual PS loopback ELF compile flags",
        "required": True,
    },
    "ir_hw_header": {
        "path": ROOT / "software/ps_lwip_bridge/src/ir_hw.h",
        "role": "shared PS IR hardware packet constants",
        "required": True,
    },
    "guard_script": {
        "path": ROOT / "tools/check_active_artifact_stage.py",
        "role": "artifact stage guard used before P1 hardware run",
        "required": True,
    },
    "p1_wrapper": {
        "path": ROOT / "tools/run_p1_lane_mapping_matrix_safe.ps1",
        "role": "safe P1 lane-mapping wrapper",
        "required": True,
    },
    "matrix_wrapper": {
        "path": ROOT / "tools/run_2lane_matrix_safe.ps1",
        "role": "safe 2-lane matrix runner",
        "required": True,
    },
    "prearmed_wrapper": {
        "path": ROOT / "tools/run_2lane_hw_prearmed_ila_safe.ps1",
        "role": "single prearmed ILA capture wrapper",
        "required": True,
    },
    "add_ila_script": {
        "path": ROOT / "tools/add_2lane_phy_ila.tcl",
        "role": "script that adds the passive 2-lane physical ILA",
        "required": True,
    },
    "build_script": {
        "path": ROOT / "tools/build_current_bitstream.tcl",
        "role": "script used for the current bitstream rebuild",
        "required": True,
    },
    "routed_artifact_script": {
        "path": ROOT / "tools/write_active_routed_artifacts.tcl",
        "role": "read-only routed-artifact extraction helper",
        "required": True,
    },
    "shutdown_script": {
        "path": ROOT / "tools/program_tfdu_shutdown.tcl",
        "role": "shutdown programming Tcl script",
        "required": True,
    },
}

CRITICAL_GUARD_HASHES = {
    "active_bit",
    "active_ltx",
    "active_xsa",
    "active_boot",
    "shutdown_bit",
    "constraint",
}

EXPECTED_PINS = {
    "ir_mode_out_0[0]": "T12",
    "ir_rx_in_0[0]": "B19",
    "ir_sd_0[0]": "T11",
    "ir_tx_out_0[0]": "C20",
    "ir_mode_out_0[1]": "G17",
    "ir_rx_in_0[1]": "H15",
    "ir_sd_0[1]": "H16",
    "ir_tx_out_0[1]": "K14",
    "loop_mode_b0[0]": "V17",
    "loop_rx_b0[0]": "U13",
    "loop_sd_b0[0]": "T14",
    "loop_tx_b0[0]": "V12",
    "loop_mode_b0[1]": "L16",
    "loop_rx_b0[1]": "G15",
    "loop_sd_b0[1]": "M17",
    "loop_tx_b0[1]": "E18",
}


@dataclass
class ArtifactRow:
    name: str
    role: str
    required: bool
    path: str
    exists: bool
    size_bytes: int
    mtime: str
    sha256: str


@dataclass
class CheckRow:
    name: str
    status: str
    detail: str


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace")
    if data[:4096].count(b"\x00") > max(4, len(data[:4096]) // 10):
        return data.decode("utf-16le", errors="replace")
    return data.decode("utf-8", errors="replace")


def artifact_row(name: str, role: str, required: bool, path: Path) -> ArtifactRow:
    exists = path.exists() and path.is_file()
    stat = path.stat() if exists else None
    return ArtifactRow(
        name=name,
        role=role,
        required=required,
        path=rel(path),
        exists=exists,
        size_bytes=stat.st_size if stat else 0,
        mtime=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds") if stat else "",
        sha256=sha256(path),
    )


def add_check(checks: list[CheckRow], name: str, passed: bool, detail: str) -> None:
    checks.append(CheckRow(name=name, status="PASS" if passed else "FAIL", detail=detail))


def md_table(headers: list[str], rows: Iterable[Iterable[object]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("\n", " ").replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def parse_xdc_pins(text: str) -> dict[str, str]:
    pins: dict[str, str] = {}
    pattern = re.compile(r"set_property\s+PACKAGE_PIN\s+(\S+)\s+\[get_ports\s+\{([^}]+)\}\]")
    for pin, port in pattern.findall(text):
        pins[port] = pin
    return pins


def ltx_probe_summary(path: Path) -> tuple[bool, str]:
    try:
        payload = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        return False, f"LTX is not valid JSON: {exc}"

    for probeset in payload.get("ltx_root", {}).get("ltx_data", []):
        for core in probeset.get("debug_cores", []):
            if core.get("type") != "ILA_V3":
                continue
            if core.get("name") != "design_shiboqi_i/ila_2lane_phy":
                continue
            pins = core.get("pins", [])
            names = {pin.get("name") for pin in pins}
            expected = {f"probe{i}" for i in range(9)}
            if len(pins) != 9 or not expected.issubset(names):
                return False, f"ILA core exists but probe set is unexpected: count={len(pins)} names={sorted(names)}"
            return True, "LTX contains design_shiboqi_i/ila_2lane_phy with probes 0..8"
    return False, "LTX does not contain design_shiboqi_i/ila_2lane_phy"


def parse_int_literal(value: str) -> int | None:
    cleaned = value.strip().strip("()")
    cleaned = re.sub(r"[uUlL]+$", "", cleaned)
    try:
        return int(cleaned, 0)
    except ValueError:
        return None


def parse_build_define(text: str, name: str) -> int | None:
    match = re.search(rf"-D{re.escape(name)}=([^\s]+)", text)
    if not match:
        return None
    return parse_int_literal(match.group(1))


def parse_header_define(text: str, name: str) -> int | None:
    match = re.search(rf"^\s*#define\s+{re.escape(name)}\s+([0-9A-Fa-fxXuUlL]+)", text, re.MULTILINE)
    if not match:
        return None
    return parse_int_literal(match.group(1))


def parse_xci_int_param(text: str, name: str) -> int | None:
    match = re.search(rf'"{re.escape(name)}"\s*:\s*\[\s*\{{\s*"value"\s*:\s*"([^"]+)"', text)
    if not match:
        return None
    return parse_int_literal(match.group(1))


def discover_loopback_b0_xci() -> Path:
    ip_dir = ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/sources_1/bd/design_shiboqi/ip"
    candidates = sorted(ip_dir.glob("design_shiboqi_ir_loopback_b0_*/design_shiboqi_ir_loopback_b0_*.xci"))
    for path in candidates:
        text = read_text(path)
        if '"cell_name": "ir_loopback_b0"' in text:
            return path
    return ARTIFACTS["ir_loopback_b0_xci"]["path"]


def effective_build_define(ps_makefile_text: str, header_text: str, name: str) -> int | None:
    return parse_build_define(ps_makefile_text, name) or parse_header_define(header_text, name)


def source_checks(artifacts: list[ArtifactRow], artifact_defs: dict[str, dict[str, object]]) -> list[CheckRow]:
    checks: list[CheckRow] = []
    hashes = {row.name: row.sha256 for row in artifacts}
    paths = {name: meta["path"] for name, meta in artifact_defs.items()}

    required_missing = [row.name for row in artifacts if row.required and not row.exists]
    add_check(checks, "required_artifacts_exist", not required_missing, "missing=" + ",".join(required_missing))
    add_check(
        checks,
        "hard_constraint_hash",
        hashes.get("constraint") == EXPECTED_CONSTRAINT_SHA256,
        f"constraint_sha256={hashes.get('constraint')}",
    )
    add_check(
        checks,
        "active_bit_copy_matches",
        hashes.get("active_bit") != "MISSING" and hashes.get("active_bit") == hashes.get("active_bit_copy"),
        f"active_bit={hashes.get('active_bit')} active_bit_copy={hashes.get('active_bit_copy')}",
    )

    xpr_text = read_text(paths["project_xpr"])
    add_check(checks, "project_uses_port1_xdc", "PORT1.xdc" in xpr_text, "Vivado project references PORT1.xdc")

    xdc_text = read_text(paths["port_xdc"])
    xdc_pins = parse_xdc_pins(xdc_text)
    wrong_pins = [
        f"{port}:expected={pin}:actual={xdc_pins.get(port, 'MISSING')}"
        for port, pin in EXPECTED_PINS.items()
        if xdc_pins.get(port) != pin
    ]
    add_check(checks, "port1_expected_pinmap", not wrong_pins, "; ".join(wrong_pins) if wrong_pins else "all expected TFDU pins match")
    duplicate_pins = sorted(pin for pin in set(xdc_pins.values()) if list(xdc_pins.values()).count(pin) > 1)
    add_check(checks, "port1_no_duplicate_package_pins", not duplicate_pins, "duplicates=" + ",".join(duplicate_pins))
    add_check(
        checks,
        "b_rx1_moved_to_g15",
        xdc_pins.get("loop_rx_b0[1]") == "G15" and "D19" not in [xdc_pins.get("loop_rx_b0[1]")],
        f"loop_rx_b0[1]={xdc_pins.get('loop_rx_b0[1]', 'MISSING')}",
    )

    bd_text = read_text(paths["block_design"])
    add_check(checks, "bd_uses_ir_stream_bidir_vec_bd", "ir_stream_bidir_vec_bd" in bd_text, "BD contains ir_stream_bidir_vec_bd")
    add_check(checks, "bd_lane_count_2", '"LANE_COUNT"' in bd_text and '"value": "2"' in bd_text, "BD contains LANE_COUNT value 2")
    add_check(checks, "bd_contains_ila_2lane_phy", "ila_2lane_phy" in bd_text, "BD contains passive 2-lane physical ILA")

    ila_xci_text = read_text(paths["ila_xci"])
    add_check(checks, "ila_xci_probe_count_9", '"C_NUM_OF_PROBES": [ { "value": "9"' in ila_xci_text, "C_NUM_OF_PROBES=9")
    add_check(checks, "ila_xci_depth_16384", '"C_DATA_DEPTH": [ { "value": "16384"' in ila_xci_text, "C_DATA_DEPTH=16384")
    add_check(checks, "ila_xci_probe8_width_32", '"C_PROBE8_WIDTH": [ { "value": "32"' in ila_xci_text, "C_PROBE8_WIDTH=32")

    ltx_ok, ltx_detail = ltx_probe_summary(paths["active_ltx"])
    add_check(checks, "ltx_contains_2lane_phy_ila", ltx_ok, ltx_detail)

    ir_array_text = read_text(paths["ir_array_xci"])
    loopback_text = read_text(paths["ir_loopback_b0_xci"])
    ps_makefile_text = read_text(paths["ps_makefile"])
    ir_hw_header_text = read_text(paths["ir_hw_header"])

    pl_lanes = parse_xci_int_param(ir_array_text, "LANE_COUNT")
    pl_max_packet = parse_xci_int_param(ir_array_text, "MAX_PACKET_BYTES")
    pl_fragment = parse_xci_int_param(ir_array_text, "FRAGMENT_BYTES")
    loop_lanes = parse_xci_int_param(loopback_text, "LANE_COUNT")
    loop_raw_packet = parse_xci_int_param(loopback_text, "RAW_PACKET_BYTES")
    loop_fragment = parse_xci_int_param(loopback_text, "FRAGMENT_BYTES")

    ps_payload = parse_build_define(ps_makefile_text, "PSPS_PAYLOAD_BYTES")
    ps_max_packet = effective_build_define(ps_makefile_text, ir_hw_header_text, "IR_HW_MAX_PACKET_BYTES")
    ps_rx_transfer = effective_build_define(ps_makefile_text, ir_hw_header_text, "IR_HW_RX_TRANSFER_BYTES")
    app_header = parse_header_define(ir_hw_header_text, "IR_HW_APP_HEADER_BYTES") or 8
    raw_payload = ps_payload + app_header if ps_payload is not None else None

    add_check(
        checks,
        "pl_2lane_packet_config",
        pl_lanes == 2 and pl_max_packet in {255, 264} and pl_fragment == 255,
        f"LANE_COUNT={pl_lanes} MAX_PACKET_BYTES={pl_max_packet} FRAGMENT_BYTES={pl_fragment} allowed_max_packet=255_or_264",
    )
    add_check(
        checks,
        "loopback_b0_packet_config_matches",
        loop_lanes == 2 and loop_raw_packet == pl_max_packet and loop_fragment == pl_fragment,
        f"LANE_COUNT={loop_lanes} RAW_PACKET_BYTES={loop_raw_packet} FRAGMENT_BYTES={loop_fragment}",
    )
    add_check(
        checks,
        "ps_compile_packet_defines_present",
        ps_payload is not None and ps_max_packet is not None and ps_rx_transfer is not None and app_header is not None,
        f"PSPS_PAYLOAD_BYTES={ps_payload} IR_HW_MAX_PACKET_BYTES={ps_max_packet} IR_HW_RX_TRANSFER_BYTES={ps_rx_transfer} IR_HW_APP_HEADER_BYTES={app_header}",
    )
    add_check(
        checks,
        "ps_raw_payload_fits_pl_packet",
        raw_payload is not None and pl_max_packet is not None and raw_payload <= pl_max_packet,
        f"raw_payload=PSPS_PAYLOAD_BYTES+IR_HW_APP_HEADER_BYTES={raw_payload} PL_MAX_PACKET_BYTES={pl_max_packet}",
    )
    add_check(
        checks,
        "ps_packet_buffers_fit_pl_packet",
        pl_max_packet is not None
        and ps_max_packet is not None
        and ps_rx_transfer is not None
        and ps_max_packet <= pl_max_packet
        and ps_rx_transfer <= pl_max_packet,
        f"IR_HW_MAX_PACKET_BYTES={ps_max_packet} IR_HW_RX_TRANSFER_BYTES={ps_rx_transfer} PL_MAX_PACKET_BYTES={pl_max_packet}",
    )

    return checks


def build_payload() -> dict[str, object]:
    artifact_defs = {name: dict(meta) for name, meta in ARTIFACTS.items()}
    artifact_defs["ir_loopback_b0_xci"]["path"] = discover_loopback_b0_xci()
    artifacts = [
        artifact_row(name, meta["role"], bool(meta["required"]), meta["path"])
        for name, meta in artifact_defs.items()
    ]
    checks = source_checks(artifacts, artifact_defs)
    pass_all = all(row.status == "PASS" for row in checks)
    overall = PASS_OVERALL if pass_all else FAIL_OVERALL
    generated = datetime.now().isoformat(timespec="seconds")
    meta = {
        "generated": generated,
        "stage": STAGE,
        "overall": overall,
        "hardware_action": "none",
        "uart_action": "none",
        "tfdu_drive": "none",
        "vivado_programming": "none",
        "constraint_sha256": next((row.sha256 for row in artifacts if row.name == "constraint"), "MISSING"),
        "critical_guard_hashes": sorted(CRITICAL_GUARD_HASHES),
        "current_plan_scope": "CONSTRAINED_2LANE_STATIC_BASELINE_P0_MANIFEST_FOR_P1_MATRIX",
    }
    return {
        "meta": meta,
        "artifacts": [asdict(row) for row in artifacts],
        "source_checks": [asdict(row) for row in checks],
    }


def write_outputs(payload: dict[str, object]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    EVIDENCE_MANIFEST.mkdir(parents=True, exist_ok=True)

    for path in (REPORT_JSON, EVIDENCE_JSON):
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    artifacts = payload["artifacts"]
    checks = payload["source_checks"]
    meta = payload["meta"]

    with REPORT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(artifacts[0].keys()))
        writer.writeheader()
        writer.writerows(artifacts)
    EVIDENCE_CSV.write_bytes(REPORT_CSV.read_bytes())

    md = "\n".join(
        [
            "# P1 2lane ILA Baseline Manifest",
            "",
            f"Generated: {meta['generated']}",
            "",
            "This is a read-only manifest for the current P1 lane-mapping baseline. It records hashes and source-shape checks only; it does not program hardware, write UART, or drive TFDU boards.",
            "",
            "## Verdict",
            "",
            f"- Stage: `{meta['stage']}`",
            f"- Overall: `{meta['overall']}`",
            f"- Scope: `{meta['current_plan_scope']}`",
            f"- Hardware action: `{meta['hardware_action']}`",
            f"- UART action: `{meta['uart_action']}`",
            f"- TFDU drive: `{meta['tfdu_drive']}`",
            "",
            "## Artifacts",
            "",
            md_table(
                ["name", "required", "exists", "path", "sha256", "role"],
                [[row["name"], int(row["required"]), int(row["exists"]), row["path"], row["sha256"], row["role"]] for row in artifacts],
            ),
            "",
            "## Source Checks",
            "",
            md_table(
                ["name", "status", "detail"],
                [[row["name"], row["status"], row["detail"]] for row in checks],
            ),
            "",
            "```text",
            f"RF_COMM_P1_2LANE_ILA_BASELINE stage={meta['stage']} overall={meta['overall']}",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            f"ROOT_CONSTRAINT_SHA256={meta['constraint_sha256']}",
            "```",
            "",
        ]
    )
    for path in (REPORT_MD, EVIDENCE_MD):
        path.write_text(md, encoding="utf-8")

    summary = "\n".join(
        [
            f"RF_COMM_P1_2LANE_ILA_BASELINE stage={meta['stage']} overall={meta['overall']}",
            f"REPORT_MD={REPORT_MD}",
            f"REPORT_JSON={REPORT_JSON}",
            f"REPORT_CSV={REPORT_CSV}",
            f"EVIDENCE_MD={EVIDENCE_MD}",
            f"EVIDENCE_JSON={EVIDENCE_JSON}",
            f"EVIDENCE_CSV={EVIDENCE_CSV}",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
        ]
    )
    REPORT_SUMMARY.write_text(summary + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    write_outputs(payload)
    meta = payload["meta"]
    print(f"RF_COMM_P1_2LANE_ILA_BASELINE stage={meta['stage']} overall={meta['overall']}")
    print(f"REPORT_MD={REPORT_MD}")
    print(f"REPORT_JSON={REPORT_JSON}")
    print(f"EVIDENCE_MD={EVIDENCE_MD}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    return 0 if meta["overall"] == PASS_OVERALL else 12


if __name__ == "__main__":
    raise SystemExit(main())
