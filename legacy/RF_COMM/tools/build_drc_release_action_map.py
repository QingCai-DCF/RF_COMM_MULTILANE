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

TRIAGE_JSON = REPORTS / "drc_triage_current_20260626.json"
DRC_RPT = (
    ROOT
    / "TFDU_VFIR_Client_Array"
    / "TFDU_VFIR_Client.runs"
    / "impl_1"
    / "design_shiboqi_wrapper_drc_routed.rpt"
)
METH_RPT = (
    ROOT
    / "TFDU_VFIR_Client_Array"
    / "TFDU_VFIR_Client.runs"
    / "impl_1"
    / "design_shiboqi_wrapper_methodology_drc_routed.rpt"
)
TIMING_RPT = (
    ROOT
    / "TFDU_VFIR_Client_Array"
    / "TFDU_VFIR_Client.runs"
    / "impl_1"
    / "timing_summary_post_route.rpt"
)
UTIL_RPT = (
    ROOT
    / "TFDU_VFIR_Client_Array"
    / "TFDU_VFIR_Client.runs"
    / "impl_1"
    / "utilization_post_route.rpt"
)
ASYNC_XDC = (
    ROOT
    / "TFDU_VFIR_Client_Array"
    / "TFDU_VFIR_Client.srcs"
    / "constrs_1"
    / "new"
    / "async_clock_groups_impl.xdc"
)
FIFO_SAFETY_MD = REPORTS / "axi_dma_writefirst_fifo_safety_current.md"
FIFO_SAFETY_JSON = REPORTS / "axi_dma_writefirst_fifo_safety_current.json"
CONTROL_SETS_MD = REPORTS / "control_sets_release_blocker_current.md"
CONTROL_SETS_JSON = REPORTS / "control_sets_release_blocker_current.json"
RELEASE_PERSONALITY_MD = REPORTS / "release_personality_dcp_evidence_current.md"
RELEASE_PERSONALITY_JSON = REPORTS / "release_personality_dcp_evidence_current.json"
CONTROL_SET_HOTSPOTS_MD = REPORTS / "release_control_set_hotspots_current.md"
CONTROL_SET_HOTSPOTS_JSON = REPORTS / "release_control_set_hotspots_current.json"


def latest_active_route_dir() -> Path | None:
    candidates = [
        path
        for path in REPORTS.glob("active_2lane_route_methodology_*")
        if path.is_dir() and (path / "methodology_post_route.rpt").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def prefer_latest(active_dir: Path | None, active_name: str, fallback: Path) -> Path:
    if active_dir is not None:
        active_path = active_dir / active_name
        if active_path.exists():
            return active_path
    return fallback


@dataclass(frozen=True)
class ActionRow:
    action_id: str
    status: str
    blocker: str
    violation_count: int
    source: str
    evidence: str
    owner_area: str
    required_before: str
    next_action: str
    validation: str
    hardware_side_effect: str


@dataclass(frozen=True)
class CheckRow:
    check: str
    status: str
    expected: str
    actual: str
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
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def find_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if path.is_file() and sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def rule_count(rules: list[dict[str, Any]], rule_name: str) -> int:
    for rule in rules:
        if rule.get("rule") == rule_name:
            try:
                return int(rule.get("violations", 0))
            except (TypeError, ValueError):
                return 0
    return 0


def parse_control_sets(text: str) -> tuple[int | None, int | None, float | None]:
    match = re.search(r"uses\s+(\d+)\s+control sets.*?available limit of\s+(\d+)", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None, None, None
    used = int(match.group(1))
    limit = int(match.group(2))
    pct = (used / limit) * 100.0 if limit else None
    return used, limit, pct


def build_actions() -> tuple[list[ActionRow], list[CheckRow], dict[str, Any]]:
    constraint = find_constraint()
    active_dir = latest_active_route_dir()
    drc_path = prefer_latest(active_dir, "drc_post_route.rpt", DRC_RPT)
    meth_path = prefer_latest(active_dir, "methodology_post_route.rpt", METH_RPT)
    timing_path = prefer_latest(active_dir, "timing_summary_post_route.rpt", TIMING_RPT)
    util_path = prefer_latest(active_dir, "utilization_post_route.rpt", UTIL_RPT)
    triage = read_json(TRIAGE_JSON)
    fifo_safety = read_json(FIFO_SAFETY_JSON)
    control_sets_evidence = read_json(CONTROL_SETS_JSON)
    release_personality_evidence = read_json(RELEASE_PERSONALITY_JSON)
    control_set_hotspots_evidence = read_json(CONTROL_SET_HOTSPOTS_JSON)
    rules_raw = triage.get("rules") if isinstance(triage.get("rules"), list) else []
    rules = [rule for rule in rules_raw if isinstance(rule, dict)]
    build = triage.get("build") if isinstance(triage.get("build"), dict) else {}
    fifo_meta = fifo_safety.get("metadata") if isinstance(fifo_safety.get("metadata"), dict) else {}
    control_sets_meta = (
        control_sets_evidence.get("metadata")
        if isinstance(control_sets_evidence.get("metadata"), dict)
        else {}
    )
    release_personality_meta = (
        release_personality_evidence.get("metadata")
        if isinstance(release_personality_evidence.get("metadata"), dict)
        else {}
    )
    control_set_hotspots_meta = (
        control_set_hotspots_evidence.get("metadata")
        if isinstance(control_set_hotspots_evidence.get("metadata"), dict)
        else {}
    )

    drc_text = read_text(drc_path)
    meth_text = read_text(meth_path)
    timing_text = read_text(timing_path)
    util_text = read_text(util_path)
    async_xdc_text = read_text(ASYNC_XDC)
    used_control_sets, control_set_limit, control_set_pct = parse_control_sets(meth_text)
    timing_violation_count = rule_count(rules, "TIMING-24") + rule_count(rules, "TIMING-28")

    has_broad_clock_group = (
        "set_clock_groups -asynchronous" in async_xdc_text
        and "get_clocks clk_fpga_0" in async_xdc_text
        and "get_clocks clk_out1_design_shiboqi_clk_wiz_0_0" in async_xdc_text
    )
    if timing_violation_count == 0 and not has_broad_clock_group:
        timing_constraint_source_status = "CLEARED_BY_ROUTE_VALIDATION"
    elif has_broad_clock_group:
        timing_constraint_source_status = "OPEN_RELEASE_BLOCKER"
    else:
        timing_constraint_source_status = "CANDIDATE_APPLIED_PENDING_ROUTE_VALIDATION"
    timing_constraint_evidence = (
        "Active async_clock_groups_impl.xdc still contains the broad async clock group reported by methodology DRC."
        if has_broad_clock_group
        else "Latest routed methodology report has no TIMING-24/TIMING-28 and active XDC has no broad clock group."
        if timing_violation_count == 0
        else (
            "Active async_clock_groups_impl.xdc no longer contains the broad async clock group; routed "
            "methodology DRC must be regenerated to prove TIMING-24/TIMING-28 are cleared."
        )
    )
    has_timing_override_positions = all(f"position {pos}" in meth_text for pos in ["64", "68", "70", "72", "74"])
    has_pin_based_recommendation = (
        "get_clocks -of_objects [get_pins design_shiboqi_i/clk_wiz_0/inst/mmcm_adv_inst/CLKOUT0]"
        in meth_text
    )
    has_dma_fifo_paths = all(
        needle in drc_text
        for needle in [
            "GEN_MM2S_FULL.I_MM2S_FULL_WRAPPER",
            "GEN_S2MM_FULL.I_S2MM_FULL_WRAPPER",
            "WRITE_FIRST write-mode",
        ]
    )
    fifo_release_drc_report = str(fifo_meta.get("release_drc_report", ""))
    release_reqp181_details = (
        fifo_meta.get("release_reqp181_details")
        if isinstance(fifo_meta.get("release_reqp181_details"), list)
        else []
    )
    release_reqp181_channels = sorted(
        item.get("channel", "")
        for item in release_reqp181_details
        if isinstance(item, dict)
    )
    has_release_dma_fifo_paths = (
        int(fifo_meta.get("release_reqp181_count", 0)) == 2
        and release_reqp181_channels == ["MM2S", "S2MM"]
        and fifo_release_drc_report != ""
    )
    fifo_safety_ok = (
        fifo_meta.get("overall") == "PASS_OFFLINE_EVIDENCE_RELEASE_STILL_BLOCKED"
        and int(fifo_meta.get("reqp181_count", 0)) == rule_count(rules, "REQP-181")
        and has_release_dma_fifo_paths
        and int(fifo_meta.get("release_ready", 1)) == 0
    )
    control_sets_evidence_ok = (
        control_sets_meta.get("overall") == "PASS_CONTROL_SET_BLOCKER_EVIDENCE_RELEASE_STILL_BLOCKED"
        and int(control_sets_meta.get("total_control_sets", 0)) == (used_control_sets or 0)
        and int(control_sets_meta.get("guideline_limit", 0)) == 660
        and int(control_sets_meta.get("control_sets_over_guideline", 0)) > 0
        and int(control_sets_meta.get("release_ready", 1)) == 0
    )
    release_personality_control_set_ready = int(release_personality_meta.get("remaining_over_guideline", 1)) == 0
    release_personality_ok = (
        str(release_personality_meta.get("overall", "")).startswith("PASS_RELEASE_PERSONALITY_DCP_EVIDENCE_")
        and int(release_personality_meta.get("active_control_sets", 0)) == (used_control_sets or 0)
        and int(release_personality_meta.get("candidate_control_sets", 0)) > 0
        and int(release_personality_meta.get("candidate_control_sets", 0))
        < int(release_personality_meta.get("active_control_sets", 0))
        and int(release_personality_meta.get("debug_control_sets", -1)) == 0
        and int(release_personality_meta.get("loopback_partner_control_sets", -1)) == 0
        and int(release_personality_meta.get("remaining_over_guideline", -1)) >= 0
        and int(release_personality_meta.get("timing_24_28_count", -1)) == 0
        and int(release_personality_meta.get("release_ready", 1)) == 0
        and int(release_personality_meta.get("no_hardware_programming", 0)) == 1
        and int(release_personality_meta.get("no_tfdu_drive", 0)) == 1
    )
    release_personality_timing_note = (
        "the regenerated DCP clears TIMING-24/TIMING-28"
        if int(release_personality_meta.get("timing_24_28_count", -1)) == 0
        else "this DCP still carries stale TIMING-24/TIMING-28 and must be regenerated after the current XDC fix"
    )
    release_control_set_note = (
        "and now clears the guideline"
        if release_personality_control_set_ready
        else "but it still exceeds the guideline"
    )
    control_set_hotspots_ok = (
        str(control_set_hotspots_meta.get("overall", "")).startswith("PASS_RELEASE_CONTROL_SET_HOTSPOTS_")
        and int(control_set_hotspots_meta.get("total_control_sets", 0))
        == int(release_personality_meta.get("candidate_control_sets", -1))
        and int(control_set_hotspots_meta.get("guideline_limit", 0)) == 660
        and int(control_set_hotspots_meta.get("remaining_over_guideline", -1))
        == int(release_personality_meta.get("remaining_over_guideline", -2))
        and int(control_set_hotspots_meta.get("row_failures", -1)) == 0
        and int(control_set_hotspots_meta.get("no_hardware_programming", 0)) == 1
        and int(control_set_hotspots_meta.get("no_tfdu_drive", 0)) == 1
    )
    timing_met = "All user specified timing constraints are met." in timing_text
    utilization_matches = all(
        needle in util_text
        for needle in [
            "| Slice LUTs",
            "| Slice Registers",
            "| Block RAM Tile",
        ]
    )

    actions = [
        ActionRow(
            action_id="DRC-A01",
            status=timing_constraint_source_status,
            blocker="TIMING-24/TIMING-28",
            violation_count=timing_violation_count,
            source=f"{rel(meth_path)}; {rel(ASYNC_XDC)}",
            evidence=(
                timing_constraint_evidence
                + " Previous routed report says the broad group between clk_fpga_0 and "
                "clk_out1_design_shiboqi_clk_wiz_0_0 overrides max_delay datapath-only constraints."
            ),
            owner_area="XDC timing constraints",
            required_before="release build and 4/8-lane expansion",
            next_action=(
                "Replace broad clock-level async grouping with point-to-point CDC exceptions, and use "
                "pin-based generated clock references where needed."
            ),
            validation=(
                "Rerun implementation and methodology DRC; TIMING-24/TIMING-28 must be zero while WNS/WHS remain met."
            ),
            hardware_side_effect="none in this map",
        ),
        ActionRow(
            action_id="DRC-A02",
            status="OPEN_RELEASE_BLOCKER_EVIDENCE_ADDED",
            blocker="REQP-181",
            violation_count=rule_count(rules, "REQP-181"),
            source="; ".join(
                item
                for item in [rel(drc_path), fifo_release_drc_report, rel(FIFO_SAFETY_MD)]
                if item
            ),
            evidence=(
                "AXI DMA MM2S and S2MM data FIFOs use synchronous SDP BRAM WRITE_FIRST mode, which needs "
                "collision exclusion evidence or IP/config mitigation. Offline evidence now confirms the "
                "same MM2S/S2MM REQP-181 paths in the current 8-lane fragment=16 release candidate DRC, "
                "confirms the PS uses simple DMA with packet-level idle/recovery guards, and shows that a "
                "conservative FIFO controller avoids same-address collision while a permissive full+read "
                "bypass can collide."
            ),
            owner_area="AXI DMA / PS traffic validation",
            required_before="release build and real PS-PC throughput acceptance",
            next_action=(
                "Run real PS DMA stress and/or IP-level simulation/formal evidence for the AXI DMA MM2S/S2MM "
                "FIFO paths. Evaluate a READ_FIRST-capable mitigation only if collision exclusion is not provable."
            ),
            validation=(
                "Evidence must cover sustained half-duplex and full-duplex target envelopes; offline FIFO "
                "model evidence alone is not a release waiver."
            ),
            hardware_side_effect="none in this map",
        ),
        ActionRow(
            action_id="DRC-A03",
            status=(
                "CLEARED_BY_RELEASE_PERSONALITY_DCP"
                if release_personality_ok and release_personality_control_set_ready and control_set_hotspots_ok
                else "OPEN_EXPANSION_BLOCKER_EVIDENCE_ADDED"
            ),
            blocker="ULMTCS-2",
            violation_count=(
                0
                if release_personality_ok and release_personality_control_set_ready and control_set_hotspots_ok
                else rule_count(rules, "ULMTCS-2")
            ),
            source=f"{rel(meth_path)}; {rel(CONTROL_SETS_MD)}; {rel(RELEASE_PERSONALITY_MD)}; {rel(CONTROL_SET_HOTSPOTS_MD)}",
            evidence=(
                f"Control sets used={used_control_sets if used_control_sets is not None else 'unknown'} "
                f"limit={control_set_limit if control_set_limit is not None else 'unknown'} "
                f"pct={control_set_pct:.2f}%. Offline control-set evidence shows guideline_limit="
                f"{control_sets_meta.get('guideline_limit', 'unknown')}, reduction_needed="
                f"{control_sets_meta.get('control_sets_over_guideline', 'unknown')}, debug_sets="
                f"{control_sets_meta.get('debug_control_sets', 'unknown')}, and loopback_partner_sets="
                f"{control_sets_meta.get('loopback_partner_control_sets', 'unknown')}. Release-personality DCP "
                f"evidence removes debug/loopback categories (debug_sets="
                f"{release_personality_meta.get('debug_control_sets', 'unknown')}, loopback_partner_sets="
                f"{release_personality_meta.get('loopback_partner_control_sets', 'unknown')}) and reduces "
                f"control sets active={release_personality_meta.get('active_control_sets', 'unknown')} "
                f"candidate={release_personality_meta.get('candidate_control_sets', 'unknown')} "
                f"reduction={release_personality_meta.get('control_set_reduction_vs_active', 'unknown')}, "
                f"{release_control_set_note} by "
                f"{release_personality_meta.get('remaining_over_guideline', 'unknown')}; "
                f"{release_personality_timing_note}. Latest hotspot evidence from the release DCP keeps "
                f"total={control_set_hotspots_meta.get('total_control_sets', 'unknown')}, "
                f"remaining={control_set_hotspots_meta.get('remaining_over_guideline', 'unknown')}, "
                f"lane_sets={control_set_hotspots_meta.get('lane_control_sets', 'unknown')}, "
                f"manager_sets={control_set_hotspots_meta.get('manager_control_sets', 'unknown')}, and "
                f"user_ir_enable_and_reset_sets={control_set_hotspots_meta.get('user_ir_enable_and_reset_sets', 'unknown')}."
                if control_set_pct is not None
                else "Control-set guideline violation is present, but numeric details were not parsed."
            ),
            owner_area="RTL reset/enable structure and generated IP settings",
            required_before="4/8-lane scaling or release signoff",
            next_action=(
                "Keep the explicit release-personality CONTROL_SET_REMAP hook for u_sink/frame_data and rerun "
                "bitstream/signoff evidence from that profile. No further ULMTCS-2 reduction is needed unless "
                "a later release DCP regresses above the 660 guideline."
                if release_personality_ok and release_personality_control_set_ready and control_set_hotspots_ok
                else "Split release from debug/board-internal loopback personality first, then optimize reset/enable "
                "structures in the remaining release IR datapath; the threshold=16 synthesis trial did not reduce "
                "the 850 release control sets."
            ),
            validation=(
                "Release-personality DCP methodology/control-set reports must stay below the 660 guideline, "
                "with routed timing/resource margin preserved."
                if release_personality_ok and release_personality_control_set_ready and control_set_hotspots_ok
                else "Methodology DRC ULMTCS-2 must clear, or a formal waiver must tie control-set use to routed "
                "timing/resource margin for the chosen lane count."
            ),
            hardware_side_effect="none in this map",
        ),
        ActionRow(
            action_id="DRC-A04",
            status="DEBUG_ONLY_WAIVER_CANDIDATE",
            blocker="PDCN-1569/RTSTAT-10/LUTAR-1/PDRC-190",
            violation_count=sum(
                rule_count(rules, rule_name)
                for rule_name in ["PDCN-1569", "RTSTAT-10", "LUTAR-1", "PDRC-190"]
            ),
            source=f"{rel(drc_path)}; {rel(meth_path)}",
            evidence=(
                "Warnings are currently separated as debug/generated-IP waiver candidates and are not counted as "
                "release-ready."
            ),
            owner_area="debug hub / generated IP / release build configuration",
            required_before="release signoff",
            next_action=(
                "Rebuild a release configuration without debug ILA where applicable, regenerate IP if required, "
                "then decide whether remaining generated-IP warnings need waivers."
            ),
            validation="Release DRC report must have no unclassified warnings, or each remaining warning must have a waiver.",
            hardware_side_effect="none in this map",
        ),
    ]

    checks = [
        CheckRow(
            "hard_constraint_unchanged",
            "PASS" if constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL",
            EXPECTED_CONSTRAINT_SHA256,
            sha256(constraint),
            "This action map does not modify the hard target constraint.",
        ),
        CheckRow(
            "triage_json_present",
            "PASS" if TRIAGE_JSON.exists() and len(rules) >= 6 else "FAIL",
            "current DRC triage JSON with at least 6 rules after cleared timing blockers",
            f"{rel(TRIAGE_JSON)} rules={len(rules)}",
            "Uses the existing routed DRC/methodology triage.",
        ),
        CheckRow(
            "raw_reports_present",
            "PASS" if all(path.exists() for path in [drc_path, meth_path, timing_path, util_path]) else "FAIL",
            "routed DRC, methodology, timing, utilization reports",
            ", ".join(rel(path) for path in [drc_path, meth_path, timing_path, util_path] if path.exists()),
            "Action rows are grounded in routed Vivado report artifacts.",
        ),
        CheckRow(
            "active_broad_clock_group_removed_or_identified",
            "PASS",
            "broad clock group either removed in source or explicitly identified as open",
            (
                "removed_from_active_xdc"
                if not has_broad_clock_group
                else f"still_present_in={rel(ASYNC_XDC)}"
            ),
            "Source-side candidate edit is allowed, but release remains blocked until routed methodology DRC is regenerated.",
        ),
        CheckRow(
            "methodology_positions_identified",
            "PASS"
            if timing_violation_count == 0
            or (has_timing_override_positions and has_pin_based_recommendation)
            else "FAIL",
            "TIMING-24/TIMING-28 cleared, or positions 64/68/70/72/74 and pin recommendation identify the open issue",
            (
                "cleared_in_latest_methodology"
                if timing_violation_count == 0
                else f"positions={has_timing_override_positions} pin_ref={has_pin_based_recommendation}"
            ),
            "The fix target is the broad clock exception when present, not functional RTL.",
        ),
        CheckRow(
            "dma_fifo_paths_identified",
            "PASS" if has_dma_fifo_paths else "FAIL",
            "MM2S/S2MM WRITE_FIRST FIFO paths",
            f"REQP-181 count={rule_count(rules, 'REQP-181')}",
            "REQP-181 is tied to AXI DMA FIFO collision review.",
        ),
        CheckRow(
            "release_candidate_dma_fifo_paths_identified",
            "PASS" if has_release_dma_fifo_paths else "FAIL",
            "current release 8-lane fragment=16 DRC has MM2S/S2MM REQP-181 paths",
            f"release_reqp181={fifo_meta.get('release_reqp181_count', 'MISSING')} channels={','.join(release_reqp181_channels) or 'none'} report={fifo_release_drc_report or 'MISSING'}",
            "The remaining REQP-181 blocker is present in the current reduced 8-lane release-personality candidate, not only in the active 2-lane debug route.",
        ),
        CheckRow(
            "dma_fifo_offline_evidence_present",
            "PASS" if fifo_safety_ok else "FAIL",
            "offline FIFO model exists, ties active/release DRC paths, passes, and still marks release_ready=0",
            f"{rel(FIFO_SAFETY_JSON)} overall={fifo_meta.get('overall', 'MISSING')} reqp181={fifo_meta.get('reqp181_count', 'MISSING')} release_reqp181={fifo_meta.get('release_reqp181_count', 'MISSING')}",
            "This adds review evidence for REQP-181 without clearing the release blocker.",
        ),
        CheckRow(
            "control_set_count_identified",
            "PASS" if used_control_sets is not None and control_set_limit is not None else "FAIL",
            "ULMTCS-2 numeric control-set count",
            (
                f"used={used_control_sets} limit={control_set_limit} pct={control_set_pct:.2f}%"
                if control_set_pct is not None
                else "missing"
            ),
            "Control-set issue is expansion/release risk, not a current routed timing failure.",
        ),
        CheckRow(
            "control_set_evidence_present",
            "PASS" if control_sets_evidence_ok else "FAIL",
            "control-set evidence exists, passes, and still marks release_ready=0",
            (
                f"{rel(CONTROL_SETS_JSON)} overall={control_sets_meta.get('overall', 'MISSING')} "
                f"total={control_sets_meta.get('total_control_sets', 'MISSING')} "
                f"reduction_needed={control_sets_meta.get('control_sets_over_guideline', 'MISSING')}"
            ),
            "This turns ULMTCS-2 into a quantified action without clearing the release blocker.",
        ),
        CheckRow(
            "release_personality_dcp_evidence_present",
            "PASS" if release_personality_ok else "FAIL",
            "external release-personality DCP evidence removes debug/loopback, improves control sets, and still marks release_ready=0",
            (
                f"{rel(RELEASE_PERSONALITY_JSON)} overall={release_personality_meta.get('overall', 'MISSING')} "
                f"active={release_personality_meta.get('active_control_sets', 'MISSING')} "
                f"candidate={release_personality_meta.get('candidate_control_sets', 'MISSING')} "
                f"reduction={release_personality_meta.get('control_set_reduction_vs_active', 'MISSING')} "
                f"remaining={release_personality_meta.get('remaining_over_guideline', 'MISSING')} "
                f"timing24_28={release_personality_meta.get('timing_24_28_count', 'MISSING')}"
            ),
            "This validates the release-personality reduction path without clearing ULMTCS-2.",
        ),
        CheckRow(
            "control_set_hotspot_evidence_present",
            "PASS" if control_set_hotspots_ok else "FAIL",
            "latest release control-set hotspot evidence exists, matches the current release DCP, and still marks release_ready=0",
            (
                f"{rel(CONTROL_SET_HOTSPOTS_JSON)} overall={control_set_hotspots_meta.get('overall', 'MISSING')} "
                f"total={control_set_hotspots_meta.get('total_control_sets', 'MISSING')} "
                f"remaining={control_set_hotspots_meta.get('remaining_over_guideline', 'MISSING')} "
                f"lane_sets={control_set_hotspots_meta.get('lane_control_sets', 'MISSING')} "
                f"manager_sets={control_set_hotspots_meta.get('manager_control_sets', 'MISSING')}"
            ),
            "This narrows ULMTCS-2 to lane-local sink and TX/RX manager reset/enable structure.",
        ),
        CheckRow(
            "debug_build_still_timing_clean",
            "PASS" if timing_met and float(build.get("timing_wns_ns", -1.0)) >= 0.0 else "FAIL",
            "current routed debug build timing met",
            f"WNS={build.get('timing_wns_ns')} WHS={build.get('timing_whs_ns')} timing_met={timing_met}",
            "Debug bring-up can continue while release blockers remain open.",
        ),
        CheckRow(
            "utilization_context_present",
            "PASS" if utilization_matches else "FAIL",
            "utilization report includes LUT/register/BRAM context",
            rel(util_path),
            "The map preserves resource context for expansion decisions.",
        ),
        CheckRow(
            "no_hardware_side_effects",
            "PASS",
            "no FPGA programming, UART write, TFDU drive, Vivado run, or bitstream generation",
            "read-only Python report generation",
            "This script only reads reports and writes reports/drc_release_action_map_current.*.",
        ),
    ]

    release_blocking = [row for row in actions if row.status.startswith("OPEN_")]
    row_failures = sum(1 for row in checks if row.status != "PASS")
    metadata = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "overall": "PASS_ACTION_MAP_RELEASE_STILL_BLOCKED" if row_failures == 0 else "FAIL_ACTION_MAP",
        "release_ready": 0,
        "debug_can_continue": int(row_failures == 0),
        "action_count": len(actions),
        "open_release_or_expansion_actions": len(release_blocking),
        "release_blocking_violation_count": sum(row.violation_count for row in release_blocking),
        "timing_constraint_source_status": timing_constraint_source_status,
        "row_failures": row_failures,
        "constraint_sha256": sha256(constraint),
        "triage_json": rel(TRIAGE_JSON),
        "active_route_dir": rel(active_dir) if active_dir is not None else "",
        "drc_report": rel(drc_path),
        "methodology_report": rel(meth_path),
        "timing_report": rel(timing_path),
        "utilization_report": rel(util_path),
        "async_clock_xdc": rel(ASYNC_XDC),
        "fifo_safety_report": rel(FIFO_SAFETY_MD),
        "fifo_safety_json": rel(FIFO_SAFETY_JSON),
        "fifo_safety_overall": fifo_meta.get("overall", "MISSING"),
        "control_sets_report": rel(CONTROL_SETS_MD),
        "control_sets_json": rel(CONTROL_SETS_JSON),
        "control_sets_overall": control_sets_meta.get("overall", "MISSING"),
        "release_personality_report": rel(RELEASE_PERSONALITY_MD),
        "release_personality_json": rel(RELEASE_PERSONALITY_JSON),
        "release_personality_overall": release_personality_meta.get("overall", "MISSING"),
        "release_personality_candidate_control_sets": release_personality_meta.get("candidate_control_sets", "MISSING"),
        "release_personality_reduction": release_personality_meta.get("control_set_reduction_vs_active", "MISSING"),
        "release_personality_remaining_over_guideline": release_personality_meta.get("remaining_over_guideline", "MISSING"),
        "release_personality_timing_24_28_count": release_personality_meta.get("timing_24_28_count", "MISSING"),
        "control_set_hotspots_report": rel(CONTROL_SET_HOTSPOTS_MD),
        "control_set_hotspots_json": rel(CONTROL_SET_HOTSPOTS_JSON),
        "control_set_hotspots_overall": control_set_hotspots_meta.get("overall", "MISSING"),
        "control_set_hotspots_total": control_set_hotspots_meta.get("total_control_sets", "MISSING"),
        "control_set_hotspots_remaining": control_set_hotspots_meta.get("remaining_over_guideline", "MISSING"),
        "control_set_hotspots_lane_sets": control_set_hotspots_meta.get("lane_control_sets", "MISSING"),
        "control_set_hotspots_manager_sets": control_set_hotspots_meta.get("manager_control_sets", "MISSING"),
        "no_hardware_programming": 1,
        "no_uart_write": 1,
        "no_tfdu_drive": 1,
        "no_vivado_run": 1,
    }
    return actions, checks, metadata


def table(headers: list[str], rows: list[list[Any]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("\n", " ").replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def write_reports(actions: list[ActionRow], checks: list[CheckRow], metadata: dict[str, Any]) -> tuple[Path, Path, Path]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    md_path = REPORTS / "drc_release_action_map_current.md"
    json_path = REPORTS / "drc_release_action_map_current.json"
    csv_path = REPORTS / "drc_release_action_map_current.csv"

    md = "\n".join(
        [
            "# DRC Release Action Map",
            "",
            f"Generated: {metadata['generated']}",
            "",
            "## Verdict",
            "",
            f"- Overall: `{metadata['overall']}`",
            f"- Release ready: `{metadata['release_ready']}`",
            f"- Debug can continue: `{metadata['debug_can_continue']}`",
            f"- Action count: `{metadata['action_count']}`",
            f"- Release-blocking violation count: `{metadata['release_blocking_violation_count']}`",
            "- No hardware programming: `1`",
            "- No UART write: `1`",
            "- No TFDU drive: `1`",
            "- No Vivado run: `1`",
            "",
            "This is an internal engineering map from routed DRC/methodology blockers to concrete pre-release actions. It is not a consulting bundle and it does not change RTL, XDC, software, bitstreams, or the hard target constraint.",
            "",
            "## Actions",
            "",
            table(
                [
                    "action_id",
                    "status",
                    "blocker",
                    "violations",
                    "source",
                    "owner_area",
                    "required_before",
                    "next_action",
                    "validation",
                ],
                [
                    [
                        row.action_id,
                        row.status,
                        row.blocker,
                        row.violation_count,
                        row.source,
                        row.owner_area,
                        row.required_before,
                        row.next_action,
                        row.validation,
                    ]
                    for row in actions
                ],
            ),
            "",
            "## Checks",
            "",
            table(
                ["check", "status", "expected", "actual", "note"],
                [[row.check, row.status, row.expected, row.actual, row.note] for row in checks],
            ),
            "",
            "```text",
            f"RF_COMM_DRC_RELEASE_ACTION_MAP overall={metadata['overall']} release_ready={metadata['release_ready']} debug_can_continue={metadata['debug_can_continue']} actions={metadata['action_count']} release_blocking={metadata['release_blocking_violation_count']} row_failures={metadata['row_failures']}",
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
                "actions": [asdict(row) for row in actions],
                "checks": [asdict(row) for row in checks],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(actions[0]).keys()))
        writer.writeheader()
        for row in actions:
            writer.writerow(asdict(row))
    return md_path, json_path, csv_path


def main() -> int:
    actions, checks, metadata = build_actions()
    md_path, json_path, csv_path = write_reports(actions, checks, metadata)
    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(
        "RF_COMM_DRC_RELEASE_ACTION_MAP "
        f"overall={metadata['overall']} "
        f"release_ready={metadata['release_ready']} "
        f"debug_can_continue={metadata['debug_can_continue']} "
        f"actions={metadata['action_count']} "
        f"release_blocking={metadata['release_blocking_violation_count']} "
        f"row_failures={metadata['row_failures']}"
    )
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("NO_VIVADO_RUN=1")
    return 0 if metadata["row_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
