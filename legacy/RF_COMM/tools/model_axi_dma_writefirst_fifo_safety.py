from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"

IR_HW_C = ROOT / "software" / "_vitis_ws_ps_ps_loopback" / "_src_import" / "ir_hw.c"
IR_HW_H = ROOT / "software" / "_vitis_ws_ps_ps_loopback" / "_src_import" / "ir_hw.h"
BD = (
    ROOT
    / "TFDU_VFIR_Client_Array"
    / "TFDU_VFIR_Client.srcs"
    / "sources_1"
    / "bd"
    / "design_shiboqi"
    / "design_shiboqi.bd"
)


@dataclass(frozen=True)
class CheckRow:
    check: str
    status: str
    expected: str
    actual: str
    note: str


@dataclass(frozen=True)
class ScenarioRow:
    scenario: str
    controller: str
    depth_words: int
    cycles: int
    writes: int
    reads: int
    max_occupancy: int
    collisions: int
    verdict: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
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
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def latest_active_drc() -> Path | None:
    candidates = [
        path / "drc_post_route.rpt"
        for path in REPORTS.glob("active_2lane_route_methodology_*")
        if path.is_dir() and (path / "drc_post_route.rpt").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def current_release_drc() -> Path | None:
    bitstream_payload = read_json(REPORTS / "external_reduced_8lane_frag16_bitstream_current.json")
    drc_value = str(bitstream_payload.get("drc_report", ""))
    if drc_value:
        drc_path = ROOT / drc_value
        if drc_path.exists():
            return drc_path
    route_payload = read_json(REPORTS / "external_reduced_8lane_frag16_route_current.json")
    drc_value = str(route_payload.get("drc_report", ""))
    if drc_value:
        drc_path = ROOT / drc_value
        if drc_path.exists():
            return drc_path
    candidates = [
        path / "drc_post_route.rpt"
        for path in REPORTS.glob("build_external_reduced_8lane_frag16_route_*")
        if path.is_dir() and (path / "drc_post_route.rpt").exists()
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if path.is_file() and sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def parse_packet_bytes(header_text: str) -> int | None:
    match = re.search(r"#define\s+IR_HW_MAX_PACKET_BYTES\s+(\d+)u?", header_text)
    if not match:
        return None
    return int(match.group(1))


def parse_bd_dma_config(bd_text: str) -> dict[str, str]:
    try:
        bd_json = json.loads(bd_text)
    except json.JSONDecodeError:
        bd_json = {}
    design = bd_json.get("design") if isinstance(bd_json, dict) else {}
    components = design.get("components") if isinstance(design, dict) else {}
    dma = components.get("axi_dma_0") if isinstance(components, dict) else {}
    parameters = dma.get("parameters") if isinstance(dma, dict) else {}
    include_sg = parameters.get("c_include_sg") if isinstance(parameters, dict) else {}
    value = include_sg.get("value") if isinstance(include_sg, dict) else None
    if value is None:
        match = re.search(r'"c_include_sg"\s*:\s*\{[^{}]*"value"\s*:\s*"([^"]+)"', bd_text, re.S)
        value = match.group(1) if match else "MISSING"
    vlnv = dma.get("vlnv") if isinstance(dma, dict) else ""
    xci_name = dma.get("xci_name") if isinstance(dma, dict) else ""
    return {
        "vlnv": str(vlnv or "MISSING"),
        "xci_name": str(xci_name or "MISSING"),
        "c_include_sg": str(value),
    }


def count_reqp181(drc_text: str) -> int:
    hits = re.findall(r"\bREQP-181#\d+\b", drc_text)
    if hits:
        return len(hits)
    table = re.search(r"\|\s*REQP-181\s*\|\s*Advisory\s*\|[^|]*\|\s*(\d+)\s*\|", drc_text)
    return int(table.group(1)) if table else 0


def reqp181_details(drc_text: str) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    pattern = re.compile(
        r"(REQP-181#(?P<index>\d+)\s+Advisory.*?BRAM\s+\((?P<path>[^)]+)\).*?WRITE_FIRST.*?Related violations:\s*<none>)",
        re.S,
    )
    for match in pattern.finditer(drc_text):
        path = match.group("path")
        if "GEN_MM2S" in path:
            channel = "MM2S"
        elif "GEN_S2MM" in path:
            channel = "S2MM"
        else:
            channel = "UNKNOWN"
        details.append(
            {
                "id": f"REQP-181#{match.group('index')}",
                "channel": channel,
                "path": path,
                "write_mode": "WRITE_FIRST",
                "related_violations": "none",
            }
        )
    return details


def lfsr_step(value: int) -> int:
    bit = ((value >> 0) ^ (value >> 2) ^ (value >> 3) ^ (value >> 5)) & 1
    return ((value >> 1) | (bit << 15)) & 0xFFFF


def simulate_fifo(
    *,
    scenario: str,
    controller: str,
    depth_words: int,
    cycles: int,
    write_period: int,
    read_period: int,
    seed: int,
    allow_full_bypass_write: bool,
    burst_gate: int,
) -> ScenarioRow:
    rptr = 0
    wptr = 0
    occupancy = 0
    max_occupancy = 0
    writes = 0
    reads = 0
    collisions = 0
    lfsr = seed & 0xFFFF or 0xACE1

    for cycle in range(cycles):
        lfsr = lfsr_step(lfsr)
        burst_open = True if burst_gate <= 1 else ((lfsr % burst_gate) != 0)
        write_req = (cycle % write_period == 0) and burst_open
        read_req = (cycle % read_period == 0) and ((lfsr & 0x3) != 0)

        read_fire = read_req and occupancy > 0
        write_room = occupancy < depth_words
        write_fire = write_req and (write_room or (allow_full_bypass_write and read_fire))

        if read_fire and write_fire and rptr == wptr:
            collisions += 1

        if read_fire:
            rptr = (rptr + 1) % depth_words
            reads += 1
        if write_fire:
            wptr = (wptr + 1) % depth_words
            writes += 1

        occupancy += int(write_fire) - int(read_fire)
        if occupancy < 0 or occupancy > depth_words:
            raise RuntimeError(f"FIFO occupancy invariant failed in {scenario}: {occupancy}")
        max_occupancy = max(max_occupancy, occupancy)

    verdict = "PASS_NO_SAME_ADDRESS_COLLISION" if collisions == 0 else "DEMONSTRATES_COLLISION_RISK"
    note = (
        "Conservative model blocks writes at full even when a read occurs in the same cycle."
        if not allow_full_bypass_write
        else "Permissive full+read bypass can collide when full pointers alias; real AXI DMA IP needs vendor/IP proof or stress evidence."
    )
    return ScenarioRow(
        scenario=scenario,
        controller=controller,
        depth_words=depth_words,
        cycles=cycles,
        writes=writes,
        reads=reads,
        max_occupancy=max_occupancy,
        collisions=collisions,
        verdict=verdict,
        note=note,
    )


def build_scenarios(packet_bytes: int) -> list[ScenarioRow]:
    packet_words = max(1, (packet_bytes + 3) // 4)
    scenarios: list[ScenarioRow] = []
    configs = [
        ("mm2s_256B_packetized_4M_lane", max(16, packet_words), 20000, 2, 3, 0x1234, 5),
        ("s2mm_prearmed_256B_packetized_4M_lane", max(16, packet_words), 20000, 3, 2, 0x5678, 7),
        ("target_hdx_raw32_fdx16_stress_label", 1024, 120000, 1, 2, 0x9ABC, 11),
    ]
    for name, depth, cycles, wp, rp, seed, gate in configs:
        scenarios.append(
            simulate_fifo(
                scenario=name,
                controller="conservative_no_full_bypass",
                depth_words=depth,
                cycles=cycles,
                write_period=wp,
                read_period=rp,
                seed=seed,
                allow_full_bypass_write=False,
                burst_gate=gate,
            )
        )
        scenarios.append(
            simulate_fifo(
                scenario=name,
                controller="permissive_full_read_bypass",
                depth_words=depth,
                cycles=cycles,
                write_period=wp,
                read_period=rp,
                seed=seed,
                allow_full_bypass_write=True,
                burst_gate=gate,
            )
        )
    return scenarios


def table(headers: list[str], rows: list[list[Any]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("\n", " ").replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def build_report() -> tuple[list[CheckRow], list[ScenarioRow], dict[str, Any]]:
    constraint = find_hard_constraint()
    drc_path = latest_active_drc()
    drc_text = read_text(drc_path)
    release_drc_path = current_release_drc()
    release_drc_text = read_text(release_drc_path)
    hw_c = read_text(IR_HW_C)
    hw_h = read_text(IR_HW_H)
    bd_text = read_text(BD)
    dma_config = parse_bd_dma_config(bd_text)
    packet_bytes = parse_packet_bytes(hw_h) or 256
    reqp181 = count_reqp181(drc_text)
    release_reqp181 = count_reqp181(release_drc_text)
    active_reqp181_details = reqp181_details(drc_text)
    release_reqp181_details = reqp181_details(release_drc_text)
    release_channels = sorted(item["channel"] for item in release_reqp181_details)

    software_needles = {
        "simple_dma_rejects_sg": "XAxiDma_HasSg(&hw->dma)" in hw_c,
        "tx_waits_idle_before_start": "wait_dma_idle(hw, XAXIDMA_DMA_TO_DEVICE" in hw_c,
        "rx_waits_idle_before_arm": "wait_dma_idle(hw, XAXIDMA_DEVICE_TO_DMA" in hw_c,
        "uses_simple_transfer": "XAxiDma_SimpleTransfer" in hw_c,
        "polls_rx_busy": "XAxiDma_Busy(&hw->dma, XAXIDMA_DEVICE_TO_DMA)" in hw_c,
        "has_recovery_reset": "recover_link" in hw_c and "reset_dma" in hw_c,
        "dcache_tx_flush": "Xil_DCacheFlushRange((UINTPTR)tx_raw" in hw_c,
        "dcache_rx_invalidate": "Xil_DCacheInvalidateRange((UINTPTR)rx_raw" in hw_c,
        "rx_rearm_state": "rx_armed" in hw_c and "hw->rx_armed = 1" in hw_c,
    }
    checks = [
        CheckRow(
            "hard_constraint_unchanged",
            "PASS" if constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL",
            EXPECTED_CONSTRAINT_SHA256,
            sha256(constraint),
            "This model does not modify the hard target constraint.",
        ),
        CheckRow(
            "reqp181_present",
            "PASS" if reqp181 == 2 else "FAIL",
            "2 routed REQP-181 advisories for AXI DMA MM2S/S2MM FIFOs",
            f"count={reqp181} report={rel(drc_path)}",
            "The issue remains a release blocker until collision exclusion is proven at IP/traffic level.",
        ),
        CheckRow(
            "release_candidate_reqp181_present",
            "PASS" if release_reqp181 == 2 and release_channels == ["MM2S", "S2MM"] else "FAIL",
            "current 8-lane release-personality DRC has exactly MM2S and S2MM AXI DMA REQP-181 advisories",
            f"count={release_reqp181} channels={','.join(release_channels) or 'none'} report={rel(release_drc_path)}",
            "This ties the remaining DMA FIFO release blocker to the current 8-lane fragment=16 candidate, not only to the older active 2-lane debug route.",
        ),
        CheckRow(
            "bd_axi_dma_simple_mode",
            "PASS" if dma_config["vlnv"] == "xilinx.com:ip:axi_dma:7.1" and dma_config["c_include_sg"] == "0" else "FAIL",
            "AXI DMA 7.1 with c_include_sg=0",
            json.dumps(dma_config, ensure_ascii=False),
            "Source BD shows simple DMA mode; generated/cache IP files are intentionally not required.",
        ),
        CheckRow(
            "ps_dma_flow_guards_present",
            "PASS" if all(software_needles.values()) else "FAIL",
            "SG rejection, idle waits, simple transfers, busy polling, recovery reset, cache maintenance, rx_armed state",
            ", ".join(f"{key}={int(value)}" for key, value in software_needles.items()),
            "PS code has the expected packet-level guards, but these guards do not prove vendor FIFO internals.",
        ),
        CheckRow(
            "packet_size_bounded",
            "PASS" if 0 < packet_bytes <= 256 else "FAIL",
            "IR_HW_MAX_PACKET_BYTES <= 256",
            f"IR_HW_MAX_PACKET_BYTES={packet_bytes}",
            "Current PS payload granularity is bounded and suitable for short deterministic DMA stress cases.",
        ),
    ]
    scenarios = build_scenarios(packet_bytes)
    conservative_ok = all(row.collisions == 0 for row in scenarios if row.controller == "conservative_no_full_bypass")
    risk_demonstrated = any(row.collisions > 0 for row in scenarios if row.controller == "permissive_full_read_bypass")
    checks.append(
        CheckRow(
            "offline_fifo_control_model",
            "PASS" if conservative_ok and risk_demonstrated else "FAIL",
            "Conservative controller has zero same-address collisions; permissive full+read bypass demonstrates why REQP-181 still matters",
            f"conservative_ok={int(conservative_ok)} risk_demonstrated={int(risk_demonstrated)}",
            "This is an offline model only and is not a release waiver.",
        )
    )

    row_failures = sum(1 for row in checks if row.status != "PASS")
    metadata = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "overall": "PASS_OFFLINE_EVIDENCE_RELEASE_STILL_BLOCKED" if row_failures == 0 else "FAIL_OFFLINE_EVIDENCE",
        "release_ready": 0,
        "debug_can_continue": int(row_failures == 0),
        "row_failures": row_failures,
        "constraint_sha256": sha256(constraint),
        "drc_report": rel(drc_path),
        "release_drc_report": rel(release_drc_path),
        "ir_hw_c": rel(IR_HW_C),
        "ir_hw_h": rel(IR_HW_H),
        "bd": rel(BD),
        "reqp181_count": reqp181,
        "release_reqp181_count": release_reqp181,
        "active_reqp181_details": active_reqp181_details,
        "release_reqp181_details": release_reqp181_details,
        "packet_bytes": packet_bytes,
        "conservative_ok": int(conservative_ok),
        "risk_demonstrated": int(risk_demonstrated),
        "no_hardware_programming": 1,
        "no_uart_write": 1,
        "no_tfdu_drive": 1,
        "no_vivado_run": 1,
    }
    return checks, scenarios, metadata


def write_reports(checks: list[CheckRow], scenarios: list[ScenarioRow], metadata: dict[str, Any]) -> tuple[Path, Path, Path]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    md_path = REPORTS / "axi_dma_writefirst_fifo_safety_current.md"
    json_path = REPORTS / "axi_dma_writefirst_fifo_safety_current.json"
    csv_path = REPORTS / "axi_dma_writefirst_fifo_safety_current.csv"

    md = "\n".join(
        [
            "# AXI DMA WRITE_FIRST FIFO Safety Evidence",
            "",
            f"Generated: {metadata['generated']}",
            "",
            "## Verdict",
            "",
            f"- Overall: `{metadata['overall']}`",
            "- Release ready: `0`",
            f"- Debug can continue: `{metadata['debug_can_continue']}`",
            f"- REQP-181 count: `{metadata['reqp181_count']}`",
            "- No hardware programming: `1`",
            "- No UART write: `1`",
            "- No TFDU drive: `1`",
            "- No Vivado run: `1`",
            "",
            "This is internal engineering evidence for the routed REQP-181 advisory. It does not clear the advisory by itself and it is not a consulting bundle.",
            "",
            "## Scope",
            "",
            "- Reads source BD, PS DMA source, and archived routed DRC report only.",
            "- Does not read generated/cache IP files.",
            "- Models FIFO pointer collision conditions offline; it does not simulate or certify Xilinx AXI DMA internals.",
            "- Parses both the active 2-lane route DRC and the current 8-lane fragment=16 candidate DRC.",
            "- Keeps REQP-181 release-blocking until real DMA stress or IP-level proof is available.",
            "",
            "## Checks",
            "",
            table(
                ["check", "status", "expected", "actual", "note"],
                [[row.check, row.status, row.expected, row.actual, row.note] for row in checks],
            ),
            "",
            "## REQP-181 Paths",
            "",
            table(
                ["source", "id", "channel", "write_mode", "related", "path"],
                [
                    ["active_2lane", item["id"], item["channel"], item["write_mode"], item["related_violations"], item["path"]]
                    for item in metadata["active_reqp181_details"]
                ]
                + [
                    ["release_8lane_frag16", item["id"], item["channel"], item["write_mode"], item["related_violations"], item["path"]]
                    for item in metadata["release_reqp181_details"]
                ],
            ),
            "",
            "## FIFO Scenarios",
            "",
            table(
                ["scenario", "controller", "depth", "cycles", "writes", "reads", "max_occ", "collisions", "verdict"],
                [
                    [
                        row.scenario,
                        row.controller,
                        row.depth_words,
                        row.cycles,
                        row.writes,
                        row.reads,
                        row.max_occupancy,
                        row.collisions,
                        row.verdict,
                    ]
                    for row in scenarios
                ],
            ),
            "",
            "```text",
            f"RF_COMM_AXI_DMA_WRITEFIRST_FIFO_SAFETY overall={metadata['overall']} release_ready={metadata['release_ready']} debug_can_continue={metadata['debug_can_continue']} reqp181={metadata['reqp181_count']} row_failures={metadata['row_failures']}",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            "NO_VIVADO_RUN=1",
            "```",
            "",
        ]
    )
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "checks": [asdict(row) for row in checks],
                "scenarios": [asdict(row) for row in scenarios],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = list(asdict(scenarios[0]).keys()) if scenarios else list(ScenarioRow.__annotations__.keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in scenarios:
            writer.writerow(asdict(row))
    return md_path, json_path, csv_path


def main() -> int:
    checks, scenarios, metadata = build_report()
    md_path, json_path, csv_path = write_reports(checks, scenarios, metadata)
    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(
        "RF_COMM_AXI_DMA_WRITEFIRST_FIFO_SAFETY "
        f"overall={metadata['overall']} "
        f"release_ready={metadata['release_ready']} "
        f"debug_can_continue={metadata['debug_can_continue']} "
        f"reqp181={metadata['reqp181_count']} "
        f"row_failures={metadata['row_failures']}"
    )
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("NO_VIVADO_RUN=1")
    return 0 if metadata["row_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
