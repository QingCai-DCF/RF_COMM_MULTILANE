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
DATE_TAG = "20260626"


@dataclass
class AuditItem:
    item_id: str
    requirement: str
    status: str
    evidence: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists():
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
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def latest(pattern: str) -> Path | None:
    matches = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def latest_containing(pattern: str, needles: Iterable[str]) -> Path | None:
    for path in sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True):
        text = read_text(path)
        if all(needle in text for needle in needles):
            return path
    return None


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def load_post_gate_rows(csv_path: Path | None) -> dict[str, dict[str, str]]:
    if csv_path is None or not csv_path.exists():
        return {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        return {row.get("name", ""): row for row in csv.DictReader(f)}


def case_pass(rows: dict[str, dict[str, str]], name: str) -> bool:
    row = rows.get(name, {})
    return (
        row.get("status") == "PASS"
        and row.get("exit_code") == "0"
        and row.get("timed_out") == "0"
        and row.get("pass_seen") == "1"
    )


def all_cases_pass(rows: dict[str, dict[str, str]], names: Iterable[str]) -> bool:
    return all(case_pass(rows, name) for name in names)


def extract_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def extract_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def line_count(text: str, line: str) -> int:
    return sum(1 for candidate in text.splitlines() if candidate.strip() == line)


def build_audit() -> tuple[list[AuditItem], dict[str, str]]:
    constraint = find_hard_constraint()
    g1_report = REPORTS / "G1_acceptance_report.md"
    post_status = REPORTS / "post_g1_target_status_current.md"
    post_csv = latest("reports/post_g1_target_sim_gate_*.cases.csv")
    post_summary = latest("reports/post_g1_target_sim_gate_*.summary.txt")
    rate_options_md = latest("reports/effective_payload_rate_options_*.md")
    rate_options_csv = latest("reports/effective_payload_rate_options_*.csv")
    rate_boundary_md = latest("reports/rate_boundary_proof_*.md")
    rate_boundary_json = latest("reports/rate_boundary_proof_*.json")
    payload_gap_closure_md = REPORTS / "payload_gap_closure_current.md"
    payload_gap_closure_json = REPORTS / "payload_gap_closure_current.json"
    payload_gap_closure_csv = REPORTS / "payload_gap_closure_current.csv"
    target_consistency_md = latest("reports/target_consistency_check_*.md")
    target_consistency_json = latest("reports/target_consistency_check_*.json")
    status_consistency_md = REPORTS / "full_target_status_consistency_current.md"
    status_consistency_json = REPORTS / "full_target_status_consistency_current.json"
    status_consistency_csv = REPORTS / "full_target_status_consistency_current.csv"
    external_preconditions_md = REPORTS / "external_preconditions_current.md"
    external_preconditions_json = REPORTS / "external_preconditions_current.json"
    external_preconditions_csv = REPORTS / "external_preconditions_current.csv"
    real_acceptance_runbook_md = REPORTS / "real_acceptance_runbook_current.md"
    real_acceptance_runbook_json = REPORTS / "real_acceptance_runbook_current.json"
    real_acceptance_runbook_csv = REPORTS / "real_acceptance_runbook_current.csv"
    real_acceptance_sequence_summary = REPORTS / "real_acceptance_sequence_safe_current.summary.txt"
    real_acceptance_sequence_md = REPORTS / "real_acceptance_sequence_safe_current.md"
    real_acceptance_sequence_json = REPORTS / "real_acceptance_sequence_safe_current.json"
    real_acceptance_sequence_csv = REPORTS / "real_acceptance_sequence_safe_current.stages.csv"
    protocol_contract_md = REPORTS / "protocol_contract_current.md"
    protocol_contract_json = REPORTS / "protocol_contract_current.json"
    protocol_contract_csv = REPORTS / "protocol_contract_current.csv"
    ps_lwip_bridge_static_md = REPORTS / "ps_lwip_bridge_static_current.md"
    ps_lwip_bridge_static_json = REPORTS / "ps_lwip_bridge_static_current.json"
    ps_lwip_bridge_static_csv = REPORTS / "ps_lwip_bridge_static_current.csv"
    ps_pc_offline_summary = latest_containing(
        "reports/ps_pc_offline_gates_*.summary.txt",
        [
            "PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1",
            "STEP_STDERR name=host_client_unittest Ran 21 tests",
            "STEP_STDOUT name=host_offline_mock_acceptance log_acceptance PASS",
            "reconnect cycle 4/4",
        ],
    )
    ps_pc_offline_unittest = (
        None
        if ps_pc_offline_summary is None
        else ps_pc_offline_summary.with_name(
            ps_pc_offline_summary.name.replace(".summary.txt", ".unittest.log")
        )
    )
    ps_pc_offline_acceptance = (
        None
        if ps_pc_offline_summary is None
        else ps_pc_offline_summary.with_name(
            ps_pc_offline_summary.name.replace(".summary.txt", ".acceptance.log")
        )
    )
    two_ax7010_model_md = REPORTS / "two_ax7010_end_to_end_model_current.md"
    two_ax7010_model_json = REPORTS / "two_ax7010_end_to_end_model_current.json"
    two_ax7010_model_csv = REPORTS / "two_ax7010_end_to_end_model_current.csv"
    host_status_snapshot_md = REPORTS / "host_status_snapshot_current.md"
    host_status_snapshot_json = REPORTS / "host_status_snapshot_current.json"
    host_status_snapshot_csv = REPORTS / "host_status_snapshot_current.csv"
    no_ethernet_network_boundary_md = REPORTS / "no_ethernet_network_boundary_evidence_current.md"
    no_ethernet_network_boundary_json = REPORTS / "no_ethernet_network_boundary_evidence_current.json"
    no_ethernet_network_boundary_csv = REPORTS / "no_ethernet_network_boundary_evidence_current.csv"
    target_matrix_md = REPORTS / "target_acceptance_matrix_current.md"
    target_matrix_json = REPORTS / "target_acceptance_matrix_current.json"
    target_matrix_csv = REPORTS / "target_acceptance_matrix_current.csv"
    full_system_twin_md = REPORTS / "full_system_capped_digital_twin_current.md"
    full_system_twin_json = REPORTS / "full_system_capped_digital_twin_current.json"
    full_system_twin_csv = REPORTS / "full_system_capped_digital_twin_current.csv"
    full_system_envelope_md = REPORTS / "full_system_offline_target_envelope_current.md"
    full_system_envelope_json = REPORTS / "full_system_offline_target_envelope_current.json"
    full_system_envelope_csv = REPORTS / "full_system_offline_target_envelope_current.csv"
    rotating_autoroute_offline_md = REPORTS / "rotating_autoroute_offline_evidence_current.md"
    rotating_autoroute_offline_json = REPORTS / "rotating_autoroute_offline_evidence_current.json"
    rotating_autoroute_offline_csv = REPORTS / "rotating_autoroute_offline_evidence_current.csv"
    topology_capacity_md = REPORTS / "topology_capacity_plan_current.md"
    topology_capacity_json = REPORTS / "topology_capacity_plan_current.json"
    topology_capacity_csv = REPORTS / "topology_capacity_plan_current.csv"
    remaining_hw_plan_md = REPORTS / "remaining_hardware_acceptance_plan_current.md"
    remaining_hw_plan_json = REPORTS / "remaining_hardware_acceptance_plan_current.json"
    remaining_hw_plan_csv = REPORTS / "remaining_hardware_acceptance_plan_current.csv"
    remaining_acceptance_readiness_md = REPORTS / "remaining_acceptance_readiness_current.md"
    remaining_acceptance_readiness_json = REPORTS / "remaining_acceptance_readiness_current.json"
    remaining_acceptance_readiness_csv = REPORTS / "remaining_acceptance_readiness_current.csv"
    rotating_fixture_validation_md = REPORTS / "rotating_fixture_log_validation_current.md"
    rotating_fixture_validation_json = REPORTS / "rotating_fixture_log_validation_current.json"
    rotating_fixture_validation_csv = REPORTS / "rotating_fixture_log_validation_current.csv"
    rotating_fixture_template = REPORTS / "rotating_fixture_log_template.csv"
    real_acceptance_validation_md = REPORTS / "real_acceptance_evidence_validation_current.md"
    real_acceptance_validation_json = REPORTS / "real_acceptance_evidence_validation_current.json"
    real_acceptance_validation_csv = REPORTS / "real_acceptance_evidence_validation_current.csv"
    real_acceptance_validator_selftest_md = REPORTS / "real_acceptance_validator_selftest_current.md"
    real_acceptance_validator_selftest_json = REPORTS / "real_acceptance_validator_selftest_current.json"
    real_acceptance_validator_selftest_csv = REPORTS / "real_acceptance_validator_selftest_current.csv"
    real_acceptance_promotion_gate_md = REPORTS / "real_acceptance_promotion_gate_current.md"
    real_acceptance_promotion_gate_json = REPORTS / "real_acceptance_promotion_gate_current.json"
    real_acceptance_promotion_gate_csv = REPORTS / "real_acceptance_promotion_gate_current.csv"
    duration_cap_compliance_md = REPORTS / "duration_cap_compliance_current.md"
    duration_cap_compliance_json = REPORTS / "duration_cap_compliance_current.json"
    duration_cap_compliance_csv = REPORTS / "duration_cap_compliance_current.csv"
    safe_wrapper_guard_md = REPORTS / "safe_wrapper_guard_contract_current.md"
    safe_wrapper_guard_json = REPORTS / "safe_wrapper_guard_contract_current.json"
    safe_wrapper_guard_csv = REPORTS / "safe_wrapper_guard_contract_current.csv"
    drc_release_gate_md = REPORTS / "drc_release_gate_current.md"
    drc_release_gate_json = REPORTS / "drc_release_gate_current.json"
    drc_release_gate_csv = REPORTS / "drc_release_gate_current.csv"
    real_acceptance_template_dir = REPORTS / "real_acceptance_template"
    real_acceptance_template_manifest = real_acceptance_template_dir / "real_acceptance_template_manifest.csv"
    two_ax7010_summary_template = real_acceptance_template_dir / "two_ax7010_summary_template.txt"
    two_ax7010_criteria_template = real_acceptance_template_dir / "two_ax7010_criteria_template.csv"
    product_loop_summary_template = real_acceptance_template_dir / "product_loop_summary_template.txt"
    product_loop_criteria_template = real_acceptance_template_dir / "product_loop_criteria_template.csv"
    rotating_shaft_summary_template = real_acceptance_template_dir / "rotating_shaft_summary_template.txt"
    rotating_shaft_criteria_template = real_acceptance_template_dir / "rotating_shaft_criteria_template.csv"
    eight_lane_summary_template = real_acceptance_template_dir / "eight_lane_summary_template.txt"
    eight_lane_criteria_template = real_acceptance_template_dir / "eight_lane_criteria_template.csv"
    eightlane_readiness_md = REPORTS / "8lane_hardware_readiness_current.md"
    eightlane_readiness_json = REPORTS / "8lane_hardware_readiness_current.json"
    eightlane_readiness_csv = REPORTS / "8lane_hardware_readiness_current.csv"
    eightlane_shutdown_build_md = REPORTS / "8lane_shutdown_build_current.md"
    eightlane_shutdown_build_json = REPORTS / "8lane_shutdown_build_current.json"
    eightlane_shutdown_build_csv = REPORTS / "8lane_shutdown_build_current.csv"
    eightlane_candidate_project_md = REPORTS / "8lane_candidate_project_build_current.md"
    eightlane_candidate_project_json = REPORTS / "8lane_candidate_project_build_current.json"
    eightlane_candidate_project_csv = REPORTS / "8lane_candidate_project_build_current.csv"
    eightlane_external_project_md = REPORTS / "8lane_external_project_build_current.md"
    eightlane_external_project_json = REPORTS / "8lane_external_project_build_current.json"
    eightlane_external_project_csv = REPORTS / "8lane_external_project_build_current.csv"
    external_lane_scan_md = REPORTS / "external_lane_resource_scan_current.md"
    external_lane_scan_json = REPORTS / "external_lane_resource_scan_current.json"
    external_lane_scan_csv = REPORTS / "external_lane_resource_scan_current.csv"
    external_option_scan_md = REPORTS / "external_resource_option_scan_current.md"
    external_option_scan_json = REPORTS / "external_resource_option_scan_current.json"
    external_option_scan_csv = REPORTS / "external_resource_option_scan_current.csv"
    external_reduced_lane_scan_md = REPORTS / "external_reduced_lane_resource_scan_current.md"
    external_reduced_lane_scan_json = REPORTS / "external_reduced_lane_resource_scan_current.json"
    external_reduced_lane_scan_csv = REPORTS / "external_reduced_lane_resource_scan_current.csv"
    external_reduced_5to8_md = REPORTS / "external_reduced_5to8_extension_current.md"
    external_reduced_5to8_json = REPORTS / "external_reduced_5to8_extension_current.json"
    external_reduced_5to8_csv = REPORTS / "external_reduced_5to8_extension_current.csv"
    external_reduced_5lane_frag32_md = REPORTS / "external_reduced_5lane_frag32_current.md"
    external_reduced_5lane_frag32_json = REPORTS / "external_reduced_5lane_frag32_current.json"
    external_reduced_5lane_frag32_csv = REPORTS / "external_reduced_5lane_frag32_current.csv"
    external_reduced_5lane_frag32_route_md = REPORTS / "external_reduced_5lane_frag32_route_current.md"
    external_reduced_5lane_frag32_route_json = REPORTS / "external_reduced_5lane_frag32_route_current.json"
    external_reduced_5lane_frag32_route_csv = REPORTS / "external_reduced_5lane_frag32_route_current.csv"
    external_reduced_5lane_frag32_bitstream_md = REPORTS / "external_reduced_5lane_frag32_bitstream_current.md"
    external_reduced_5lane_frag32_bitstream_json = REPORTS / "external_reduced_5lane_frag32_bitstream_current.json"
    external_reduced_5lane_frag32_bitstream_csv = REPORTS / "external_reduced_5lane_frag32_bitstream_current.csv"
    external_reduced_8lane_frag16_bitstream_md = REPORTS / "external_reduced_8lane_frag16_bitstream_current.md"
    external_reduced_8lane_frag16_bitstream_json = REPORTS / "external_reduced_8lane_frag16_bitstream_current.json"
    external_reduced_8lane_frag16_bitstream_csv = REPORTS / "external_reduced_8lane_frag16_bitstream_current.csv"
    external_reduced_route_md = REPORTS / "external_reduced_2lane_route_current.md"
    external_reduced_route_json = REPORTS / "external_reduced_2lane_route_current.json"
    external_reduced_route_csv = REPORTS / "external_reduced_2lane_route_current.csv"
    external_reduced_4lane_route_md = REPORTS / "external_reduced_4lane_route_current.md"
    external_reduced_4lane_route_json = REPORTS / "external_reduced_4lane_route_current.json"
    external_reduced_4lane_route_csv = REPORTS / "external_reduced_4lane_route_current.csv"
    external_reduced_4lane_bitstream_md = REPORTS / "external_reduced_4lane_bitstream_current.md"
    external_reduced_4lane_bitstream_json = REPORTS / "external_reduced_4lane_bitstream_current.json"
    external_reduced_4lane_bitstream_csv = REPORTS / "external_reduced_4lane_bitstream_current.csv"
    external_reduced_4lane_bringup_md = REPORTS / "external_reduced_4lane_bringup_plan_current.md"
    external_reduced_4lane_bringup_json = REPORTS / "external_reduced_4lane_bringup_plan_current.json"
    external_reduced_4lane_bringup_csv = REPORTS / "external_reduced_4lane_bringup_plan_current.csv"
    board_tcp_summary = latest("reports/ps_pc_tcp_dhcp_acceptance_safe_*.summary.txt")
    no_ethernet_network_summary = latest_containing(
        "reports/no_ethernet_network_offline_acceptance_*.summary.txt",
        [
            "NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS=1",
            "NO_ETHERNET_NETWORK_OFFLINE_PASS_COUNT=11",
            "NO_ETHERNET_NETWORK_OFFLINE_FAIL_COUNT=0",
            "NO_REAL_BOARD_TCP_DHCP=1",
            "NO_REAL_TWO_AX7010_TRAFFIC=1",
            "NO_TFDU_DRIVE=1",
        ],
    )
    no_ethernet_network_csv = latest_containing(
        "reports/no_ethernet_network_offline_acceptance_*.cases.csv",
        [
            "ps_bridge_static",
            "host_client_unittest",
            "host_offline_mock_acceptance",
            "two_ax7010_direct_offline_model",
            "network_fault_recovery_model",
            "board_tcp_safe_dry_run",
            "two_ax7010_safe_wrapper_offline_model",
            "two_ax7010_safe_wrapper_dry_run_cap",
            "rotating_shaft_safe_wrapper_dry_run_cap",
            "product_loop_safe_wrapper_dry_run_cap",
            "eight_lane_hardware_safe_wrapper_dry_run_cap",
        ],
    )
    boot_audit_md = REPORTS / "boot_artifact_audit_current.md"
    boot_audit_json = REPORTS / "boot_artifact_audit_current.json"
    two_ax7010_safe_wrapper = ROOT / "tools" / "run_two_ax7010_end_to_end_acceptance_safe.ps1"
    rotating_shaft_safe_wrapper = ROOT / "tools" / "run_rotating_shaft_acceptance_safe.ps1"
    rotating_fixture_validator = ROOT / "tools" / "validate_rotating_fixture_log.py"
    real_acceptance_validator = ROOT / "tools" / "validate_real_acceptance_evidence.py"
    product_loop_safe_wrapper = ROOT / "tools" / "run_product_loop_acceptance_safe.ps1"
    eightlane_hw_safe_wrapper = ROOT / "tools" / "run_8lane_hardware_acceptance_safe.ps1"
    two_ax7010_offline_summary = latest_containing(
        "reports/two_ax7010_end_to_end_acceptance_safe_*.summary.txt",
        [
            "TWO_AX7010_OFFLINE_MODEL_PASS=1",
            "TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=1",
            "TWO_AX7010_BLOCKED_REASON=real_two_board_ethernet_not_run",
            "NO_TX_DATA_TO_REAL_BOARDS=1",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1",
        ],
    )
    two_ax7010_dryrun_summary = latest_containing(
        "reports/two_ax7010_end_to_end_acceptance_safe_*.summary.txt",
        [
            "TWO_AX7010_DRY_RUN=1",
            "CONTINUOUS_RUNTIME_CAP_APPLIED=1",
            "DURATION_SECONDS_EFFECTIVE=600",
            "NO_TX_DATA_TO_REAL_BOARDS=1",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1",
        ],
    )
    rotating_shaft_dryrun_summary = latest_containing(
        "reports/rotating_shaft_acceptance_safe_*.summary.txt",
        [
            "ROTATING_SHAFT_DRY_RUN=1",
            "CONTINUOUS_RUNTIME_CAP_APPLIED=1",
            "DURATION_SECONDS_EFFECTIVE=600",
            "SHAFT_DIAMETER_MM=200",
            "RPM=600",
            "NO_TX_DATA_TO_REAL_BOARDS=1",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1",
            "ROTATING_SHAFT_REAL_ACCEPTANCE_BLOCKED=0",
        ],
    )
    product_loop_dryrun_summary = latest_containing(
        "reports/product_loop_acceptance_safe_*.summary.txt",
        [
            "PRODUCT_LOOP_DRY_RUN=1",
            "TOPOLOGY=two_ax7010",
            "CONTINUOUS_RUNTIME_CAP_APPLIED=1",
            "DURATION_SECONDS_EFFECTIVE=600",
            "NO_TX_DATA_TO_REAL_BOARDS=1",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1",
            "PRODUCT_LOOP_REAL_ACCEPTANCE_BLOCKED=0",
        ],
    )
    eightlane_hw_dryrun_summary = latest_containing(
        "reports/8lane_hardware_acceptance_safe_*.summary.txt",
        [
            "EIGHT_LANE_HARDWARE_DRY_RUN=1",
            "PROFILE=reduced_8lane_frag16_external",
            "LANE_COUNT_REQUESTED=8",
            "CONTINUOUS_RUNTIME_CAP_APPLIED=1",
            "DURATION_SECONDS_EFFECTIVE=600",
            "CANDIDATE_A_LANE_COUNT=8",
            "CANDIDATE_B_LANE_COUNT=8",
            "REDUCED_8LANE_FRAG16_BITSTREAM_READY_FOR_REVIEW=1",
            "REDUCED_8LANE_FRAG16_RAW_HALF_MBPS=32.0",
            "REDUCED_8LANE_FRAG16_RAW_FDX_PER_DIR_MBPS=16.0",
            "REDUCED_8LANE_FRAG16_BITSTREAM_SHA256=F3661A68DB0F36FCAC96DE983538EA31B5AA2B50338B44A81DAB3E45999AC778",
            "CANDIDATE_PROJECT_RESOURCE_BLOCKED=1",
            "EIGHT_LANE_HARDWARE_DRY_RUN_BLOCKED_REASON_PREVIEW=ethernet_link_not_up",
            "NO_TX_DATA_TO_REAL_BOARDS=1",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1",
        ],
    )
    two_ax7010_blocked_summary = latest_containing(
        "reports/two_ax7010_end_to_end_acceptance_safe_*.summary.txt",
        [
            "TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=1",
            "TWO_AX7010_BLOCKED_REASON=ethernet_link_not_up",
            "NO_TX_DATA_TO_REAL_BOARDS=1",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1",
        ],
    )
    two_ax7010_real_summary = latest_containing(
        "reports/two_ax7010_end_to_end_acceptance_safe_*.summary.txt",
        [
            "TWO_AX7010_REAL_ACCEPTANCE_PASS=1",
            "TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=0",
            "TWO_AX7010_SHUTDOWN_AFTER_RUN_PASS=1",
            "NO_TX_DATA_TO_REAL_BOARDS=0",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=0",
        ],
    )
    rotating_shaft_real_summary = latest_containing(
        "reports/rotating_shaft_acceptance_safe_*.summary.txt",
        [
            "ROTATING_SHAFT_REAL_ACCEPTANCE_PASS=1",
            "ROTATING_SHAFT_REAL_ACCEPTANCE_BLOCKED=0",
            "FIXTURE_LOG_DIAMETER_OK=1",
            "FIXTURE_LOG_RPM_OK=1",
            "NO_TX_DATA_TO_REAL_BOARDS=0",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=0",
        ],
    )
    eightlane_hw_real_summary = latest_containing(
        "reports/8lane_hardware_acceptance_safe_*.summary.txt",
        [
            "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_PASS=1",
            "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_BLOCKED=0",
            "EIGHT_LANE_HARDWARE_SHUTDOWN_BEFORE_RUN_PASS=1",
            "EIGHT_LANE_HARDWARE_SHUTDOWN_AFTER_RUN_PASS=1",
            "NO_TX_DATA_TO_REAL_BOARDS=0",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=0",
        ],
    )
    g1_config = REPORTS / "G1_test_config.json"
    g1_artifacts = REPORTS / "G1_artifacts_hashes.txt"
    host_acceptance = ROOT / "software" / "host_client" / "run_acceptance.ps1"
    host_client = ROOT / "software" / "host_client" / "rf_comm_client.py"
    host_client_tests = ROOT / "software" / "host_client" / "test_rf_comm_client.py"
    host_mock_server = ROOT / "software" / "host_client" / "mock_rfcm_server.py"

    g1_report_text = read_text(g1_report)
    post_status_text = read_text(post_status)
    post_summary_text = read_text(post_summary)
    rate_options_text = read_text(rate_options_md)
    rate_boundary_text = read_text(rate_boundary_md)
    payload_gap_closure_text = read_text(payload_gap_closure_md)
    payload_gap_closure_json_text = read_text(payload_gap_closure_json)
    payload_gap_closure_csv_text = read_text(payload_gap_closure_csv)
    target_consistency_text = read_text(target_consistency_md)
    status_consistency_text = read_text(status_consistency_md)
    status_consistency_csv_text = read_text(status_consistency_csv)
    external_preconditions_text = read_text(external_preconditions_md)
    external_preconditions_csv_text = read_text(external_preconditions_csv)
    real_acceptance_runbook_text = read_text(real_acceptance_runbook_md)
    real_acceptance_runbook_csv_text = read_text(real_acceptance_runbook_csv)
    real_acceptance_sequence_text = read_text(real_acceptance_sequence_md)
    real_acceptance_sequence_summary_text = read_text(real_acceptance_sequence_summary)
    real_acceptance_sequence_json_text = read_text(real_acceptance_sequence_json)
    real_acceptance_sequence_csv_text = read_text(real_acceptance_sequence_csv)
    protocol_contract_text = read_text(protocol_contract_md)
    protocol_contract_csv_text = read_text(protocol_contract_csv)
    ps_lwip_bridge_static_text = read_text(ps_lwip_bridge_static_md)
    ps_lwip_bridge_static_json_text = read_text(ps_lwip_bridge_static_json)
    ps_lwip_bridge_static_csv_text = read_text(ps_lwip_bridge_static_csv)
    ps_pc_offline_summary_text = read_text(ps_pc_offline_summary)
    ps_pc_offline_unittest_text = read_text(ps_pc_offline_unittest)
    ps_pc_offline_acceptance_text = read_text(ps_pc_offline_acceptance)
    two_ax7010_model_text = read_text(two_ax7010_model_md)
    two_ax7010_model_json_text = read_text(two_ax7010_model_json)
    two_ax7010_model_csv_text = read_text(two_ax7010_model_csv)
    host_status_snapshot_text = read_text(host_status_snapshot_md)
    host_status_snapshot_json_text = read_text(host_status_snapshot_json)
    host_status_snapshot_csv_text = read_text(host_status_snapshot_csv)
    no_ethernet_network_boundary_text = read_text(no_ethernet_network_boundary_md)
    no_ethernet_network_boundary_json_text = read_text(no_ethernet_network_boundary_json)
    no_ethernet_network_boundary_csv_text = read_text(no_ethernet_network_boundary_csv)
    target_matrix_text = read_text(target_matrix_md)
    target_matrix_csv_text = read_text(target_matrix_csv)
    full_system_twin_text = read_text(full_system_twin_md)
    full_system_twin_json_text = read_text(full_system_twin_json)
    full_system_twin_csv_text = read_text(full_system_twin_csv)
    full_system_envelope_text = read_text(full_system_envelope_md)
    full_system_envelope_json_text = read_text(full_system_envelope_json)
    full_system_envelope_csv_text = read_text(full_system_envelope_csv)
    rotating_autoroute_offline_text = read_text(rotating_autoroute_offline_md)
    rotating_autoroute_offline_json_text = read_text(rotating_autoroute_offline_json)
    rotating_autoroute_offline_csv_text = read_text(rotating_autoroute_offline_csv)
    topology_capacity_text = read_text(topology_capacity_md)
    topology_capacity_csv_text = read_text(topology_capacity_csv)
    remaining_hw_plan_text = read_text(remaining_hw_plan_md)
    remaining_hw_plan_csv_text = read_text(remaining_hw_plan_csv)
    remaining_acceptance_readiness_text = read_text(remaining_acceptance_readiness_md)
    remaining_acceptance_readiness_json_text = read_text(remaining_acceptance_readiness_json)
    remaining_acceptance_readiness_csv_text = read_text(remaining_acceptance_readiness_csv)
    rotating_fixture_validation_text = read_text(rotating_fixture_validation_md)
    rotating_fixture_validation_csv_text = read_text(rotating_fixture_validation_csv)
    rotating_fixture_template_text = read_text(rotating_fixture_template)
    real_acceptance_validation_text = read_text(real_acceptance_validation_md)
    real_acceptance_validation_csv_text = read_text(real_acceptance_validation_csv)
    real_acceptance_validator_selftest_text = read_text(real_acceptance_validator_selftest_md)
    real_acceptance_validator_selftest_json_text = read_text(real_acceptance_validator_selftest_json)
    real_acceptance_validator_selftest_csv_text = read_text(real_acceptance_validator_selftest_csv)
    real_acceptance_promotion_gate_text = read_text(real_acceptance_promotion_gate_md)
    real_acceptance_promotion_gate_json_text = read_text(real_acceptance_promotion_gate_json)
    real_acceptance_promotion_gate_csv_text = read_text(real_acceptance_promotion_gate_csv)
    duration_cap_compliance_text = read_text(duration_cap_compliance_md)
    duration_cap_compliance_json_text = read_text(duration_cap_compliance_json)
    duration_cap_compliance_csv_text = read_text(duration_cap_compliance_csv)
    safe_wrapper_guard_text = read_text(safe_wrapper_guard_md)
    safe_wrapper_guard_json_text = read_text(safe_wrapper_guard_json)
    safe_wrapper_guard_csv_text = read_text(safe_wrapper_guard_csv)
    drc_release_gate_text = read_text(drc_release_gate_md)
    drc_release_gate_json_text = read_text(drc_release_gate_json)
    drc_release_gate_csv_text = read_text(drc_release_gate_csv)
    real_acceptance_template_manifest_text = read_text(real_acceptance_template_manifest)
    throughput_summary_template_text = "\n".join(
        read_text(path)
        for path in [
            two_ax7010_summary_template,
            product_loop_summary_template,
            rotating_shaft_summary_template,
            eight_lane_summary_template,
        ]
    )
    throughput_criteria_template_text = "\n".join(
        read_text(path)
        for path in [
            two_ax7010_criteria_template,
            product_loop_criteria_template,
            rotating_shaft_criteria_template,
            eight_lane_criteria_template,
        ]
    )
    eightlane_readiness_text = read_text(eightlane_readiness_md)
    eightlane_readiness_csv_text = read_text(eightlane_readiness_csv)
    eightlane_shutdown_build_text = read_text(eightlane_shutdown_build_md)
    eightlane_shutdown_build_csv_text = read_text(eightlane_shutdown_build_csv)
    eightlane_candidate_project_text = read_text(eightlane_candidate_project_md)
    eightlane_candidate_project_csv_text = read_text(eightlane_candidate_project_csv)
    eightlane_external_project_text = read_text(eightlane_external_project_md)
    eightlane_external_project_csv_text = read_text(eightlane_external_project_csv)
    external_lane_scan_text = read_text(external_lane_scan_md)
    external_lane_scan_csv_text = read_text(external_lane_scan_csv)
    external_option_scan_text = read_text(external_option_scan_md)
    external_option_scan_csv_text = read_text(external_option_scan_csv)
    external_reduced_lane_scan_text = read_text(external_reduced_lane_scan_md)
    external_reduced_lane_scan_csv_text = read_text(external_reduced_lane_scan_csv)
    external_reduced_5to8_text = read_text(external_reduced_5to8_md)
    external_reduced_5to8_csv_text = read_text(external_reduced_5to8_csv)
    external_reduced_5lane_frag32_text = read_text(external_reduced_5lane_frag32_md)
    external_reduced_5lane_frag32_csv_text = read_text(external_reduced_5lane_frag32_csv)
    external_reduced_5lane_frag32_route_text = read_text(external_reduced_5lane_frag32_route_md)
    external_reduced_5lane_frag32_route_csv_text = read_text(external_reduced_5lane_frag32_route_csv)
    external_reduced_5lane_frag32_bitstream_text = read_text(external_reduced_5lane_frag32_bitstream_md)
    external_reduced_5lane_frag32_bitstream_csv_text = read_text(external_reduced_5lane_frag32_bitstream_csv)
    external_reduced_8lane_frag16_bitstream_text = read_text(external_reduced_8lane_frag16_bitstream_md)
    external_reduced_8lane_frag16_bitstream_csv_text = read_text(external_reduced_8lane_frag16_bitstream_csv)
    external_reduced_route_text = read_text(external_reduced_route_md)
    external_reduced_route_csv_text = read_text(external_reduced_route_csv)
    external_reduced_4lane_route_text = read_text(external_reduced_4lane_route_md)
    external_reduced_4lane_route_csv_text = read_text(external_reduced_4lane_route_csv)
    external_reduced_4lane_bitstream_text = read_text(external_reduced_4lane_bitstream_md)
    external_reduced_4lane_bitstream_csv_text = read_text(external_reduced_4lane_bitstream_csv)
    external_reduced_4lane_bringup_text = read_text(external_reduced_4lane_bringup_md)
    external_reduced_4lane_bringup_csv_text = read_text(external_reduced_4lane_bringup_csv)
    board_tcp_text = read_text(board_tcp_summary)
    no_ethernet_network_text = read_text(no_ethernet_network_summary)
    no_ethernet_network_csv_text = read_text(no_ethernet_network_csv)
    boot_audit_text = read_text(boot_audit_md)
    two_ax7010_safe_wrapper_text = read_text(two_ax7010_safe_wrapper)
    rotating_shaft_safe_wrapper_text = read_text(rotating_shaft_safe_wrapper)
    rotating_fixture_validator_text = read_text(rotating_fixture_validator)
    real_acceptance_validator_text = read_text(real_acceptance_validator)
    rotating_shaft_dryrun_text = read_text(rotating_shaft_dryrun_summary)
    product_loop_safe_wrapper_text = read_text(product_loop_safe_wrapper)
    product_loop_dryrun_text = read_text(product_loop_dryrun_summary)
    eightlane_hw_safe_wrapper_text = read_text(eightlane_hw_safe_wrapper)
    eightlane_hw_dryrun_text = read_text(eightlane_hw_dryrun_summary)
    two_ax7010_offline_text = read_text(two_ax7010_offline_summary)
    two_ax7010_dryrun_text = read_text(two_ax7010_dryrun_summary)
    two_ax7010_blocked_text = read_text(two_ax7010_blocked_summary)
    g1_config_text = read_text(g1_config)
    artifact_text = read_text(g1_artifacts)
    host_acceptance_text = read_text(host_acceptance)
    host_client_text = read_text(host_client)
    host_client_tests_text = read_text(host_client_tests)
    host_mock_server_text = read_text(host_mock_server)
    rows = load_post_gate_rows(post_csv)

    phy_rate_pass = case_pass(rows, "phy_rate") and re.search(
        r"raw_mbps=4\.000000 .*half_duplex_raw_mbps=32\.000000 .*full_duplex_per_dir_raw_mbps=16\.000000",
        post_summary_text,
    )
    payload_budget_pass = case_pass(rows, "payload_budget")
    half_payload_upper = extract_float(r"half_payload_upper_mbps_no_ack=([0-9.]+)", post_summary_text)
    fdx_payload_upper = extract_float(r"fdx_payload_upper_mbps_per_dir_no_ack=([0-9.]+)", post_summary_text)
    effective_payload_missing = (
        payload_budget_pass
        and half_payload_upper is not None
        and fdx_payload_upper is not None
        and (half_payload_upper < 32.0 or fdx_payload_upper < 16.0)
    )
    best_half_packet_ack = extract_float(r"half-duplex 8-lane payload `([0-9.]+) Mbit/s`", rate_options_text)
    best_fdx_packet_ack = extract_float(r"full-duplex 4\+4 payload `([0-9.]+) Mbit/s`", rate_options_text)
    packet_ack_meets_16_8 = extract_int(
        r"Packet-ACK options meeting the earlier 16/8 Mbit/s effective-payload threshold: `([0-9]+)`",
        rate_options_text,
    )
    packet_ack_meets_32_16 = extract_int(
        r"Packet-ACK options meeting 32/16 Mbit/s effective-payload threshold: `([0-9]+)`",
        rate_options_text,
    )
    rate_options_pass = (
        rate_options_md is not None
        and rate_options_md.exists()
        and rate_options_csv is not None
        and rate_options_csv.exists()
        and best_half_packet_ack is not None
        and best_fdx_packet_ack is not None
        and packet_ack_meets_16_8 is not None
        and packet_ack_meets_32_16 is not None
    )
    target_consistency_gate_pass = case_pass(rows, "target_consistency")
    target_consistency_boundary = (
        target_consistency_md is not None
        and target_consistency_md.exists()
        and target_consistency_json is not None
        and target_consistency_json.exists()
        and target_consistency_gate_pass
        and "RF_COMM_TARGET_CONSISTENCY_CHECK overall=BOUNDARY_RAW_ONLY" in target_consistency_text
        and "raw_half_8lane_mbps | 32.000000" in target_consistency_text
        and "raw_fdx_4lane_per_dir_mbps | 16.000000" in target_consistency_text
    )
    status_consistency_ok = (
        status_consistency_md.exists()
        and status_consistency_json.exists()
        and status_consistency_csv.exists()
        and "RF_COMM_FULL_TARGET_STATUS_CONSISTENCY overall=PASS" in status_consistency_text
        and "NO_HARDWARE_PROGRAMMING=1" in status_consistency_text
        and "NO_UART_WRITE=1" in status_consistency_text
        and "NO_TFDU_DRIVE=1" in status_consistency_text
        and "status_report_references_post_g1_target_sim_gate" in status_consistency_csv_text
        and "matrix_meta_uses_latest_post_gate,PASS" in status_consistency_csv_text
        and "audit_meta_uses_latest_no_ethernet_gate,PASS" in status_consistency_csv_text
        and "active_project_restored_2lane_port1,PASS" in status_consistency_csv_text
    )
    external_preconditions_ok = (
        external_preconditions_md.exists()
        and external_preconditions_json.exists()
        and external_preconditions_csv.exists()
        and "RF_COMM_EXTERNAL_PRECONDITIONS overall=BLOCKED_NO_ETHERNET" in external_preconditions_text
        and "NO_HARDWARE_PROGRAMMING=1" in external_preconditions_text
        and "NO_UART_WRITE=1" in external_preconditions_text
        and "NO_TFDU_DRIVE=1" in external_preconditions_text
        and "ethernet_link,BLOCKED" in external_preconditions_csv_text
        and "tcp_quick_probe_single_board,BLOCKED" in external_preconditions_csv_text
        and "tcp_quick_probe_two_ax7010,BLOCKED" in external_preconditions_csv_text
    )
    real_acceptance_runbook_ok = (
        real_acceptance_runbook_md.exists()
        and real_acceptance_runbook_json.exists()
        and real_acceptance_runbook_csv.exists()
        and "RF_COMM_REAL_ACCEPTANCE_RUNBOOK overall=WAITING_FOR_ETHERNET stages=5" in real_acceptance_runbook_text
        and "NO_HARDWARE_PROGRAMMING=1" in real_acceptance_runbook_text
        and "NO_UART_WRITE=1" in real_acceptance_runbook_text
        and "NO_TFDU_DRIVE=1" in real_acceptance_runbook_text
        and all(item_id in real_acceptance_runbook_csv_text for item_id in ["N03", "N04", "A01", "S05", "A02"])
        and real_acceptance_runbook_csv_text.count("BLOCKED_NO_ETHERNET") >= 5
    )
    real_acceptance_sequence_ok = (
        real_acceptance_sequence_summary.exists()
        and real_acceptance_sequence_md.exists()
        and real_acceptance_sequence_json.exists()
        and real_acceptance_sequence_csv.exists()
        and "RF_COMM_REAL_ACCEPTANCE_SEQUENCE overall=BLOCKED_NO_ETHERNET stages=5" in real_acceptance_sequence_text
        and "RF_COMM_REAL_ACCEPTANCE_SEQUENCE overall=BLOCKED_NO_ETHERNET stages=5" in real_acceptance_sequence_summary_text
        and "PREFLIGHT_OVERALL=BLOCKED_NO_ETHERNET" in real_acceptance_sequence_summary_text
        and "PREFLIGHT_BLOCKERS=ethernet_link,tcp_quick_probe_single_board,tcp_quick_probe_two_ax7010" in real_acceptance_sequence_summary_text
        and "REMAINING_READINESS_OVERALL=BLOCKED_EXTERNAL_PRECONDITIONS" in real_acceptance_sequence_summary_text
        and "REMAINING_READINESS_ITEMS=5" in real_acceptance_sequence_summary_text
        and "- Remaining readiness gate: `BLOCKED_EXTERNAL_PRECONDITIONS`" in real_acceptance_sequence_text
        and '"remaining_readiness_overall":  "BLOCKED_EXTERNAL_PRECONDITIONS"' in real_acceptance_sequence_json_text
        and '"N03=ethernet_link_up;single_board_tcp_reachable"' in real_acceptance_sequence_json_text
        and "EXECUTED_WRAPPERS=0" in real_acceptance_sequence_summary_text
        and "NO_HARDWARE_PROGRAMMING=1" in real_acceptance_sequence_text
        and "NO_UART_WRITE=1" in real_acceptance_sequence_text
        and "NO_TFDU_DRIVE=1" in real_acceptance_sequence_text
        and all(item_id in real_acceptance_sequence_csv_text for item_id in ["N03", "N04", "A01", "S05", "A02"])
        and real_acceptance_sequence_csv_text.count('"0","1"') >= 5
        and real_acceptance_sequence_csv_text.count("preflight_blockers=ethernet_link;tcp_quick_probe_single_board;tcp_quick_probe_two_ax7010") >= 5
    )
    protocol_contract_ok = (
        protocol_contract_md.exists()
        and protocol_contract_json.exists()
        and protocol_contract_csv.exists()
        and "RF_COMM_PROTOCOL_CONTRACT overall=PASS checks=25 status_fields=16 frame_types=9 config_bits=4" in protocol_contract_text
        and "NO_HARDWARE_PROGRAMMING=1" in protocol_contract_text
        and "NO_UART_WRITE=1" in protocol_contract_text
        and "NO_TFDU_DRIVE=1" in protocol_contract_text
        and "status_payload_layout,PASS" in protocol_contract_csv_text
        and "final_half_duplex_8lane_mask,PASS" in protocol_contract_csv_text
        and "final_full_duplex_4plus4_masks,PASS" in protocol_contract_csv_text
    )
    ps_lwip_bridge_static_ok = (
        ps_lwip_bridge_static_md.exists()
        and ps_lwip_bridge_static_json.exists()
        and ps_lwip_bridge_static_csv.exists()
        and "RF_COMM_PS_LWIP_BRIDGE_STATIC overall=PASS checks=64 failures=0" in ps_lwip_bridge_static_text
        and "DHCP_SOURCE_READY=1" in ps_lwip_bridge_static_text
        and "STATIC_FALLBACK_SOURCE_READY=1" in ps_lwip_bridge_static_text
        and "TCP_BRIDGE_SOURCE_READY=1" in ps_lwip_bridge_static_text
        and "RFCM_PROTOCOL_SOURCE_READY=1" in ps_lwip_bridge_static_text
        and "NO_HARDWARE_PROGRAMMING=1" in ps_lwip_bridge_static_text
        and "NO_UART_WRITE=1" in ps_lwip_bridge_static_text
        and "NO_TFDU_DRIVE=1" in ps_lwip_bridge_static_text
        and "NO_REAL_BOARD_TCP_DHCP=1" in ps_lwip_bridge_static_text
        and f"CONSTRAINT_SHA256={EXPECTED_CONSTRAINT_SHA256}" in ps_lwip_bridge_static_text
        and '"overall": "PASS"' in ps_lwip_bridge_static_json_text
        and '"checks_passed": 64' in ps_lwip_bridge_static_json_text
        and "dhcp_start,dhcp_static_network,PASS" in ps_lwip_bridge_static_csv_text
        and "tcp_new_bind_listen,tcp_connection,PASS" in ps_lwip_bridge_static_csv_text
        and "frame_tx_data_matches_pc,pc_ps_protocol_contract,PASS" in ps_lwip_bridge_static_csv_text
    )
    ps_pc_protocol_robustness_ok = (
        ps_pc_offline_summary is not None
        and ps_pc_offline_summary.exists()
        and ps_pc_offline_unittest is not None
        and ps_pc_offline_unittest.exists()
        and ps_pc_offline_acceptance is not None
        and ps_pc_offline_acceptance.exists()
        and "PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1" in ps_pc_offline_summary_text
        and "PS_BRIDGE_STATIC_CHECKS_PASS checks=64 dhcp=1 tcp=1 protocol=1 reconnect=1" in ps_pc_offline_summary_text
        and "STEP_STDERR name=host_client_unittest Ran 21 tests" in ps_pc_offline_summary_text
        and "STEP_STDERR name=host_client_unittest OK" in ps_pc_offline_summary_text
        and "STEP_STDOUT name=host_offline_mock_acceptance log_acceptance PASS" in ps_pc_offline_summary_text
        and "sent_packets=64 sent_bytes=16384" in ps_pc_offline_summary_text
        and "reconnect cycle 4/4" in ps_pc_offline_summary_text
        and "class ProtocolError" in host_client_text
        and "bad magic" in host_client_text
        and "unsupported version" in host_client_text
        and "payload length" in host_client_text
        and "malformed_status_payload_len" in host_client_text
        and "test_recv_frame_reports_protocol_desync_details" in host_client_tests_text
        and "test_status_parser_reports_malformed_lengths" in host_client_tests_text
        and "rf.MAX_FRAME_PAYLOAD" in host_mock_server_text
        and 'bridge_send_text(RF_FRAME_ERROR, 0u, "bad_magic")' in read_text(ROOT / "software" / "ps_lwip_bridge" / "src" / "tcp_bridge.c")
        and 'bridge_send_text(RF_FRAME_ERROR, seq, "unsupported_version")' in read_text(ROOT / "software" / "ps_lwip_bridge" / "src" / "tcp_bridge.c")
    )
    target_matrix_ok = (
        target_matrix_md.exists()
        and target_matrix_json.exists()
        and target_matrix_csv.exists()
        and "RF_COMM_TARGET_ACCEPTANCE_MATRIX overall=INCOMPLETE_REQUIREMENT_MATRIX" in target_matrix_text
        and "Requirements tracked: `36`" in target_matrix_text
        and "DEFERRED_NO_ETHERNET" in target_matrix_text
        and "MISSING_HARDWARE" in target_matrix_text
        and "PARTIAL_G1_ONLY" in target_matrix_text
        and "P02" in target_matrix_csv_text
        and "PASS_RAW_OFFLINE_BITSTREAM" in target_matrix_csv_text
        and "external_reduced_8lane_frag16_bitstream_current.md" in target_matrix_csv_text
        and "F3661A68DB0F36FCAC96DE983538EA31B5AA2B50338B44A81DAB3E45999AC778" in target_matrix_csv_text
        and "not effective payload or hardware acceptance" in target_matrix_csv_text
        and "P03" in target_matrix_csv_text
        and "PASS_RAW_ONLY_BOUNDARY_DOCUMENTED" in target_matrix_csv_text
        and "does not claim 32/16 as effective payload" in target_matrix_csv_text
        and "N02" in target_matrix_csv_text
        and "ps_lwip_bridge_static_current.md" in target_matrix_csv_text
        and "Structured PS lwIP static report confirms DHCP start/wait/timeout" in target_matrix_csv_text
        and "N03" in target_matrix_csv_text
        and "N04" in target_matrix_csv_text
        and "S05" in target_matrix_csv_text
        and "A01" in target_matrix_csv_text
        and "A02" in target_matrix_csv_text
    )
    topology_capacity_ok = (
        topology_capacity_md.exists()
        and topology_capacity_json.exists()
        and topology_capacity_csv.exists()
        and "RF_COMM_TOPOLOGY_CAPACITY_PLAN overall=FINAL_RAW_TARGET_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED" in topology_capacity_text
        and "best_buildable_profile=reduced_8lane_frag16_bitstream_candidate" in topology_capacity_text
        and "target_raw_half_mbps=32.000" in topology_capacity_text
        and "target_raw_fdx_per_dir_mbps=16.000" in topology_capacity_text
        and "full_8lane_stream_bidir_candidate" in topology_capacity_csv_text
        and "a_only_external_8lane_candidate" in topology_capacity_csv_text
        and "RESOURCE_BLOCKED_ON_XC7Z010" in topology_capacity_csv_text
        and "reduced_4lane_external_candidate" in topology_capacity_csv_text
        and "ROUTE_TIMING_BITSTREAM_READY_REVIEW_REQUIRED" in topology_capacity_csv_text
        and "5-lane reduced extension fails placement" in topology_capacity_text
        and "LUT=17801/17600" in topology_capacity_text
        and "slices=3869/3845" in topology_capacity_text
        and "reduced_5lane_frag32_route_candidate" in topology_capacity_csv_text
        and "reduced_5lane_frag32_bitstream_candidate" in topology_capacity_csv_text
        and "reduced_8lane_frag16_bitstream_candidate" in topology_capacity_csv_text
        and "ROUTE_TIMING_PASS_SMALL_PACKET_PROFILE" in topology_capacity_csv_text
        and "ROUTE_TIMING_BITSTREAM_READY_REVIEW_REQUIRED" in topology_capacity_csv_text
        and "5-lane fragment=32 profile now reaches route_design, meets timing, and produces a candidate bitstream" in topology_capacity_text
        and "meets the 32/16 Mbit/s raw PHY target" in topology_capacity_text
        and "still not effective-payload, TCP/DHCP, two-AX7010, TFDU hardware, or rotating-shaft acceptance" in topology_capacity_text
        and "rtl_8lane_simulation_model" in topology_capacity_csv_text
    )
    remaining_hw_plan_ok = (
        remaining_hw_plan_md.exists()
        and remaining_hw_plan_json.exists()
        and remaining_hw_plan_csv.exists()
        and "RF_COMM_REMAINING_HARDWARE_ACCEPTANCE_PLAN overall=WAITING_FOR_EXTERNAL_HARDWARE items=5" in remaining_hw_plan_text
        and "Development board Ethernet is not connected and this cannot be changed right now." in remaining_hw_plan_text
        and "Continuous physical run cap: `600 seconds`" in remaining_hw_plan_text
        and "Required after every physical run that drives TFDU/TX" in remaining_hw_plan_text
        and "candidate shutdown bitstream has been built offline" in remaining_hw_plan_text
        and "implementation is blocked on XC7Z010 LUT capacity (21125 required vs 17600 available)" in remaining_hw_plan_text
        and "A-only external 8-lane profile" in remaining_hw_plan_text
        and "Slice LUTs: 45050/17600" in remaining_hw_plan_text
        and "only 1 lane reaches place_design" in remaining_hw_plan_text
        and "lane 2 and above resource-blocked" in remaining_hw_plan_text
        and "reduced 2-lane external option" in remaining_hw_plan_text
        and "fragment=64" in remaining_hw_plan_text
        and "TX/RX FIFO=128/128" in remaining_hw_plan_text
        and "reduced 1..4-lane external scan" in remaining_hw_plan_text
        and "reaches place_design up to 4 lanes" in remaining_hw_plan_text
        and "reaches route_design and meets timing" in remaining_hw_plan_text
        and "WNS=1.58 ns" in remaining_hw_plan_text
        and "reduced 4-lane external option now also reaches route_design and meets timing" in remaining_hw_plan_text
        and "WNS=1.317 ns" in remaining_hw_plan_text
        and "offline candidate bitstream" in remaining_hw_plan_text
        and "BDDE1CE8416E05EBAD8BF24FF96FEC04419CC3C7C35841CBB3ED825425714779" in remaining_hw_plan_text
        and "reduced 5-lane fragment=32 external option reaches route_design and meets timing" in remaining_hw_plan_text
        and "WNS=1.571 ns" in remaining_hw_plan_text
        and "PASS_OFFLINE_5LANE_FRAG32_BITSTREAM_READY_REVIEW_REQUIRED" in remaining_hw_plan_text
        and "64213BD459D5CF8E6A487DC601D8942F1D938858AFAE5039CBB46FF3A39A903E" in remaining_hw_plan_text
        and "reduced 4-lane bring-up/ILA plan is ready for manual review" in remaining_hw_plan_text
        and "reduced 5..8-lane extension scan confirms the first reduced-profile resource boundary at lane 5" in remaining_hw_plan_text
        and "LUT=17801/17600" in remaining_hw_plan_text
        and "slices=3869/3845" in remaining_hw_plan_text
        and "fragment=32 5-lane result shows packet/cache sizing is the current reduction lever" in remaining_hw_plan_text
        and "Fixture CSV should pass tools/validate_rotating_fixture_log.py before real acceptance is claimed." in remaining_hw_plan_text
        and "reports/rotating_fixture_log_template.csv" in remaining_hw_plan_text
        and "reports/rotating_fixture_log_validation_current.*" in remaining_hw_plan_text
        and "reports/real_acceptance_evidence_validation_current.*" in remaining_hw_plan_text
        and "reports/real_acceptance_template/ps_pc_tcp_dhcp_summary_template.txt" in remaining_hw_plan_text
        and "reports/real_acceptance_template/two_ax7010_summary_template.txt" in remaining_hw_plan_text
        and "reports/real_acceptance_template/two_ax7010_criteria_template.csv" in remaining_hw_plan_text
        and "reports/real_acceptance_template/rotating_shaft_summary_template.txt" in remaining_hw_plan_text
        and "reports/real_acceptance_template/product_loop_summary_template.txt" in remaining_hw_plan_text
        and "reports/real_acceptance_template/eight_lane_summary_template.txt" in remaining_hw_plan_text
        and "fixture-log and real-acceptance evidence validators/templates exist for 20 cm / 600 rpm / 600 s segment evidence" in remaining_hw_plan_text
        and "The rotating fixture log template is readiness evidence only and is not real rotating-shaft acceptance." in remaining_hw_plan_text
        and "Use tools/validate_real_acceptance_evidence.py --mode rotating_shaft" in remaining_hw_plan_text
        and "Use tools/validate_real_acceptance_evidence.py --mode product_loop" in remaining_hw_plan_text
        and "Use tools/validate_real_acceptance_evidence.py --mode eight_lane" in remaining_hw_plan_text
        and "run_rotating_shaft_acceptance_safe.ps1" in remaining_hw_plan_text
        and "ROTATING_SHAFT_REAL_ACCEPTANCE_PASS=1" in remaining_hw_plan_text
        and "Dedicated safe wrapper exists and dry-run evidence proves the 600 s cap/no-hardware gate" in remaining_hw_plan_text
        and "run_product_loop_acceptance_safe.ps1" in remaining_hw_plan_text
        and "PRODUCT_LOOP_REAL_ACCEPTANCE_PASS=1" in remaining_hw_plan_text
        and "Dedicated safe wrapper exists and dry-run evidence proves the 600 s cap/no-hardware gate" in remaining_hw_plan_text
        and "run_8lane_hardware_acceptance_safe.ps1" in remaining_hw_plan_text
        and "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_PASS=1" in remaining_hw_plan_text
        and "A dedicated 8-lane hardware safe wrapper exists and dry-run evidence proves the 600 s cap/no-hardware gate" in remaining_hw_plan_text
        and "N03" in remaining_hw_plan_csv_text
        and "N04" in remaining_hw_plan_csv_text
        and "S05" in remaining_hw_plan_csv_text
        and "A01" in remaining_hw_plan_csv_text
        and "A02" in remaining_hw_plan_csv_text
    )
    remaining_acceptance_readiness_ok = (
        remaining_acceptance_readiness_md.exists()
        and remaining_acceptance_readiness_json.exists()
        and remaining_acceptance_readiness_csv.exists()
        and "RF_COMM_REMAINING_ACCEPTANCE_READINESS overall=BLOCKED_EXTERNAL_PRECONDITIONS items=5" in remaining_acceptance_readiness_text
        and "NO_HARDWARE_PROGRAMMING=1" in remaining_acceptance_readiness_text
        and "NO_UART_WRITE=1" in remaining_acceptance_readiness_text
        and "NO_TFDU_DRIVE=1" in remaining_acceptance_readiness_text
        and "CURRENT_BOARD_ETHERNET_CABLE_AVAILABLE=0" in remaining_acceptance_readiness_text
        and "CURRENT_BOARD_ETHERNET_CONDITION_CHANGEABLE_NOW=0" in remaining_acceptance_readiness_text
        and "CURRENT_NO_ETHERNET_CABLE_UNCHANGEABLE_NOW=1" in remaining_acceptance_readiness_text
        and "REAL_ACCEPTANCE_EXECUTED=0" in remaining_acceptance_readiness_text
        and '"overall": "BLOCKED_EXTERNAL_PRECONDITIONS"' in remaining_acceptance_readiness_json_text
        and '"current_board_ethernet_cable_available": false' in remaining_acceptance_readiness_json_text
        and '"current_board_ethernet_condition_changeable_now": false' in remaining_acceptance_readiness_json_text
        and '"no_hardware_programming": true' in remaining_acceptance_readiness_json_text
        and '"no_uart_write": true' in remaining_acceptance_readiness_json_text
        and '"no_tfdu_drive": true' in remaining_acceptance_readiness_json_text
        and "current_board_ethernet_cable_unavailable" in remaining_acceptance_readiness_csv_text
        and "current_board_ethernet_condition_not_changeable_now" in remaining_acceptance_readiness_csv_text
        and "N03,BLOCKED_EXTERNAL_PRECONDITIONS,0,ethernet_link_up;single_board_tcp_reachable" in remaining_acceptance_readiness_csv_text
        and "N04,BLOCKED_EXTERNAL_PRECONDITIONS,0,ethernet_link_up;two_ax7010_tcp_reachable" in remaining_acceptance_readiness_csv_text
        and "S05,BLOCKED_EXTERNAL_PRECONDITIONS,0,ethernet_link_up;two_ax7010_tcp_reachable;real_20cm_600rpm_fixture_log_missing" in remaining_acceptance_readiness_csv_text
        and "A01,BLOCKED_EXTERNAL_PRECONDITIONS,0,ethernet_link_up;two_ax7010_tcp_reachable" in remaining_acceptance_readiness_csv_text
        and "A02,BLOCKED_EXTERNAL_PRECONDITIONS,0,ethernet_link_up;two_ax7010_tcp_reachable;real_8lane_tfdu_wiring_validation_missing" in remaining_acceptance_readiness_csv_text
        and "start_when" in remaining_acceptance_readiness_csv_text
        and "unlock_action" in remaining_acceptance_readiness_csv_text
        and "safety_requirement" in remaining_acceptance_readiness_csv_text
        and "Connect the board Ethernet path, boot the PS lwIP bridge" in remaining_acceptance_readiness_csv_text
        and "two_complete_ax7010_systems_ready;optical_lanes_ready" in remaining_acceptance_readiness_csv_text
        and "real_20cm_600rpm_fixture_log_valid;rotating_optical_path_ready" in remaining_acceptance_readiness_csv_text
        and "product_loop_topology_selected;real_ir_path_ready" in remaining_acceptance_readiness_csv_text
        and "pinmap_reviewed;shutdown_bitstream_reviewed;real_8lane_tfdu_wiring_validated" in remaining_acceptance_readiness_csv_text
        and '"unlock_action": "Review the 8-lane pinmap and shutdown bitstream' in remaining_acceptance_readiness_json_text
        and "-ProgramShutdownBeforeRun" in remaining_acceptance_readiness_json_text
    )
    eightlane_readiness_ok = (
        eightlane_readiness_md.exists()
        and eightlane_readiness_json.exists()
        and eightlane_readiness_csv.exists()
        and "RF_COMM_8LANE_HARDWARE_READINESS overall=NOT_READY_FOR_REAL_8LANE_HARDWARE" in eightlane_readiness_text
        and "Active A-endpoint lane coverage: `2/8`" in eightlane_readiness_text
        and "Active B/internal lane coverage: `2/8`" in eightlane_readiness_text
        and "Candidate A/B 8-lane XDC coverage: `8/8`, `8/8`" in eightlane_readiness_text
        and "Candidate A-only external 8-lane XDC coverage: `8/8`, B ports `0/8`" in eightlane_readiness_text
        and "Hardware script lane limit: `1..8`" in eightlane_readiness_text
        and "HW-SCRIPT-LANE-LIMIT" in eightlane_readiness_csv_text
        and "ACTIVE-XDC-A-ENDPOINT" in eightlane_readiness_csv_text
        and "CANDIDATE-XDC-8LANE-COVERAGE" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-XDC-8LANE" in eightlane_readiness_csv_text
        and "PASS_CANDIDATE_REVIEW_REQUIRED" in eightlane_readiness_csv_text
        and "DRAFT-XDC-8LANE-COVERAGE" in eightlane_readiness_csv_text
        and "SUPERSEDED_BY_CANDIDATE" in eightlane_readiness_csv_text
        and "SHUTDOWN-XDC-COVERAGE" in eightlane_readiness_csv_text
        and "CANDIDATE-SHUTDOWN-COVERAGE" in eightlane_readiness_csv_text
        and "CANDIDATE-SHUTDOWN-BITSTREAM" in eightlane_readiness_csv_text
        and "CANDIDATE-HW-PROJECT-BUILD" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-PROJECT-BUILD" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-LANE-SCAN" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-REDUCED-2LANE" in eightlane_readiness_csv_text
        and "PASS_REDUCED_2LANE_PLACE" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-REDUCED-1TO4LANE" in eightlane_readiness_csv_text
        and "PASS_REDUCED_UP_TO_4LANE_PLACE" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-REDUCED-5TO8-BOUNDARY" in eightlane_readiness_csv_text
        and "PASS_FIRST_BLOCKED_5LANE" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-REDUCED-5LANE-FRAG32" in eightlane_readiness_csv_text
        and "PASS_PLACE_5LANE_FRAG32" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-REDUCED-5LANE-FRAG32-ROUTE" in eightlane_readiness_csv_text
        and "PASS_ROUTE_TIMING_5LANE_FRAG32" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-REDUCED-5LANE-FRAG32-BITSTREAM" in eightlane_readiness_csv_text
        and "PASS_OFFLINE_5LANE_FRAG32_BITSTREAM_READY_REVIEW_REQUIRED" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-REDUCED-8LANE-FRAG16-BITSTREAM" in eightlane_readiness_csv_text
        and "PASS_OFFLINE_8LANE_FRAG16_BITSTREAM_READY_REVIEW_REQUIRED" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-REDUCED-2LANE-ROUTE" in eightlane_readiness_csv_text
        and "PASS_ROUTE_TIMING_REDUCED_2LANE" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-REDUCED-4LANE-ROUTE" in eightlane_readiness_csv_text
        and "PASS_ROUTE_TIMING_REDUCED_4LANE" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-REDUCED-4LANE-BITSTREAM" in eightlane_readiness_csv_text
        and "PASS_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED" in eightlane_readiness_csv_text
        and "A-ONLY-EXTERNAL-REDUCED-4LANE-BRINGUP-PLAN" in eightlane_readiness_csv_text
        and "READY_FOR_MANUAL_REVIEW_NO_HARDWARE_RUN" in eightlane_readiness_csv_text
        and "Candidate A-only external lane-count scan: `PLACE_PASS_ONLY_1LANE`" in eightlane_readiness_text
        and "max place-pass lane `1`" in eightlane_readiness_text
        and "first resource-blocked lane `2`" in eightlane_readiness_text
        and "Reduced A-only external 2-lane option: `PLACE_PASS_REDUCED_2LANE`" in eightlane_readiness_text
        and "TX/RX FIFO `128/128`" in eightlane_readiness_text
        and "Reduced A-only external 1..4 lane scan: `PLACE_PASS_REDUCED_UP_TO_4LANE`" in eightlane_readiness_text
        and "max place-pass lane `4`" in eightlane_readiness_text
        and "Reduced A-only external 5..8 lane extension: `FIRST_BLOCKED_AT_5LANE_REDUCED_PROFILE`" in eightlane_readiness_text
        and "first blocked lane `5`" in eightlane_readiness_text
        and "lane5 LUTs `17801/17600`" in eightlane_readiness_text
        and "lane5 slices `3869/3845`" in eightlane_readiness_text
        and "Reduced A-only external 5-lane fragment=32 probe: `PLACE_PASS_5LANE_FRAG32_REDUCED_PROFILE`" in eightlane_readiness_text
        and "LUTs `10697/17600`" in eightlane_readiness_text
        and "control sets `918`" in eightlane_readiness_text
        and "Reduced A-only external 5-lane fragment=32 route/timing: `ROUTE_TIMING_PASS_REDUCED_5LANE_FRAG32`" in eightlane_readiness_text
        and "WNS `1.571` ns" in eightlane_readiness_text
        and "route errors `0`" in eightlane_readiness_text
        and "Reduced A-only external 5-lane fragment=32 candidate bitstream: `PASS_OFFLINE_5LANE_FRAG32_BITSTREAM_READY_REVIEW_REQUIRED`" in eightlane_readiness_text
        and "sha256 `64213BD459D5CF8E6A487DC601D8942F1D938858AFAE5039CBB46FF3A39A903E`" in eightlane_readiness_text
        and "Reduced A-only external 8-lane fragment=16 candidate bitstream: `PASS_OFFLINE_8LANE_FRAG16_BITSTREAM_READY_REVIEW_REQUIRED`" in eightlane_readiness_text
        and "raw half `32.0` Mbit/s" in eightlane_readiness_text
        and "sha256 `F3661A68DB0F36FCAC96DE983538EA31B5AA2B50338B44A81DAB3E45999AC778`" in eightlane_readiness_text
        and "Reduced A-only external 2-lane route/timing: `ROUTE_TIMING_PASS_REDUCED_2LANE`" in eightlane_readiness_text
        and "WNS `1.58` ns" in eightlane_readiness_text
        and "Reduced A-only external 4-lane route/timing: `ROUTE_TIMING_PASS_REDUCED_4LANE`" in eightlane_readiness_text
        and "WNS `1.317` ns" in eightlane_readiness_text
        and "Reduced A-only external 4-lane candidate bitstream: `PASS_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED`" in eightlane_readiness_text
        and "size `2083858` bytes" in eightlane_readiness_text
        and "Reduced A-only external 4-lane bring-up plan: `READY_FOR_MANUAL_REVIEW_NO_HARDWARE_RUN`" in eightlane_readiness_text
        and "Candidate shutdown covers 64/64 TFDU signals" in eightlane_readiness_text
        and "Candidate shutdown bitstream was generated offline with 0 errors, 0 critical warnings" in eightlane_readiness_text
        and "21125 required vs 17600 available" in eightlane_readiness_text
        and "Slice LUTs: 45050/17600" in eightlane_readiness_text
    )
    eightlane_shutdown_build_ok = (
        eightlane_shutdown_build_md.exists()
        and eightlane_shutdown_build_json.exists()
        and eightlane_shutdown_build_csv.exists()
        and "RF_COMM_8LANE_SHUTDOWN_BUILD overall=PASS_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED" in eightlane_shutdown_build_text
        and "warnings=1, critical_warnings=0, errors=0" in eightlane_shutdown_build_text
        and "ZPS7-1 PS7 block required" in eightlane_shutdown_build_text
        and "No FPGA was programmed; no UART was written; no TFDU was driven." in eightlane_shutdown_build_text
        and "BITSTREAM-FILE" in eightlane_shutdown_build_csv_text
        and "VIVADO-RESULT" in eightlane_shutdown_build_csv_text
        and "KNOWN-DRC-WARNING" in eightlane_shutdown_build_csv_text
    )
    eightlane_candidate_project_ok = (
        eightlane_candidate_project_md.exists()
        and eightlane_candidate_project_json.exists()
        and eightlane_candidate_project_csv.exists()
        and "RF_COMM_8LANE_CANDIDATE_PROJECT_BUILD overall=SYNTH_PASS_IMPL_BLOCKED_LUT_OVERUTILIZED" in eightlane_candidate_project_text
        and "Slice LUT requirement: `21125` / `17600`" in eightlane_candidate_project_text
        and "SYNTHESIS | PASS" in eightlane_candidate_project_text
        and "IMPLEMENTATION | BLOCKED_RESOURCE" in eightlane_candidate_project_text
        and "NO-HARDWARE-ACTION | PASS" in eightlane_candidate_project_text
    )
    eightlane_external_project_ok = (
        eightlane_external_project_md.exists()
        and eightlane_external_project_json.exists()
        and eightlane_external_project_csv.exists()
        and "RF_COMM_8LANE_EXTERNAL_PROJECT_BUILD overall=SYNTH_PASS_IMPL_BLOCKED_RESOURCE_OVERUTILIZED" in eightlane_external_project_text
        and "FDRE: 52477/35500" in eightlane_external_project_text
        and "Slice LUTs: 45050/17600" in eightlane_external_project_text
        and "BD-8LANE-EXTERNAL-CONFIG | PASS" in eightlane_external_project_text
        and "SYNTHESIS | PASS" in eightlane_external_project_text
        and "IMPLEMENTATION | BLOCKED_RESOURCE" in eightlane_external_project_text
        and "PORT1-XDC-RESTORE | PASS" in eightlane_external_project_text
        and "NO-HARDWARE-ACTION | PASS" in eightlane_external_project_text
        and "NO-ETHERNET-BOUNDARY | DEFERRED" in eightlane_external_project_text
    )
    external_lane_scan_ok = (
        external_lane_scan_md.exists()
        and external_lane_scan_json.exists()
        and external_lane_scan_csv.exists()
        and "RF_COMM_EXTERNAL_LANE_RESOURCE_SCAN overall=PLACE_PASS_ONLY_1LANE first_blocked_lane=2 max_place_pass_lane=1" in external_lane_scan_text
        and "Max lane count that reached `place_design`: `1`" in external_lane_scan_text
        and "First lane count blocked by resource DRC: `2`" in external_lane_scan_text
        and "No FPGA was programmed; no UART was written; no TFDU was driven." in external_lane_scan_text
        and "1,PLACE_PASS" in external_lane_scan_csv_text
        and "2,PLACE_RESOURCE_BLOCKED" in external_lane_scan_csv_text
        and "8,PLACE_RESOURCE_BLOCKED" in external_lane_scan_csv_text
    )
    external_option_scan_ok = (
        external_option_scan_md.exists()
        and external_option_scan_json.exists()
        and external_option_scan_csv.exists()
        and "RF_COMM_EXTERNAL_RESOURCE_OPTION_SCAN overall=PLACE_PASS_REDUCED_2LANE lane=2 fragment_bytes=64 max_packet_bytes=255 tx_fifo=128 rx_fifo=128" in external_option_scan_text
        and "Reduced profile: `IR_FRAGMENT_BYTES=64`, `IR_MAX_PACKET_BYTES=255`, `TX_ASYNC_FIFO_DEPTH=128`, `RX_ASYNC_FIFO_DEPTH=128`" in external_option_scan_text
        and "offline Vivado place-design result only" in external_option_scan_text
        and "No FPGA was programmed; no UART was written; no TFDU was driven." in external_option_scan_text
        and "2,PLACE_PASS_REDUCED_PROFILE,64,255,128,128" in external_option_scan_csv_text
    )
    external_reduced_lane_scan_ok = (
        external_reduced_lane_scan_md.exists()
        and external_reduced_lane_scan_json.exists()
        and external_reduced_lane_scan_csv.exists()
        and "RF_COMM_EXTERNAL_REDUCED_LANE_RESOURCE_SCAN overall=PLACE_PASS_REDUCED_UP_TO_4LANE max_place_pass_lane=4 first_blocked_lane=None" in external_reduced_lane_scan_text
        and "Profile: `lanes=1 2 3 4`, `fragment=64`, `max_packet=255`, `TX/RX FIFO=128/128`." in external_reduced_lane_scan_text
        and "Max reduced lane count that reached place_design: `4`" in external_reduced_lane_scan_text
        and "The current board has no Ethernet cable, so real network acceptance remains deferred." in external_reduced_lane_scan_text
        and "No FPGA was programmed; no UART was written; no TFDU was driven." in external_reduced_lane_scan_text
        and "1,PLACE_PASS_REDUCED_PROFILE" in external_reduced_lane_scan_csv_text
        and "2,PLACE_PASS_REDUCED_PROFILE" in external_reduced_lane_scan_csv_text
        and "3,PLACE_PASS_REDUCED_PROFILE" in external_reduced_lane_scan_csv_text
        and "4,PLACE_PASS_REDUCED_PROFILE" in external_reduced_lane_scan_csv_text
    )
    external_reduced_5to8_ok = (
        external_reduced_5to8_md.exists()
        and external_reduced_5to8_json.exists()
        and external_reduced_5to8_csv.exists()
        and "RF_COMM_EXTERNAL_REDUCED_5TO8_EXTENSION overall=FIRST_BLOCKED_AT_5LANE_REDUCED_PROFILE first_blocked_lane=5 max_place_pass_lane=4 lane5_luts=17801/17600 restored_2lane=1 stopped_after_stall=1" in external_reduced_5to8_text
        and "First blocked reduced lane count: `5`" in external_reduced_5to8_text
        and "Last proven reduced lane count remains: `4`" in external_reduced_5to8_text
        and "Lane 5 LUT usage at placement failure: `17801/17600` total LUTs" in external_reduced_5to8_text
        and "Lane 5 slice demand at placement failure: `3869/3845` slices" in external_reduced_5to8_text
        and "Lane 5 control sets: `1274`" in external_reduced_5to8_text
        and "Project restored to active 2-lane stream_bidir / PORT1.xdc: `1`" in external_reduced_5to8_text
        and "No FPGA was programmed; no UART was written; no TFDU was driven." in external_reduced_5to8_text
        and "5,PLACE_RESOURCE_BLOCKED" in external_reduced_5to8_csv_text
        and "6,STOPPED_AFTER_STALL" in external_reduced_5to8_csv_text
        and "7,NOT_STARTED_AFTER_STOP" in external_reduced_5to8_csv_text
        and "8,NOT_STARTED_AFTER_STOP" in external_reduced_5to8_csv_text
    )
    external_reduced_5lane_frag32_ok = (
        external_reduced_5lane_frag32_md.exists()
        and external_reduced_5lane_frag32_json.exists()
        and external_reduced_5lane_frag32_csv.exists()
        and "RF_COMM_EXTERNAL_REDUCED_5LANE_FRAG32 overall=PLACE_PASS_5LANE_FRAG32_REDUCED_PROFILE lane=5 fragment_bytes=32 max_packet_bytes=128 luts=10697/17600 regs=14001/35200 bram_tiles=4.5/60.0 control_sets=918 restored_2lane=1 no_ethernet=1" in external_reduced_5lane_frag32_text
        and "Profile: `5lane / fragment_bytes=32 / max_packet_bytes=128 / tx_fifo=128 / rx_fifo=128 / stream_phy_dbg_select=6`" in external_reduced_5lane_frag32_text
        and "Place result: `PASS`" in external_reduced_5lane_frag32_text
        and "Placed LUTs: `10697/17600`" in external_reduced_5lane_frag32_text
        and "Slice registers: `14001/35200`" in external_reduced_5lane_frag32_text
        and "BRAM tiles: `4.5/60.0`" in external_reduced_5lane_frag32_text
        and "Control sets: `918`" in external_reduced_5lane_frag32_text
        and "LUT delta versus 5lane fragment=64 failure: `-7104`" in external_reduced_5lane_frag32_text
        and "Project restored to active 2-lane stream_bidir / PORT1.xdc: `1`" in external_reduced_5lane_frag32_text
        and "No FPGA was programmed; no UART was written; no TFDU was driven." in external_reduced_5lane_frag32_text
        and "PLACE,PASS" in external_reduced_5lane_frag32_csv_text
        and "LUTS,PASS,10697/17600" in external_reduced_5lane_frag32_csv_text
        and "RESTORE-2LANE,PASS" in external_reduced_5lane_frag32_csv_text
        and "NO-ETHERNET-BOUNDARY,DEFERRED" in external_reduced_5lane_frag32_csv_text
    )
    external_reduced_5lane_frag32_route_ok = (
        external_reduced_5lane_frag32_route_md.exists()
        and external_reduced_5lane_frag32_route_json.exists()
        and external_reduced_5lane_frag32_route_csv.exists()
        and "RF_COMM_EXTERNAL_REDUCED_5LANE_FRAG32_ROUTE overall=ROUTE_TIMING_PASS_REDUCED_5LANE_FRAG32 wns=1.571 whs=0.012 route_errors=0" in external_reduced_5lane_frag32_route_text
        and "Profile: `lane=5`, `fragment=32`, `max_packet=128`, `TX/RX FIFO=128/128`." in external_reduced_5lane_frag32_route_text
        and "Timing: `WNS=1.571 ns`, `WHS=0.012 ns`, constraints met `True`" in external_reduced_5lane_frag32_route_text
        and "Routing: `routing_errors=0`, fully routed nets `22564/22564`" in external_reduced_5lane_frag32_route_text
        and "DRC: `6` warning/advisory violations, no critical warning/error DRC rows." in external_reduced_5lane_frag32_route_text
        and "No FPGA was programmed; no UART was written; no TFDU was driven." in external_reduced_5lane_frag32_route_text
        and "TIMING,PASS" in external_reduced_5lane_frag32_route_csv_text
        and "ROUTE,PASS" in external_reduced_5lane_frag32_route_csv_text
        and "NO-ETHERNET-BOUNDARY,DEFERRED" in external_reduced_5lane_frag32_route_csv_text
    )
    external_reduced_5lane_frag32_bitstream_ok = (
        external_reduced_5lane_frag32_bitstream_md.exists()
        and external_reduced_5lane_frag32_bitstream_json.exists()
        and external_reduced_5lane_frag32_bitstream_csv.exists()
        and "RF_COMM_EXTERNAL_REDUCED_5LANE_FRAG32_BITSTREAM overall=PASS_OFFLINE_5LANE_FRAG32_BITSTREAM_READY_REVIEW_REQUIRED" in external_reduced_5lane_frag32_bitstream_text
        and "Bitstream SHA256: `64213BD459D5CF8E6A487DC601D8942F1D938858AFAE5039CBB46FF3A39A903E`" in external_reduced_5lane_frag32_bitstream_text
        and "Profile: `lane=5`, `fragment=32`, `max_packet=128`, `stream_phy_dbg_select=6`." in external_reduced_5lane_frag32_bitstream_text
        and "Timing: `WNS=1.571 ns`, `WHS=0.012 ns`, constraints met `True`" in external_reduced_5lane_frag32_bitstream_text
        and "Routing: `routing_errors=0`, fully routed nets `22564/22564`" in external_reduced_5lane_frag32_bitstream_text
        and "Vivado final counts: warnings=5, critical_warnings=0, errors=0." in external_reduced_5lane_frag32_bitstream_text
        and "No FPGA was programmed; no UART was written; no TFDU was driven." in external_reduced_5lane_frag32_bitstream_text
        and "BITSTREAM-FILE,PASS" in external_reduced_5lane_frag32_bitstream_csv_text
        and "TIMING,PASS" in external_reduced_5lane_frag32_bitstream_csv_text
        and "NO-ETHERNET-BOUNDARY,DEFERRED" in external_reduced_5lane_frag32_bitstream_csv_text
    )
    external_reduced_8lane_frag16_bitstream_ok = (
        external_reduced_8lane_frag16_bitstream_md.exists()
        and external_reduced_8lane_frag16_bitstream_json.exists()
        and external_reduced_8lane_frag16_bitstream_csv.exists()
        and "RF_COMM_EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM overall=PASS_OFFLINE_8LANE_FRAG16_BITSTREAM_READY_REVIEW_REQUIRED" in external_reduced_8lane_frag16_bitstream_text
        and "Bitstream SHA256: `F3661A68DB0F36FCAC96DE983538EA31B5AA2B50338B44A81DAB3E45999AC778`" in external_reduced_8lane_frag16_bitstream_text
        and "Profile: `lane=8`, `fragment=16`, `max_packet=64`, `stream_phy_dbg_select=6`." in external_reduced_8lane_frag16_bitstream_text
        and "Raw capacity: `32.000 Mbit/s half-duplex`, `16.000 Mbit/s per direction full-duplex with 4+4 lane partition`." in external_reduced_8lane_frag16_bitstream_text
        and "Timing: `WNS=1.153 ns`, `WHS=0.009 ns`, constraints met `True`" in external_reduced_8lane_frag16_bitstream_text
        and "Routing: `routing_errors=0`, fully routed nets `22464/22464`" in external_reduced_8lane_frag16_bitstream_text
        and "Vivado final counts: warnings=5, critical_warnings=0, errors=0." in external_reduced_8lane_frag16_bitstream_text
        and "No FPGA was programmed; no UART was written; no TFDU was driven." in external_reduced_8lane_frag16_bitstream_text
        and "RAW-CAPACITY,PASS_RAW_32_16" in external_reduced_8lane_frag16_bitstream_csv_text
        and "BITSTREAM-FILE,PASS" in external_reduced_8lane_frag16_bitstream_csv_text
        and "TIMING,PASS" in external_reduced_8lane_frag16_bitstream_csv_text
        and "NO-ETHERNET-BOUNDARY,DEFERRED" in external_reduced_8lane_frag16_bitstream_csv_text
    )
    external_reduced_route_ok = (
        external_reduced_route_md.exists()
        and external_reduced_route_json.exists()
        and external_reduced_route_csv.exists()
        and "RF_COMM_EXTERNAL_REDUCED_2LANE_ROUTE overall=ROUTE_TIMING_PASS_REDUCED_2LANE wns=1.58 whs=0.017 route_errors=0" in external_reduced_route_text
        and "Timing: `WNS=1.58 ns`, `WHS=0.017 ns`, constraints met `True`" in external_reduced_route_text
        and "Routing: `routing_errors=0`" in external_reduced_route_text
        and "No FPGA was programmed; no UART was written; no TFDU was driven." in external_reduced_route_text
        and "TIMING,PASS" in external_reduced_route_csv_text
        and "ROUTE,PASS" in external_reduced_route_csv_text
        and "NO-ETHERNET-BOUNDARY,DEFERRED" in external_reduced_route_csv_text
    )
    external_reduced_4lane_route_ok = (
        external_reduced_4lane_route_md.exists()
        and external_reduced_4lane_route_json.exists()
        and external_reduced_4lane_route_csv.exists()
        and "RF_COMM_EXTERNAL_REDUCED_4LANE_ROUTE overall=ROUTE_TIMING_PASS_REDUCED_4LANE wns=1.317 whs=0.017 route_errors=0" in external_reduced_4lane_route_text
        and "Timing: `WNS=1.317 ns`, `WHS=0.017 ns`, constraints met `True`" in external_reduced_4lane_route_text
        and "Routing: `routing_errors=0`" in external_reduced_4lane_route_text
        and "Slice LUTs | 14028 | 17600 | 79.70%" in external_reduced_4lane_route_text
        and "No FPGA was programmed; no UART was written; no TFDU was driven." in external_reduced_4lane_route_text
        and "TIMING,PASS" in external_reduced_4lane_route_csv_text
        and "ROUTE,PASS" in external_reduced_4lane_route_csv_text
        and "NO-ETHERNET-BOUNDARY,DEFERRED" in external_reduced_4lane_route_csv_text
    )
    external_reduced_4lane_bitstream_ok = (
        external_reduced_4lane_bitstream_md.exists()
        and external_reduced_4lane_bitstream_json.exists()
        and external_reduced_4lane_bitstream_csv.exists()
        and "RF_COMM_EXTERNAL_REDUCED_4LANE_BITSTREAM overall=PASS_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED" in external_reduced_4lane_bitstream_text
        and "Bitstream SHA256: `BDDE1CE8416E05EBAD8BF24FF96FEC04419CC3C7C35841CBB3ED825425714779`" in external_reduced_4lane_bitstream_text
        and "Timing: `WNS=1.317 ns`, `WHS=0.017 ns`, constraints met `True`" in external_reduced_4lane_bitstream_text
        and "Vivado final counts: warnings=5, critical_warnings=0, errors=0." in external_reduced_4lane_bitstream_text
        and "No FPGA was programmed; no UART was written; no TFDU was driven." in external_reduced_4lane_bitstream_text
        and "BITSTREAM-FILE,PASS" in external_reduced_4lane_bitstream_csv_text
        and "TIMING,PASS" in external_reduced_4lane_bitstream_csv_text
        and "NO-ETHERNET-BOUNDARY,DEFERRED" in external_reduced_4lane_bitstream_csv_text
    )
    external_reduced_4lane_bringup_ok = (
        external_reduced_4lane_bringup_md.exists()
        and external_reduced_4lane_bringup_json.exists()
        and external_reduced_4lane_bringup_csv.exists()
        and "RF_COMM_EXTERNAL_REDUCED_4LANE_BRINGUP_PLAN overall=READY_FOR_MANUAL_REVIEW_NO_HARDWARE_RUN" in external_reduced_4lane_bringup_text
        and "Candidate bitstream SHA256: `BDDE1CE8416E05EBAD8BF24FF96FEC04419CC3C7C35841CBB3ED825425714779`" in external_reduced_4lane_bringup_text
        and "Shutdown bitstream SHA256: `97F543060E570499AA42CD554D04896BEFE47F4BD9E74C19C5275CAC112D97FD`" in external_reduced_4lane_bringup_text
        and "Program the 8-lane shutdown candidate before and after any future TFDU-driven run." in external_reduced_4lane_bringup_text
        and "Do not retry real TCP/DHCP or two-AX7010 network acceptance while the board has no Ethernet cable." in external_reduced_4lane_bringup_text
        and "PINMAP-4LANE,PASS_REVIEW_REQUIRED" in external_reduced_4lane_bringup_csv_text
        and "SAFETY-SCRIPTS,PASS" in external_reduced_4lane_bringup_csv_text
        and "NO-HARDWARE-ACTION,PASS" in external_reduced_4lane_bringup_csv_text
    )
    rate_boundary_proof_pass = (
        rate_boundary_md is not None
        and rate_boundary_md.exists()
        and rate_boundary_json is not None
        and rate_boundary_json.exists()
        and case_pass(rows, "rate_boundary_proof")
        and "RATE_BOUNDARY_PROOF_PASS" in post_summary_text
        and "RATE_BOUNDARY_PROOF_PASS" in rate_boundary_text
        and "raw_half_8lane_mbps=32.000000" in post_summary_text
        and "raw_fdx_4lane_per_dir_mbps=16.000000" in post_summary_text
        and "effective_32_16_possible_with_current_raw=0" in post_summary_text
        and "rate_claim_must_be_raw_phy=1" in post_summary_text
        and "required_lanes_half_payload32=9" in post_summary_text
        and "required_lanes_per_dir_fdx_payload16=5" in post_summary_text
    )
    payload_gap_closure_pass = (
        payload_gap_closure_md.exists()
        and payload_gap_closure_json.exists()
        and payload_gap_closure_csv.exists()
        and "- Overall: `PASS_RAW_ONLY_GAP_CLASSIFIED`" in payload_gap_closure_text
        and "OFFLINE_RATE_MODEL_NOT_HARDWARE" in payload_gap_closure_text
        and "No hardware programming: `1`" in payload_gap_closure_text
        and "No UART write: `1`" in payload_gap_closure_text
        and "No TFDU drive: `1`" in payload_gap_closure_text
        and "28.966188" in payload_gap_closure_text
        and "14.483094" in payload_gap_closure_text
        and "4.418945" in payload_gap_closure_text
        and "`9` half-duplex lanes" in payload_gap_closure_text
        and "`5` lanes per direction" in payload_gap_closure_text
        and "cannot be honestly closed as 32/16 Mbit/s effective payload" in payload_gap_closure_text
        and '"overall": "PASS_RAW_ONLY_GAP_CLASSIFIED"' in payload_gap_closure_json_text
        and '"packet_ack_required_raw_per_lane_mbps": 4.418945' in payload_gap_closure_json_text
        and "packet_ack_required_half_lanes,9,CLOSURE_OPTION" in payload_gap_closure_csv_text
        and "packet_ack_required_fdx_lanes_per_direction,5,CLOSURE_OPTION" in payload_gap_closure_csv_text
    )
    g1_capped_pass = (
        "SIM_OFFLINE_CAPPED_10MIN_SOAK_PASS" in g1_report_text
        and "sent=267892" in g1_report_text
        and "rx_ok=267892" in g1_report_text
        and "HW_WINDOW_TO_SHUTDOWN_END_SECONDS=582.2" in g1_report_text
    )
    post_gate_pass = (
        "POST_G1_TARGET_SIM_GATE_PASS=1" in post_summary_text
        and "POST_G1_TARGET_SIM_GATE_FAIL_COUNT=0" in post_summary_text
    )
    post_gate_pass_count = extract_int(r"POST_G1_TARGET_SIM_GATE_PASS_COUNT=([0-9]+)", post_summary_text)
    post_gate_fail_count = extract_int(r"POST_G1_TARGET_SIM_GATE_FAIL_COUNT=([0-9]+)", post_summary_text)
    rotating_model_pass = (
        case_pass(rows, "rotating_soak_model")
        and "seconds=7200" in post_summary_text
        and "rotations=72000" in post_summary_text
        and "sectors=288000" in post_summary_text
    )
    rotating_8lane_model_pass = (
        case_pass(rows, "rotating_8lane_soak_model")
        and "ROTATING_AUTOROUTE_8LANE_CAPPED_SOAK_MODEL_PASS" in post_summary_text
        and "runtime_cap_seconds=600" in post_summary_text
        and "seconds=600" in post_summary_text
        and "rotations=6000" in post_summary_text
        and "sectors=48000" in post_summary_text
        and "lane_count=8" in post_summary_text
        and "good_lane_coverage=11111111" in post_summary_text
        and "attempted_lane_coverage=11111111" in post_summary_text
    )
    rotating_stress_pass = (
        case_pass(rows, "rotating_autoroute")
        and "rpm=600" in post_summary_text
        and "shaft_diameter_mm=200" in post_summary_text
    )
    pc_offline_pass = case_pass(rows, "ps_pc_offline") and "PS_PC_OFFLINE_GATES_PASS" in post_summary_text
    two_system_offline_pass = (
        case_pass(rows, "two_ax7010_end_to_end_offline")
        and "TWO_AX7010_END_TO_END_OFFLINE_PASS" in post_summary_text
        and "endpoints=2" in post_summary_text
        and "queued_reconnect_rx=1" in post_summary_text
        and "lane_count=8" in post_summary_text
        and "tx_lane_coverage=0xff" in post_summary_text
        and "rx_lane_coverage=0xff" in post_summary_text
        and "- Overall: `PASS`" in two_ax7010_model_text
        and "- Evidence type: `OFFLINE_MODEL_NOT_HARDWARE`" in two_ax7010_model_text
        and "hdx_tx_lane_coverage" in two_ax7010_model_text
        and "`0xff`" in two_ax7010_model_text
        and "fdx_a_to_b_tx_lane_coverage" in two_ax7010_model_text
        and "`0x0f`" in two_ax7010_model_text
        and "fdx_b_to_a_tx_lane_coverage" in two_ax7010_model_text
        and "`0xf0`" in two_ax7010_model_text
        and '"a_tx_lane_mask": "0x0f"' in two_ax7010_model_json_text
        and '"b_tx_lane_mask": "0xf0"' in two_ax7010_model_json_text
        and "coverage,PASS,fdx_a_to_b_tx_lane_coverage,0x0f" in two_ax7010_model_csv_text
        and "coverage,PASS,fdx_b_to_a_tx_lane_coverage,0xf0" in two_ax7010_model_csv_text
    )
    full_system_capped_model_pass = (
        case_pass(rows, "full_system_capped_digital_twin")
        and "FULL_SYSTEM_CAPPED_DIGITAL_TWIN_PASS" in post_summary_text
        and "original_target_seconds=7200" in post_summary_text
        and "runtime_cap_seconds=600" in post_summary_text
        and "seconds=600" in post_summary_text
        and "rpm=600" in post_summary_text
        and "rotations=6000" in post_summary_text
        and "sectors=48000" in post_summary_text
        and "lane_count=8" in post_summary_text
        and "tx_lane_coverage=0xff" in post_summary_text
        and "rx_lane_coverage=0xff" in post_summary_text
        and "route_map_coverage=0xff" in post_summary_text
        and "source_lane_coverage=0xff" in post_summary_text
        and "rate_claim=raw_phy_only" in post_summary_text
        and "- Overall: `PASS`" in full_system_twin_text
        and "- Evidence type: `OFFLINE_MODEL_NOT_HARDWARE`" in full_system_twin_text
        and "fdx_a_to_b_tx_lane_coverage" in full_system_twin_text
        and "`0x0f`" in full_system_twin_text
        and "fdx_b_to_a_tx_lane_coverage" in full_system_twin_text
        and "`0xf0`" in full_system_twin_text
        and "fdx_a_to_b_rx_lane_coverage" in full_system_twin_text
        and "fdx_b_to_a_rx_lane_coverage" in full_system_twin_text
        and '"fdx_a_to_b_tx_lane_coverage": 15' in full_system_twin_json_text
        and '"fdx_b_to_a_tx_lane_coverage": 240' in full_system_twin_json_text
        and "coverage,PASS,fdx_a_to_b_tx_lane_coverage,0x0f" in full_system_twin_csv_text
        and "coverage,PASS,fdx_b_to_a_tx_lane_coverage,0xf0" in full_system_twin_csv_text
    )
    full_system_offline_envelope_pass = (
        full_system_envelope_md.exists()
        and full_system_envelope_json.exists()
        and full_system_envelope_csv.exists()
        and "RF_COMM_FULL_SYSTEM_OFFLINE_TARGET_ENVELOPE overall=PASS_OFFLINE_TARGET_ENVELOPE_NOT_HARDWARE checks=15 failures=0" in full_system_envelope_text
        and "NO_HARDWARE_PROGRAMMING=1" in full_system_envelope_text
        and "NO_UART_WRITE=1" in full_system_envelope_text
        and "NO_TFDU_DRIVE=1" in full_system_envelope_text
        and "REAL_BOARD_TCP_DHCP_ACCEPTANCE=0" in full_system_envelope_text
        and "REAL_TWO_AX7010_TRAFFIC_ACCEPTANCE=0" in full_system_envelope_text
        and "REAL_ROTATING_SHAFT_ACCEPTANCE=0" in full_system_envelope_text
        and "REAL_8LANE_TFDU_ACCEPTANCE=0" in full_system_envelope_text
        and "CURRENT_NO_ETHERNET_CABLE_UNCHANGEABLE_NOW=1" in full_system_envelope_text
        and "RAW_RATE_CLAIM_ONLY=1" in full_system_envelope_text
        and '"overall": "PASS_OFFLINE_TARGET_ENVELOPE_NOT_HARDWARE"' in full_system_envelope_json_text
        and '"failures": 0' in full_system_envelope_json_text
        and "raw_rate_target_envelope,rate,PASS" in full_system_envelope_csv_text
        and "half_duplex_8lane_coverage,lane_coverage,PASS" in full_system_envelope_csv_text
        and "full_duplex_4plus4_partition,lane_coverage,PASS" in full_system_envelope_csv_text
        and "rotating_autoroute_search,autoroute,PASS" in full_system_envelope_csv_text
        and "rotating_dynamic_permutation_autoroute,autoroute,PASS" in full_system_envelope_csv_text
        and "link_fault_recovery_paths,robustness,PASS" in full_system_envelope_csv_text
        and "network_recovery_paths,network,PASS" in full_system_envelope_csv_text
        and "real_acceptance_boundary,boundary,PASS_BOUNDARY_NOT_HARDWARE" in full_system_envelope_csv_text
        and "current_no_ethernet_boundary,boundary,PASS_BOUNDARY_NO_ETHERNET" in full_system_envelope_csv_text
    )
    rotating_autoroute_offline_evidence_pass = (
        rotating_autoroute_offline_md.exists()
        and rotating_autoroute_offline_json.exists()
        and rotating_autoroute_offline_csv.exists()
        and "RF_COMM_ROTATING_AUTOROUTE_OFFLINE_EVIDENCE overall=PASS_OFFLINE_ROTATING_AUTOROUTE_EVIDENCE checks=13" in rotating_autoroute_offline_text
        and "NO_HARDWARE_PROGRAMMING=1" in rotating_autoroute_offline_text
        and "NO_UART_WRITE=1" in rotating_autoroute_offline_text
        and "NO_TFDU_DRIVE=1" in rotating_autoroute_offline_text
        and "REAL_ROTATING_SHAFT_ACCEPTANCE=0" in rotating_autoroute_offline_text
        and '"overall": "PASS_OFFLINE_ROTATING_AUTOROUTE_EVIDENCE"' in rotating_autoroute_offline_json_text
        and "four_lane_rotating_stress,PASS" in rotating_autoroute_offline_csv_text
        and "eight_lane_autoroute,PASS" in rotating_autoroute_offline_csv_text
        and "eight_lane_capped_rotating_model,PASS" in rotating_autoroute_offline_csv_text
        and "two_hour_equivalent_model,PASS" in rotating_autoroute_offline_csv_text
        and "full_system_capped_twin,PASS" in rotating_autoroute_offline_csv_text
        and "two_ax7010_offline_route_reconnect,PASS" in rotating_autoroute_offline_csv_text
        and "dynamic_permutation_autoroute,PASS" in rotating_autoroute_offline_csv_text
        and "network_fault_recovery,PASS" in rotating_autoroute_offline_csv_text
        and "real_hardware_boundary,DEFERRED" in rotating_autoroute_offline_csv_text
        and "real_acceptance_not_overclaimed,PASS" in rotating_autoroute_offline_csv_text
    )
    multi_sim_pass = all_cases_pass(
        rows,
        [
            "stream_4lane",
            "multi",
            "multi_8lane",
            "max_fragment_8lane",
            "multi_impair",
            "degrade",
            "route",
            "autoroute",
            "autoroute_8lane",
            "fdx",
            "fdx_4plus4",
        ],
    )
    eight_lane_sim_pass = (
        case_pass(rows, "multi_8lane")
        and "LOOPBACK_8LANE_PASS" in post_summary_text
        and "max_busy_lanes=8" in post_summary_text
        and "max_inflight_frags=8" in post_summary_text
    )
    max_fragment_8lane_sim_pass = (
        case_pass(rows, "max_fragment_8lane")
        and "LOOPBACK_8LANE_MAX_FRAGMENT_PASS" in post_summary_text
        and "payload_bytes=2040" in post_summary_text
        and "fragment_bytes=255" in post_summary_text
        and "max_busy_lanes=8" in post_summary_text
        and "max_inflight_frags=8" in post_summary_text
    )
    fdx_4plus4_sim_pass = (
        case_pass(rows, "fdx_4plus4")
        and "LOOPBACK_FULL_DUPLEX_4PLUS4_LANE_PASS" in post_summary_text
        and "max_a_busy=4" in post_summary_text
        and "max_b_busy=4" in post_summary_text
        and "max_total_busy=8" in post_summary_text
    )
    eight_lane_autoroute_sim_pass = (
        case_pass(rows, "autoroute_8lane")
        and "LOOPBACK_8LANE_AUTOROUTE_PASS" in post_summary_text
        and "good_src_coverage=11111111" in post_summary_text
        and "tx_attempt_coverage=11111111" in post_summary_text
    )
    two_lane_perf_pass = all_cases_pass(rows, ["stream_bidir_b0_2lane_perf", "stream_parallel_asym_2lane_perf"])
    eight_lane_hw_evidence = eightlane_hw_real_summary is not None
    two_system_evidence = two_ax7010_real_summary is not None
    board_tcp_acceptance_pass = (
        "BOARD_TCP_DHCP_ACCEPTANCE_PASS=1" in board_tcp_text
        and "BOARD_TCP_DHCP_ACCEPTANCE_BLOCKED=0" in board_tcp_text
        and "SMOKE_OK=1" in board_tcp_text
        and "RECONNECT_OK=1" in board_tcp_text
        and "DHCP_OR_STATIC_EVIDENCE_OK=1" in board_tcp_text
        and "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1" in board_tcp_text
        and "NO_TX_DATA_DONE_BY_THIS_SCRIPT=1" in board_tcp_text
        and "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1" in board_tcp_text
    )
    board_tcp_blocked = "BOARD_TCP_DHCP_ACCEPTANCE_BLOCKED=1" in board_tcp_text
    ethernet_link_unavailable_now = (
        "BOARD_TCP_DHCP_BLOCKED_REASON=ethernet_link_not_up" in board_tcp_text
        or "TWO_AX7010_BLOCKED_REASON=ethernet_link_not_up" in two_ax7010_blocked_text
    )
    board_tcp_evidence = board_tcp_acceptance_pass
    real_rotation_evidence = rotating_shaft_real_summary is not None
    real_payload_throughput_evidence = bool(
        re.search(r"effective payload.*32.*PASS|end-to-end.*16.*PASS|PC-to-PC throughput.*PASS", g1_report_text + post_status_text, re.IGNORECASE)
    )
    shutdown_bitstream_ok = "shutdown_bitstream" in g1_config_text and "F72680DD3" in g1_config_text
    host_acceptance_runtime_cap_ok = (
        "$MaxContinuousRunSeconds = 600" in host_acceptance_text
        and "[Math]::Min($requestedDurationSeconds, $MaxContinuousRunSeconds)" in host_acceptance_text
        and 'Invoke-Traffic -Name "soak_2h" -DefaultDurationSeconds $MaxContinuousRunSeconds' in host_acceptance_text
    )
    boot_artifacts_ok = (
        boot_audit_md.exists()
        and boot_audit_json.exists()
        and re.search(r"\| ps_lwip_bridge \| PASS \|", boot_audit_text) is not None
        and re.search(r"\| ps_ps_loopback \| PASS \|", boot_audit_text) is not None
        and "stale inputs: `none`" in boot_audit_text
        and "app markers missing: `none`" in boot_audit_text
    )
    artifact_hashes_ok = (
        "design_shiboqi_wrapper.bit" in artifact_text
        and "rf_comm_ps_ps_loopback.elf" in artifact_text
        and "SHA256" in artifact_text
    )
    two_ax7010_safe_wrapper_ok = (
        two_ax7010_safe_wrapper.exists()
        and "$maxContinuousRunSeconds = 600" in two_ax7010_safe_wrapper_text
        and "[switch]$ProgramShutdownAfterRun" in two_ax7010_safe_wrapper_text
        and "program_shutdown_after_run_not_set" in two_ax7010_safe_wrapper_text
        and "TWO_AX7010_SHUTDOWN_AFTER_RUN_PASS=" in two_ax7010_safe_wrapper_text
        and "$criteriaCsv = Join-Path $reportsDir" in two_ax7010_safe_wrapper_text
        and "smoke_both" in two_ax7010_safe_wrapper_text
        and "bidirectional_traffic" in two_ax7010_safe_wrapper_text
        and "shutdown_after_run" in two_ax7010_safe_wrapper_text
        and "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1" in two_ax7010_safe_wrapper_text
        and "NO_UART_WRITE_DONE_BY_THIS_SCRIPT=1" in two_ax7010_safe_wrapper_text
        and "NO_TX_DATA_TO_REAL_BOARDS=1" in two_ax7010_offline_text
        and "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1" in two_ax7010_offline_text
        and "TWO_AX7010_OFFLINE_MODEL_PASS=1" in two_ax7010_offline_text
        and "TWO_AX7010_DRY_RUN=1" in two_ax7010_dryrun_text
        and "CONTINUOUS_RUNTIME_CAP_APPLIED=1" in two_ax7010_dryrun_text
        and "DURATION_SECONDS_EFFECTIVE=600" in two_ax7010_dryrun_text
        and "TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=1" in two_ax7010_blocked_text
        and "TWO_AX7010_BLOCKED_REASON=ethernet_link_not_up" in two_ax7010_blocked_text
        and "NO_TX_DATA_TO_REAL_BOARDS=1" in two_ax7010_blocked_text
        and "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1" in two_ax7010_blocked_text
    )
    rotating_shaft_safe_wrapper_ok = (
        rotating_shaft_safe_wrapper.exists()
        and "$maxContinuousRunSeconds = 600" in rotating_shaft_safe_wrapper_text
        and "[switch]$ProgramShutdownAfterRun" in rotating_shaft_safe_wrapper_text
        and "program_shutdown_after_run_not_set" in rotating_shaft_safe_wrapper_text
        and "ROTATING_SHAFT_REAL_ACCEPTANCE_PASS=" in rotating_shaft_safe_wrapper_text
        and "ROTATING_SHAFT_SHUTDOWN_AFTER_RUN_PASS=" in rotating_shaft_safe_wrapper_text
        and "ROTATING_SHAFT_DRY_RUN=1" in rotating_shaft_dryrun_text
        and "CONTINUOUS_RUNTIME_CAP_APPLIED=1" in rotating_shaft_dryrun_text
        and "DURATION_SECONDS_EFFECTIVE=600" in rotating_shaft_dryrun_text
        and "SHAFT_DIAMETER_MM=200" in rotating_shaft_dryrun_text
        and "RPM=600" in rotating_shaft_dryrun_text
        and "NO_TX_DATA_TO_REAL_BOARDS=1" in rotating_shaft_dryrun_text
        and "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1" in rotating_shaft_dryrun_text
    )
    rotating_fixture_log_validator_ok = (
        rotating_fixture_validator.exists()
        and "--template-only-ok" in rotating_fixture_validator_text
        and "--max-continuous-seconds" in rotating_fixture_validator_text
        and rotating_fixture_template.exists()
        and "shaft_diameter_mm" in rotating_fixture_template_text
        and "is_template" in rotating_fixture_template_text
        and "template row only" in rotating_fixture_template_text
        and rotating_fixture_validation_md.exists()
        and rotating_fixture_validation_json.exists()
        and rotating_fixture_validation_csv.exists()
        and "RF_COMM_ROTATING_FIXTURE_LOG_VALIDATION overall=TEMPLATE_READY_NOT_REAL_EVIDENCE" in rotating_fixture_validation_text
        and "Target diameter: `200.0` mm" in rotating_fixture_validation_text
        and "Target RPM: `600.0`" in rotating_fixture_validation_text
        and "Continuous segment cap: `600.0` seconds" in rotating_fixture_validation_text
        and "NO_HARDWARE_PROGRAMMING=1" in rotating_fixture_validation_text
        and "NO_UART_WRITE=1" in rotating_fixture_validation_text
        and "NO_TFDU_DRIVE=1" in rotating_fixture_validation_text
        and "REAL_ACCEPTANCE_EVIDENCE=0" in rotating_fixture_validation_text
        and "template row only" in rotating_fixture_validation_csv_text
    )
    real_acceptance_evidence_validator_ok = (
        real_acceptance_validator.exists()
        and real_acceptance_validation_md.exists()
        and real_acceptance_validation_json.exists()
        and real_acceptance_validation_csv.exists()
        and real_acceptance_template_manifest.exists()
        and "RF_COMM_REAL_ACCEPTANCE_EVIDENCE_VALIDATION overall=TEMPLATE_READY_NOT_REAL_EVIDENCE modes=5" in real_acceptance_validation_text
        and "NO_HARDWARE_PROGRAMMING=1" in real_acceptance_validation_text
        and "NO_UART_WRITE=1" in real_acceptance_validation_text
        and "NO_TFDU_DRIVE=1" in real_acceptance_validation_text
        and "REAL_ACCEPTANCE_EVIDENCE=0" in real_acceptance_validation_text
        and "ps_pc_tcp_dhcp" in real_acceptance_validation_csv_text
        and "two_ax7010" in real_acceptance_validation_csv_text
        and "product_loop" in real_acceptance_validation_csv_text
        and "rotating_shaft" in real_acceptance_validation_csv_text
        and "eight_lane" in real_acceptance_validation_csv_text
        and "TEMPLATE_READY" in real_acceptance_validation_csv_text
        and "ps_pc_tcp_dhcp" in real_acceptance_template_manifest_text
        and "two_ax7010" in real_acceptance_template_manifest_text
        and "product_loop" in real_acceptance_template_manifest_text
        and "rotating_shaft" in real_acceptance_template_manifest_text
        and "eight_lane" in real_acceptance_template_manifest_text
        and "two_ax7010_criteria_template.csv" in real_acceptance_template_manifest_text
        and "TWO_AX7010_SHUTDOWN_AFTER_RUN_PASS=1" in real_acceptance_validator_text
        and "validate_throughput_markers" in real_acceptance_validator_text
        and line_count(throughput_summary_template_text, "REQUIRED_MARKER=RAW_HALF_MBPS=32.0") == 4
        and line_count(throughput_summary_template_text, "REQUIRED_MARKER=RAW_FDX_PER_DIR_MBPS=16.0") == 4
        and line_count(throughput_summary_template_text, "REQUIRED_MARKER=RATE_CLAIM=raw_phy_only") == 4
        and line_count(throughput_summary_template_text, "REQUIRED_MARKER=EFFECTIVE_PAYLOAD_REPORTED=1") == 4
        and line_count(throughput_summary_template_text, "REQUIRED_MARKER=PAYLOAD_HALF_MBPS=") == 4
        and line_count(throughput_summary_template_text, "REQUIRED_MARKER=PAYLOAD_FDX_PER_DIR_MBPS=") == 4
        and line_count(throughput_summary_template_text, "REQUIRED_MARKER=PHYSICAL_MATRIX_GATE_EXIT=0") == 4
        and line_count(throughput_summary_template_text, "REQUIRED_MARKER=PHYSICAL_MATRIX_GATE_RESULT=PASS") == 4
        and line_count(throughput_summary_template_text, "FORBIDDEN_MARKER=physical_matrix_not_passing") == 4
        and line_count(throughput_summary_template_text, "FORBIDDEN_MARKER=PHYSICAL_MATRIX_GATE_RESULT=BLOCK") == 4
        and line_count(throughput_summary_template_text, "FORBIDDEN_MARKER=PHYSICAL_MATRIX_GATE_EXIT=2") == 4
        and line_count(throughput_summary_template_text, "FORBIDDEN_MARKER=PHYSICAL_MATRIX_GATE_EXIT=22") == 4
        and line_count(throughput_criteria_template_text, '"raw_payload_rate_separation",PASS,"replace_with_real_value","template row only"') == 4
        and line_count(throughput_criteria_template_text, '"payload_throughput_reported",PASS,"replace_with_real_value","template row only"') == 4
    )
    real_acceptance_validator_selftest_ok = (
        real_acceptance_validator_selftest_md.exists()
        and real_acceptance_validator_selftest_json.exists()
        and real_acceptance_validator_selftest_csv.exists()
        and "RF_COMM_REAL_ACCEPTANCE_VALIDATOR_SELFTEST overall=PASS_VALIDATOR_REJECTS_FALSE_REAL_EVIDENCE cases=12 failures=0" in real_acceptance_validator_selftest_text
        and "NO_HARDWARE_PROGRAMMING=1" in real_acceptance_validator_selftest_text
        and "NO_UART_WRITE=1" in real_acceptance_validator_selftest_text
        and "NO_TFDU_DRIVE=1" in real_acceptance_validator_selftest_text
        and "REAL_ACCEPTANCE_EVIDENCE_PRODUCED=0" in real_acceptance_validator_selftest_text
        and "TEMPLATE_SUMMARY_REJECTION=1" in real_acceptance_validator_selftest_text
        and "DRY_RUN_REJECTION=1" in real_acceptance_validator_selftest_text
        and "DURATION_CAP_REJECTION=1" in real_acceptance_validator_selftest_text
        and "SHUTDOWN_GATING_REJECTION=1" in real_acceptance_validator_selftest_text
        and "RAW_PAYLOAD_OVERCLAIM_REJECTION=1" in real_acceptance_validator_selftest_text
        and "ROTATING_TEMPLATE_FIXTURE_REJECTION=1" in real_acceptance_validator_selftest_text
        and "PHYSICAL_MATRIX_GATE_REJECTION=1" in real_acceptance_validator_selftest_text
        and '"overall": "PASS_VALIDATOR_REJECTS_FALSE_REAL_EVIDENCE"' in real_acceptance_validator_selftest_json_text
        and '"failures": 0' in real_acceptance_validator_selftest_json_text
        and '"real_acceptance_evidence_produced": false' in real_acceptance_validator_selftest_json_text
        and "template_summary_rejected_ps_pc_tcp_dhcp" in real_acceptance_validator_selftest_csv_text
        and "template_summary_rejected_two_ax7010" in real_acceptance_validator_selftest_csv_text
        and "template_summary_rejected_product_loop" in real_acceptance_validator_selftest_csv_text
        and "template_summary_rejected_rotating_shaft" in real_acceptance_validator_selftest_csv_text
        and "template_summary_rejected_eight_lane" in real_acceptance_validator_selftest_csv_text
        and "dry_run_blocked_rejected" in real_acceptance_validator_selftest_csv_text
        and "missing_shutdown_marker_rejected" in real_acceptance_validator_selftest_csv_text
        and "payload_over_raw_rejected" in real_acceptance_validator_selftest_csv_text
        and "duration_over_cap_rejected" in real_acceptance_validator_selftest_csv_text
        and "rotating_template_fixture_rejected" in real_acceptance_validator_selftest_csv_text
        and "eight_lane_shutdown_before_criterion_rejected" in real_acceptance_validator_selftest_csv_text
        and "missing_physical_matrix_gate_rejected" in real_acceptance_validator_selftest_csv_text
        and not re.search(r",FAIL,", real_acceptance_validator_selftest_csv_text)
    )
    real_acceptance_promotion_gate_ok = (
        real_acceptance_promotion_gate_md.exists()
        and real_acceptance_promotion_gate_json.exists()
        and real_acceptance_promotion_gate_csv.exists()
        and "RF_COMM_REAL_ACCEPTANCE_PROMOTION_GATE overall=BLOCKED_NOT_PROMOTABLE items=5 promotable=0" in real_acceptance_promotion_gate_text
        and "NO_HARDWARE_PROGRAMMING=1" in real_acceptance_promotion_gate_text
        and "NO_UART_WRITE=1" in real_acceptance_promotion_gate_text
        and "NO_TFDU_DRIVE=1" in real_acceptance_promotion_gate_text
        and "PROMOTED_TO_REAL_PASS_BY_THIS_SCRIPT=0" in real_acceptance_promotion_gate_text
        and "REAL_ACCEPTANCE_EVIDENCE_REQUIRED=1" in real_acceptance_promotion_gate_text
        and "TEMPLATE_OR_DRY_RUN_PROMOTION_ALLOWED=0" in real_acceptance_promotion_gate_text
        and '"overall": "BLOCKED_NOT_PROMOTABLE"' in real_acceptance_promotion_gate_json_text
        and '"items": 5' in real_acceptance_promotion_gate_json_text
        and '"promotable": 0' in real_acceptance_promotion_gate_json_text
        and '"promoted_to_real_pass_by_this_script": false' in real_acceptance_promotion_gate_json_text
        and "N03,ps_pc_tcp_dhcp,NOT_PROMOTABLE_CURRENTLY,0,DEFERRED_NO_ETHERNET,BLOCKED_EXTERNAL_PRECONDITIONS" in real_acceptance_promotion_gate_csv_text
        and "N04,two_ax7010,NOT_PROMOTABLE_CURRENTLY,0,MISSING_HARDWARE,BLOCKED_EXTERNAL_PRECONDITIONS" in real_acceptance_promotion_gate_csv_text
        and "S05,rotating_shaft,NOT_PROMOTABLE_CURRENTLY,0,MISSING_HARDWARE,BLOCKED_EXTERNAL_PRECONDITIONS" in real_acceptance_promotion_gate_csv_text
        and "A01,product_loop,NOT_PROMOTABLE_CURRENTLY,0,PARTIAL_G1_ONLY,BLOCKED_EXTERNAL_PRECONDITIONS" in real_acceptance_promotion_gate_csv_text
        and "A02,eight_lane,NOT_PROMOTABLE_CURRENTLY,0,MISSING_HARDWARE,BLOCKED_EXTERNAL_PRECONDITIONS" in real_acceptance_promotion_gate_csv_text
        and "current_board_ethernet_cable_unavailable" in real_acceptance_promotion_gate_csv_text
        and "current_board_ethernet_condition_not_changeable_now" in real_acceptance_promotion_gate_csv_text
        and "real_acceptance_evidence_missing" in real_acceptance_promotion_gate_csv_text
        and ",PROMOTABLE_TO_REAL_PASS," not in real_acceptance_promotion_gate_csv_text
    )
    duration_cap_compliance_ok = (
        duration_cap_compliance_md.exists()
        and duration_cap_compliance_json.exists()
        and duration_cap_compliance_csv.exists()
        and "RF_COMM_DURATION_CAP_COMPLIANCE overall=PASS_DURATION_CAP_600S checks=16 failures=0" in duration_cap_compliance_text
        and "MAX_CONTINUOUS_RUN_SECONDS=600" in duration_cap_compliance_text
        and "REAL_PHYSICAL_RUN_GT_600_ALLOWED=0" in duration_cap_compliance_text
        and "LEGACY_2H_NAME_REQUIRES_600S_CAP=1" in duration_cap_compliance_text
        and "NO_HARDWARE_PROGRAMMING=1" in duration_cap_compliance_text
        and "NO_UART_WRITE=1" in duration_cap_compliance_text
        and "NO_TFDU_DRIVE=1" in duration_cap_compliance_text
        and "REAL_ACCEPTANCE_EVIDENCE_PRODUCED=0" in duration_cap_compliance_text
        and '"overall": "PASS_DURATION_CAP_600S"' in duration_cap_compliance_json_text
        and '"failures": 0' in duration_cap_compliance_json_text
        and '"max_continuous_run_seconds": 600' in duration_cap_compliance_json_text
        and '"real_physical_run_gt_600_allowed": false' in duration_cap_compliance_json_text
        and "ps_lwip_readme_documents_600_cap,PASS" in duration_cap_compliance_csv_text
        and "host_acceptance_caps_soak_2h_to_600,PASS" in duration_cap_compliance_csv_text
        and "dryrun_wrappers_cap_7200_request_to_600,PASS" in duration_cap_compliance_csv_text
        and not re.search(r",FAIL,", duration_cap_compliance_csv_text)
    )
    safe_wrapper_guard_ok = (
        safe_wrapper_guard_md.exists()
        and safe_wrapper_guard_json.exists()
        and safe_wrapper_guard_csv.exists()
        and "RF_COMM_SAFE_WRAPPER_GUARD_CONTRACT overall=PASS_SAFE_WRAPPER_GUARDS guards=25 failures=0" in safe_wrapper_guard_text
        and "NO_HARDWARE_PROGRAMMING=1" in safe_wrapper_guard_text
        and "NO_UART_WRITE=1" in safe_wrapper_guard_text
        and "NO_TFDU_DRIVE=1" in safe_wrapper_guard_text
        and "WRAPPER_EXECUTION_DONE_BY_THIS_CHECK=0" in safe_wrapper_guard_text
        and "REAL_TRAFFIC_REQUIRES_ALLOW_TRAFFIC=1" in safe_wrapper_guard_text
        and "REAL_TFDU_TRAFFIC_REQUIRES_SHUTDOWN_AFTER=1" in safe_wrapper_guard_text
        and "EIGHT_LANE_REQUIRES_SHUTDOWN_BEFORE_AFTER_AND_REVIEW=1" in safe_wrapper_guard_text
        and "CURRENT_NO_ETHERNET_EXECUTES_ZERO_WRAPPERS=1" in safe_wrapper_guard_text
        and '"overall": "PASS_SAFE_WRAPPER_GUARDS"' in safe_wrapper_guard_json_text
        and '"guards": 25' in safe_wrapper_guard_json_text
        and '"failures": 0' in safe_wrapper_guard_json_text
        and '"wrapper_execution_done_by_this_check": false' in safe_wrapper_guard_json_text
        and '"real_traffic_requires_allow_traffic": true' in safe_wrapper_guard_json_text
        and '"real_tfdu_traffic_requires_shutdown_after": true' in safe_wrapper_guard_json_text
        and '"eight_lane_requires_shutdown_before_after_and_review": true' in safe_wrapper_guard_json_text
        and '"current_no_ethernet_executes_zero_wrappers": true' in safe_wrapper_guard_json_text
        and "N03,network_only_no_tfdu_or_fpga,PASS" in safe_wrapper_guard_csv_text
        and "N04,two_ax7010_real_traffic_guard,PASS" in safe_wrapper_guard_csv_text
        and "N04,two_ax7010_requires_physical_matrix_gate,PASS" in safe_wrapper_guard_csv_text
        and "A01,product_loop_real_traffic_guard,PASS" in safe_wrapper_guard_csv_text
        and "A01,product_loop_requires_physical_matrix_gate,PASS" in safe_wrapper_guard_csv_text
        and "S05,rotating_shaft_fixture_and_shutdown_guard,PASS" in safe_wrapper_guard_csv_text
        and "S05,rotating_shaft_requires_physical_matrix_gate,PASS" in safe_wrapper_guard_csv_text
        and "A02,eightlane_review_shutdown_and_pinmap_guard,PASS" in safe_wrapper_guard_csv_text
        and "A02,eightlane_requires_physical_matrix_gate,PASS" in safe_wrapper_guard_csv_text
        and "GLOBAL,physical_matrix_gate_script_blocks_required_link_failures,PASS" in safe_wrapper_guard_csv_text
        and "GLOBAL,physical_matrix_gate_selftest_passes,PASS" in safe_wrapper_guard_csv_text
        and "SEQUENCE,current_no_ethernet_executes_zero_wrappers,PASS" in safe_wrapper_guard_csv_text
        and "P1,lane_mapping_parent_timeout_emergency_shutdown,PASS" in safe_wrapper_guard_csv_text
        and "P1,two_lane_matrix_timeout_and_shutdown_after_each_run,PASS" in safe_wrapper_guard_csv_text
        and "P1,prearmed_single_run_finally_shutdown,PASS" in safe_wrapper_guard_csv_text
        and "P1,latest_p1_dryrun_no_hardware,PASS" in safe_wrapper_guard_csv_text
        and "P1,failed_link_retest_requires_allow_traffic_for_real_hardware,PASS" in safe_wrapper_guard_csv_text
        and "P1,repeat_physical_failure_guard_is_read_only_and_blocks_stale_retests,PASS" in safe_wrapper_guard_csv_text
        and "P1,latest_repeat_failure_guard_blocks_without_hardware,PASS" in safe_wrapper_guard_csv_text
        and "P1,latest_failed_link_retest_dryrun_no_hardware,PASS" in safe_wrapper_guard_csv_text
        and "DRYRUN,latest_wrapper_dryruns_are_no_tfdu,PASS" in safe_wrapper_guard_csv_text
        and "READINESS,readiness_and_promotion_preserve_blockers,PASS" in safe_wrapper_guard_csv_text
        and "DURATION,duration_cap_gate_still_passes,PASS" in safe_wrapper_guard_csv_text
        and not re.search(r",FAIL,", safe_wrapper_guard_csv_text)
    )
    drc_release_gate_ok = (
        drc_release_gate_md.exists()
        and drc_release_gate_json.exists()
        and drc_release_gate_csv.exists()
        and "RF_COMM_DRC_RELEASE_GATE overall=BLOCK_RELEASE_NOT_READY_DEBUG_CAN_CONTINUE release_ready=0 debug_can_continue=1 release_blocking=2 row_failures=0" in drc_release_gate_text
        and "NO_HARDWARE_PROGRAMMING=1" in drc_release_gate_text
        and "NO_UART_WRITE=1" in drc_release_gate_text
        and "NO_TFDU_DRIVE=1" in drc_release_gate_text
        and "NO_VIVADO_RUN=1" in drc_release_gate_text
        and '"overall": "BLOCK_RELEASE_NOT_READY_DEBUG_CAN_CONTINUE"' in drc_release_gate_json_text
        and '"release_ready": 0' in drc_release_gate_json_text
        and '"debug_can_continue": 1' in drc_release_gate_json_text
        and '"release_blocking_count": 2' in drc_release_gate_json_text
        and '"row_failures": 0' in drc_release_gate_json_text
        and "timing_constraint_actions_cleared_or_block_release,PASS" in drc_release_gate_csv_text
        and "dma_writefirst_review_blocks_release,PASS" in drc_release_gate_csv_text
        and "control_set_action_blocks_expansion,PASS" in drc_release_gate_csv_text
        and "release_not_ready_is_enforced,PASS" in drc_release_gate_csv_text
        and "unknown_rules_not_silently_accepted,PASS" in drc_release_gate_csv_text
        and not re.search(r",FAIL,", drc_release_gate_csv_text)
    )
    product_loop_safe_wrapper_ok = (
        product_loop_safe_wrapper.exists()
        and "$maxContinuousRunSeconds = 600" in product_loop_safe_wrapper_text
        and "[switch]$ProgramShutdownAfterRun" in product_loop_safe_wrapper_text
        and "program_shutdown_after_run_not_set" in product_loop_safe_wrapper_text
        and "PRODUCT_LOOP_REAL_ACCEPTANCE_PASS=" in product_loop_safe_wrapper_text
        and "PRODUCT_LOOP_SHUTDOWN_AFTER_RUN_PASS=" in product_loop_safe_wrapper_text
        and "PRODUCT_LOOP_DRY_RUN=1" in product_loop_dryrun_text
        and "TOPOLOGY=two_ax7010" in product_loop_dryrun_text
        and "CONTINUOUS_RUNTIME_CAP_APPLIED=1" in product_loop_dryrun_text
        and "DURATION_SECONDS_EFFECTIVE=600" in product_loop_dryrun_text
        and "NO_TX_DATA_TO_REAL_BOARDS=1" in product_loop_dryrun_text
        and "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1" in product_loop_dryrun_text
    )
    eightlane_hw_safe_wrapper_ok = (
        eightlane_hw_safe_wrapper.exists()
        and "$maxContinuousRunSeconds = 600" in eightlane_hw_safe_wrapper_text
        and "[switch]$ProgramShutdownBeforeRun" in eightlane_hw_safe_wrapper_text
        and "[switch]$ProgramShutdownAfterRun" in eightlane_hw_safe_wrapper_text
        and "reduced_8lane_frag16_external" in eightlane_hw_safe_wrapper_text
        and "reduced_8lane_frag16_raw_profile" in eightlane_hw_safe_wrapper_text
        and "full_8lane_stream_bidir_resource_blocked" in eightlane_hw_safe_wrapper_text
        and "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_PASS=" in eightlane_hw_safe_wrapper_text
        and "EIGHT_LANE_HARDWARE_SHUTDOWN_BEFORE_RUN_PASS=" in eightlane_hw_safe_wrapper_text
        and "EIGHT_LANE_HARDWARE_SHUTDOWN_AFTER_RUN_PASS=" in eightlane_hw_safe_wrapper_text
        and "EIGHT_LANE_HARDWARE_DRY_RUN=1" in eightlane_hw_dryrun_text
        and "PROFILE=reduced_8lane_frag16_external" in eightlane_hw_dryrun_text
        and "LANE_COUNT_REQUESTED=8" in eightlane_hw_dryrun_text
        and "CONTINUOUS_RUNTIME_CAP_APPLIED=1" in eightlane_hw_dryrun_text
        and "DURATION_SECONDS_EFFECTIVE=600" in eightlane_hw_dryrun_text
        and "CANDIDATE_A_LANE_COUNT=8" in eightlane_hw_dryrun_text
        and "CANDIDATE_B_LANE_COUNT=8" in eightlane_hw_dryrun_text
        and "REDUCED_8LANE_FRAG16_BITSTREAM_READY_FOR_REVIEW=1" in eightlane_hw_dryrun_text
        and "REDUCED_8LANE_FRAG16_RAW_HALF_MBPS=32.0" in eightlane_hw_dryrun_text
        and "REDUCED_8LANE_FRAG16_RAW_FDX_PER_DIR_MBPS=16.0" in eightlane_hw_dryrun_text
        and "REDUCED_8LANE_FRAG16_BITSTREAM_SHA256=F3661A68DB0F36FCAC96DE983538EA31B5AA2B50338B44A81DAB3E45999AC778" in eightlane_hw_dryrun_text
        and "CANDIDATE_PROJECT_RESOURCE_BLOCKED=1" in eightlane_hw_dryrun_text
        and "EIGHT_LANE_HARDWARE_DRY_RUN_BLOCKED_REASON_PREVIEW=ethernet_link_not_up" in eightlane_hw_dryrun_text
        and "NO_TX_DATA_TO_REAL_BOARDS=1" in eightlane_hw_dryrun_text
        and "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1" in eightlane_hw_dryrun_text
    )
    no_ethernet_network_offline_ok = (
        no_ethernet_network_summary is not None
        and no_ethernet_network_csv is not None
        and "NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS=1" in no_ethernet_network_text
        and "NO_ETHERNET_NETWORK_OFFLINE_PASS_COUNT=11" in no_ethernet_network_text
        and "NO_ETHERNET_NETWORK_OFFLINE_FAIL_COUNT=0" in no_ethernet_network_text
        and "NO_HARDWARE_PROGRAMMING=1" in no_ethernet_network_text
        and "NO_UART_WRITE=1" in no_ethernet_network_text
        and "NO_TFDU_DRIVE=1" in no_ethernet_network_text
        and "NO_REAL_BOARD_TCP_DHCP=1" in no_ethernet_network_text
        and "NO_REAL_TWO_AX7010_TRAFFIC=1" in no_ethernet_network_text
        and "CONSTRAINT_UNCHANGED=1" in no_ethernet_network_text
        and "ps_bridge_static" in no_ethernet_network_csv_text
        and "host_client_unittest" in no_ethernet_network_csv_text
        and "host_offline_mock_acceptance" in no_ethernet_network_csv_text
        and "two_ax7010_direct_offline_model" in no_ethernet_network_csv_text
        and "fdx_a_to_b_tx_lane_coverage=0x0f" in no_ethernet_network_text
        and "fdx_b_to_a_tx_lane_coverage=0xf0" in no_ethernet_network_text
        and "hdx_tx_lane_coverage=0xff" in no_ethernet_network_text
        and "hdx_rx_lane_coverage=0xff" in no_ethernet_network_text
        and "network_fault_recovery_model" in no_ethernet_network_csv_text
        and "tcp_reset_reconnect" in no_ethernet_network_text
        and "dhcp_timeout_static_fallback" in no_ethernet_network_text
        and "queued_rx_after_reconnect" in no_ethernet_network_text
        and "board_tcp_safe_dry_run" in no_ethernet_network_csv_text
        and "two_ax7010_safe_wrapper_offline_model" in no_ethernet_network_csv_text
        and "two_ax7010_safe_wrapper_dry_run_cap" in no_ethernet_network_csv_text
        and "rotating_shaft_safe_wrapper_dry_run_cap" in no_ethernet_network_csv_text
        and "product_loop_safe_wrapper_dry_run_cap" in no_ethernet_network_csv_text
        and "eight_lane_hardware_safe_wrapper_dry_run_cap" in no_ethernet_network_csv_text
        and "PROFILE=reduced_8lane_frag16_external" in no_ethernet_network_csv_text
        and "REDUCED_8LANE_FRAG16_BITSTREAM_READY_FOR_REVIEW=1" in no_ethernet_network_csv_text
        and "REDUCED_8LANE_FRAG16_RAW_HALF_MBPS=32.0" in no_ethernet_network_csv_text
        and "REDUCED_8LANE_FRAG16_RAW_FDX_PER_DIR_MBPS=16.0" in no_ethernet_network_csv_text
        and "EIGHT_LANE_HARDWARE_DRY_RUN_BLOCKED_REASON_PREVIEW=ethernet_link_not_up" in no_ethernet_network_csv_text
        and not re.search(r",FAIL,", no_ethernet_network_csv_text)
    )
    host_status_snapshot_ok = (
        host_status_snapshot_md.exists()
        and host_status_snapshot_json.exists()
        and host_status_snapshot_csv.exists()
        and "- Overall: `PASS`" in host_status_snapshot_text
        and "OFFLINE_HOST_VIEW_NOT_REAL_BOARD_TCP" in host_status_snapshot_text
        and "No hardware programming: `1`" in host_status_snapshot_text
        and "No UART write: `1`" in host_status_snapshot_text
        and "No TFDU drive: `1`" in host_status_snapshot_text
        and "`device_connection_state`" in host_status_snapshot_text
        and "`network_state`" in host_status_snapshot_text
        and "REAL_BOARD_TCP_DHCP_DEFERRED_NO_ETHERNET" in host_status_snapshot_text
        and "`tx_packets`" in host_status_snapshot_text
        and "`rx_packets`" in host_status_snapshot_text
        and "`error_frames`" in host_status_snapshot_text
        and "`pending_frames`" in host_status_snapshot_text
        and "`rtt_avg_ms`" in host_status_snapshot_text
        and "`hdx_tx_lane_coverage`" in host_status_snapshot_text
        and "`0xff`" in host_status_snapshot_text
        and "`fdx_a_to_b_tx_lane_coverage`" in host_status_snapshot_text
        and "`0x0f`" in host_status_snapshot_text
        and "`fdx_b_to_a_tx_lane_coverage`" in host_status_snapshot_text
        and "`0xf0`" in host_status_snapshot_text
        and '"overall": "PASS"' in host_status_snapshot_json_text
        and '"display_fields_ok": true' in host_status_snapshot_json_text
        and '"no_hardware_action": true' in host_status_snapshot_json_text
        and "verdict,overall,PASS" in host_status_snapshot_csv_text
        and "display,device_connection_state,OFFLINE_MOCK_CONNECTED" in host_status_snapshot_csv_text
        and "display,network_state,REAL_BOARD_TCP_DHCP_DEFERRED_NO_ETHERNET" in host_status_snapshot_csv_text
        and "display,error_frames,0" in host_status_snapshot_csv_text
        and "display,pending_frames,0" in host_status_snapshot_csv_text
    )
    no_ethernet_network_boundary_ok = (
        no_ethernet_network_boundary_md.exists()
        and no_ethernet_network_boundary_json.exists()
        and no_ethernet_network_boundary_csv.exists()
        and "RF_COMM_NO_ETHERNET_NETWORK_BOUNDARY_EVIDENCE overall=PASS_OFFLINE_NETWORK_BOUNDARY checks=8" in no_ethernet_network_boundary_text
        and "NO_HARDWARE_PROGRAMMING=1" in no_ethernet_network_boundary_text
        and "NO_UART_WRITE=1" in no_ethernet_network_boundary_text
        and "NO_TFDU_DRIVE=1" in no_ethernet_network_boundary_text
        and "NO_REAL_BOARD_TCP_DHCP=1" in no_ethernet_network_boundary_text
        and "NO_REAL_ETHERNET_LINK_REQUIRED=1" in no_ethernet_network_boundary_text
        and "CONSTRAINT_UNCHANGED=1" in no_ethernet_network_boundary_text
        and "TCP_SEGMENTATION_CASES=fragmented_outgoing;coalesced_ack_rx" in no_ethernet_network_boundary_text
        and "NEGATIVE_CASES=missing_ack_timeout;tx_error;oversize_rejected;protocol_desync" in no_ethernet_network_boundary_text
        and "RECONNECT_RECOVERY=1" in no_ethernet_network_boundary_text
        and "FDX_4PLUS4_CONFIG=1" in no_ethernet_network_boundary_text
        and '"overall": "PASS_OFFLINE_NETWORK_BOUNDARY"' in no_ethernet_network_boundary_json_text
        and '"real_board_tcp_dhcp_acceptance": false' in no_ethernet_network_boundary_json_text
        and "fragmented_and_coalesced_tcp_frames,PASS" in no_ethernet_network_boundary_csv_text
        and "missing_tx_ack_timeout_detected,PASS" in no_ethernet_network_boundary_csv_text
        and "tx_error_reports_failed_data,PASS" in no_ethernet_network_boundary_csv_text
        and "oversize_payload_rejected_before_send,PASS" in no_ethernet_network_boundary_csv_text
        and "payload_exchange_after_reconnect,PASS" in no_ethernet_network_boundary_csv_text
        and "fdx_4plus4_config_status_masks,PASS" in no_ethernet_network_boundary_csv_text
        and "protocol_desync_reports_explicit_details,PASS" in no_ethernet_network_boundary_csv_text
        and "no_real_board_boundary,PASS" in no_ethernet_network_boundary_csv_text
        and not re.search(r",FAIL,", no_ethernet_network_boundary_csv_text)
    )

    items = [
        AuditItem(
            "HARD-CONSTRAINT",
            "Root project constraint file remains unchanged.",
            "PASS" if constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL",
            rel(constraint),
            f"sha256={sha256(constraint)}",
        ),
        AuditItem(
            "TARGET-CONSISTENCY",
            "Target wording, lane count, raw PHY capacity, and effective-payload reachability are checked together.",
            "PASS_BOUNDARY_DOCUMENTED" if target_consistency_boundary else "MISSING",
            rel(target_consistency_md),
            "Consistency check documents that 32/16 Mbit/s is internally consistent as raw PHY capacity, while effective payload remains below that boundary."
            if target_consistency_boundary
            else "Missing target consistency check evidence.",
        ),
        AuditItem(
            "TARGET-ACCEPTANCE-MATRIX",
            "The hard target is decomposed into requirement-level acceptance rows with explicit evidence and remaining blockers.",
            "PASS_INCOMPLETE_TRACKED" if target_matrix_ok else "MISSING",
            rel(target_matrix_md),
            "Matrix tracks 36 requirements and correctly leaves only no-Ethernet/real-hardware/product-acceptance rows incomplete."
            if target_matrix_ok
            else "Missing or stale requirement-level target acceptance matrix.",
        ),
        AuditItem(
            "TOPOLOGY-CAPACITY-PLAN",
            "Final raw 32/16 Mbit/s lane arithmetic is mapped against current XC7Z010 hardware profiles so offline raw-target progress is not mistaken for product acceptance.",
            "PASS_GAP_CLASSIFIED" if topology_capacity_ok else "MISSING",
            rel(topology_capacity_md),
            "Plan classifies the reduced 8-lane fragment=16 external candidate as the strongest current offline bitstream-ready raw-target profile, while keeping effective payload, network, TFDU hardware, and rotating-shaft acceptance open."
            if topology_capacity_ok
            else "Missing or stale topology capacity classification.",
        ),
        AuditItem(
            "REMAINING-HARDWARE-ACCEPTANCE-PLAN",
            "The remaining no-Ethernet and real-hardware gaps have explicit preconditions, safe commands, pass criteria, evidence patterns, shutdown requirements, and implementation gaps.",
            "PASS_READY_PLAN" if remaining_hw_plan_ok else "MISSING",
            rel(remaining_hw_plan_md),
            "Plan covers N03/N04/S05/A01/A02, preserves the current no-Ethernet blocker, enforces the 600 s continuous-run cap, and records the current 8-lane XDC/pinmap gap."
            if remaining_hw_plan_ok
            else "Missing or stale remaining hardware acceptance plan.",
        ),
        AuditItem(
            "REMAINING-ACCEPTANCE-READINESS-GATE",
            "The five remaining real-acceptance items have a current read-only READY/BLOCKED gate tied to external preconditions, wrappers, templates, shutdown requirements, exact evidence needed, and per-item unlock actions.",
            "PASS_BLOCKERS_CLASSIFIED" if remaining_acceptance_readiness_ok else "MISSING",
            rel(remaining_acceptance_readiness_md),
            "Gate classifies all remaining items as blocked only by external preconditions and records the current no-Ethernet-cable condition as unavailable and not changeable now. It also records explicit start_when/unlock_action/safety_requirement fields: N03 needs Ethernet/single-board TCP; N04/A01 need Ethernet/two-AX7010 TCP; S05 additionally needs a real 20 cm/600 rpm fixture log; A02 additionally needs pinmap/shutdown review and real 8-lane TFDU wiring validation. It executed no real acceptance, programmed no hardware, wrote no UART, and drove no TFDU."
            if remaining_acceptance_readiness_ok
            else "Missing or stale remaining real-acceptance readiness gate.",
        ),
        AuditItem(
            "EIGHT-LANE-HARDWARE-READINESS",
            "The real 8-lane hardware path has a static readiness report that separates script support, active XDC coverage, draft TODO pins, shutdown coverage, and no-hardware-action safety.",
            "PASS_BLOCKERS_IDENTIFIED" if eightlane_readiness_ok else "MISSING",
            rel(eightlane_readiness_md),
            "Readiness report shows the hardware script now allows 8 lanes, complete A/B and A-only external candidate XDCs exist, candidate shutdown coverage is ready for review, the candidate shutdown bitstream is built, and both 8-lane hardware profiles are resource-blocked on XC7Z010; no hardware was programmed or driven."
            if eightlane_readiness_ok
            else "Missing or stale 8-lane hardware readiness report.",
        ),
        AuditItem(
            "EIGHT-LANE-SHUTDOWN-BITSTREAM",
            "The generated 8-lane shutdown candidate has an offline Vivado bitstream build with DRC, timing, IO, utilization, and log evidence before any future physical 8-lane TFDU run.",
            "PASS_CANDIDATE_REVIEW_REQUIRED" if eightlane_shutdown_build_ok else "MISSING",
            rel(eightlane_shutdown_build_md),
            "Candidate shutdown bitstream exists with 0 errors, 0 critical warnings, one known ZPS7-1 pure-PL Zynq warning, and no hardware programming/UART/TFDU drive."
            if eightlane_shutdown_build_ok
            else "Missing or stale 8-lane shutdown bitstream build report.",
        ),
        AuditItem(
            "EIGHT-LANE-CANDIDATE-PROJECT-BUILD",
            "The full 8-lane stream_bidir candidate hardware project is built far enough to classify implementation feasibility on XC7Z010.",
            "SYNTH_PASS_IMPL_RESOURCE_BLOCKED" if eightlane_candidate_project_ok else "MISSING",
            rel(eightlane_candidate_project_md),
            "8-lane candidate reaches synthesis, but implementation is blocked by LUT over-utilization on XC7Z010: 21125 required vs 17600 available; no hardware programming/UART/TFDU drive occurred."
            if eightlane_candidate_project_ok
            else "Missing or stale 8-lane candidate project build classification.",
        ),
        AuditItem(
            "EIGHT-LANE-EXTERNAL-PROJECT-BUILD",
            "The 8-lane A-only external candidate hardware project is built far enough to classify one side of the final two-AX7010 topology on XC7Z010.",
            "SYNTH_PASS_IMPL_RESOURCE_BLOCKED" if eightlane_external_project_ok else "MISSING",
            rel(eightlane_external_project_md),
            "8-lane A-only external candidate reaches synthesis, but implementation is blocked by XC7Z010 resource over-utilization: FDRE 52477/35500, Slice LUTs 45050/17600, Slice Registers 53287/35200; no hardware programming/UART/TFDU drive occurred and Ethernet acceptance remains deferred."
            if eightlane_external_project_ok
            else "Missing or stale 8-lane A-only external project build classification.",
        ),
        AuditItem(
            "EXTERNAL-LANE-RESOURCE-SCAN",
            "The A-only external profile is scanned from 1 to 8 lanes to identify the largest placement-feasible XC7Z010 lane count.",
            "PLACE_PASS_ONLY_1LANE" if external_lane_scan_ok else "MISSING",
            rel(external_lane_scan_md),
            "External A-only profile reaches place_design at 1 lane only; lane 2 through lane 8 are resource-blocked. The scan restored the active project and did not program hardware, write UART, or drive TFDU."
            if external_lane_scan_ok
            else "Missing or stale external A-only lane-count resource scan.",
        ),
        AuditItem(
            "EXTERNAL-RESOURCE-OPTION-SCAN",
            "A reduced-resource A-only external option is scanned to test whether 2 lanes can become placement-feasible on XC7Z010.",
            "PASS_REDUCED_2LANE_PLACE" if external_option_scan_ok else "MISSING",
            rel(external_option_scan_md),
            "Reduced external 2-lane profile reaches place_design with fragment=64 and TX/RX async FIFOs=128. This is a resource-reduction direction only, not route/timing/bitstream/TCP-DHCP/hardware acceptance."
            if external_option_scan_ok
            else "Missing or stale reduced-resource external option scan.",
        ),
        AuditItem(
            "EXTERNAL-REDUCED-1TO4LANE-SCAN",
            "The reduced-resource A-only external profile is scanned from 1 to 4 lanes to check placement-feasible expansion headroom on XC7Z010.",
            "PASS_REDUCED_UP_TO_4LANE_PLACE" if external_reduced_lane_scan_ok else "MISSING",
            rel(external_reduced_lane_scan_md),
            "Reduced external profile reaches place_design for 1, 2, 3, and 4 lanes with fragment=64 and TX/RX async FIFOs=128; this is offline place/resource evidence only, not route/timing/bitstream/TCP-DHCP/two-AX7010/TFDU hardware acceptance."
            if external_reduced_lane_scan_ok
            else "Missing or stale reduced-resource 1..4 lane external scan.",
        ),
        AuditItem(
            "EXTERNAL-REDUCED-5TO8-BOUNDARY",
            "The reduced-resource A-only external profile is checked beyond 4 lanes to prove the first XC7Z010 resource boundary before treating 4 lanes as the current endpoint.",
            "PASS_FIRST_BLOCKED_5LANE" if external_reduced_5to8_ok else "MISSING",
            rel(external_reduced_5to8_md),
            "Reduced external 5..8 extension establishes lane 5 as the first blocked reduced-profile count: LUT 17801/17600, slices 3869/3845, control sets 1274. Lane 6 was stopped after no progress because lane 5 already proved the boundary; the project was restored and no hardware was programmed."
            if external_reduced_5to8_ok
            else "Missing or stale reduced-resource 5..8 lane extension boundary report.",
        ),
        AuditItem(
            "EXTERNAL-REDUCED-5LANE-FRAG32",
            "A smaller-packet reduced A-only external 5-lane profile is checked to prove whether the 5-lane resource boundary can be moved by frame/cache sizing.",
            "PASS_PLACE_5LANE_FRAG32" if external_reduced_5lane_frag32_ok else "MISSING",
            rel(external_reduced_5lane_frag32_md),
            "Reduced external 5-lane fragment=32 profile reaches place_design offline with LUT 10697/17600, registers 14001/35200, BRAM 4.5/60, and 918 control sets; no hardware was programmed and Ethernet remains unavailable."
            if external_reduced_5lane_frag32_ok
            else "Missing or stale reduced 5-lane fragment=32 place report.",
        ),
        AuditItem(
            "EXTERNAL-REDUCED-5LANE-FRAG32-ROUTE",
            "The smaller-packet reduced A-only external 5-lane profile routes and meets timing offline on XC7Z010.",
            "PASS_ROUTE_TIMING_5LANE_FRAG32" if external_reduced_5lane_frag32_route_ok else "MISSING",
            rel(external_reduced_5lane_frag32_route_md),
            "Reduced external 5-lane fragment=32 profile reaches route_design with WNS=1.571 ns, WHS=0.012 ns, routing_errors=0, and no critical/error DRC rows. This remains offline evidence only because the candidate bitstream has not been programmed and Ethernet is absent."
            if external_reduced_5lane_frag32_route_ok
            else "Missing or stale reduced 5-lane fragment=32 route/timing report.",
        ),
        AuditItem(
            "EXTERNAL-REDUCED-5LANE-FRAG32-BITSTREAM",
            "The smaller-packet reduced A-only external 5-lane profile produces an offline candidate bitstream for later manual review.",
            "PASS_OFFLINE_5LANE_FRAG32_BITSTREAM_READY_REVIEW_REQUIRED" if external_reduced_5lane_frag32_bitstream_ok else "MISSING",
            rel(external_reduced_5lane_frag32_bitstream_md),
            "Reduced external 5-lane fragment=32 candidate bitstream exists, sha256=64213BD459D5CF8E6A487DC601D8942F1D938858AFAE5039CBB46FF3A39A903E, WNS=1.571 ns, WHS=0.012 ns, routing_errors=0, no critical warnings/errors. It has not been programmed and remains review-required."
            if external_reduced_5lane_frag32_bitstream_ok
            else "Missing or stale reduced 5-lane fragment=32 candidate bitstream report.",
        ),
        AuditItem(
            "EXTERNAL-REDUCED-8LANE-FRAG16-BITSTREAM",
            "The smaller-packet reduced A-only external 8-lane profile produces an offline candidate bitstream at the final raw 32/16 Mbit/s lane capacity.",
            "PASS_OFFLINE_8LANE_FRAG16_BITSTREAM_READY_REVIEW_REQUIRED" if external_reduced_8lane_frag16_bitstream_ok else "MISSING",
            rel(external_reduced_8lane_frag16_bitstream_md),
            "Reduced external 8-lane fragment=16 candidate bitstream exists, sha256=F3661A68DB0F36FCAC96DE983538EA31B5AA2B50338B44A81DAB3E45999AC778, WNS=1.153 ns, WHS=0.009 ns, routing_errors=0, raw_half=32 Mbit/s, raw_fdx_per_dir=16 Mbit/s, no critical warnings/errors. It has not been programmed and remains review-required."
            if external_reduced_8lane_frag16_bitstream_ok
            else "Missing or stale reduced 8-lane fragment=16 candidate bitstream report.",
        ),
        AuditItem(
            "EXTERNAL-REDUCED-2LANE-ROUTE",
            "The reduced-resource A-only external 2-lane profile routes and meets timing offline on XC7Z010.",
            "PASS_ROUTE_TIMING_REDUCED_2LANE" if external_reduced_route_ok else "MISSING",
            rel(external_reduced_route_md),
            "Reduced external 2-lane profile reaches route_design with WNS=1.58 ns, WHS=0.017 ns, routing_errors=0, and no critical DRC rows. This remains offline evidence only because no bitstream was programmed and Ethernet is absent."
            if external_reduced_route_ok
            else "Missing or stale reduced external 2-lane route/timing report.",
        ),
        AuditItem(
            "EXTERNAL-REDUCED-4LANE-ROUTE",
            "The reduced-resource A-only external 4-lane profile routes and meets timing offline on XC7Z010.",
            "PASS_ROUTE_TIMING_REDUCED_4LANE" if external_reduced_4lane_route_ok else "MISSING",
            rel(external_reduced_4lane_route_md),
            "Reduced external 4-lane profile reaches route_design with WNS=1.317 ns, WHS=0.017 ns, routing_errors=0, no critical DRC rows, and LUT utilization 14028/17600. This remains offline evidence only because no bitstream was programmed and Ethernet is absent."
            if external_reduced_4lane_route_ok
            else "Missing or stale reduced external 4-lane route/timing report.",
        ),
        AuditItem(
            "EXTERNAL-REDUCED-4LANE-BITSTREAM",
            "The reduced-resource A-only external 4-lane profile produces an offline candidate bitstream for later manual review.",
            "PASS_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED" if external_reduced_4lane_bitstream_ok else "MISSING",
            rel(external_reduced_4lane_bitstream_md),
            "Reduced external 4-lane candidate bitstream exists, sha256=BDDE1CE8416E05EBAD8BF24FF96FEC04419CC3C7C35841CBB3ED825425714779, WNS=1.317 ns, WHS=0.017 ns, routing_errors=0, no critical warnings/errors. It has not been programmed and remains review-required."
            if external_reduced_4lane_bitstream_ok
            else "Missing or stale reduced external 4-lane candidate bitstream report.",
        ),
        AuditItem(
            "EXTERNAL-REDUCED-4LANE-BRINGUP-PLAN",
            "The reduced-resource A-only external 4-lane candidate has a safety-bounded ILA/bring-up plan before any future hardware programming.",
            "READY_FOR_MANUAL_REVIEW_NO_HARDWARE_RUN" if external_reduced_4lane_bringup_ok else "MISSING",
            rel(external_reduced_4lane_bringup_md),
            "Bring-up plan records the 4-lane pin matrix, passive ILA probe matrix, shutdown-before/after rule, 600 s cap, no static diagnostic waveform rule, and current no-Ethernet boundary; no hardware was programmed."
            if external_reduced_4lane_bringup_ok
            else "Missing or stale reduced external 4-lane bring-up plan.",
        ),
        AuditItem(
            "G1-SINGLE-LANE-MVP",
            "Single-lane G1 MVP passes under the active capped 10-minute runtime rule.",
            "PASS" if g1_capped_pass else "MISSING",
            rel(g1_report),
            "G1 capped soak evidence includes sent=rx_ok=267892, tx_fail=0, and shutdown after 582.2 s."
            if g1_capped_pass
            else "Missing current G1 capped acceptance evidence.",
        ),
        AuditItem(
            "POST-G1-SIM-GATE",
            "Post-G1 simulation/offline regression gate runs and all cases pass.",
            "PASS" if post_gate_pass else "FAIL",
            rel(post_summary),
            f"{post_gate_pass_count}/{(post_gate_pass_count or 0) + (post_gate_fail_count or 0)} post-G1 cases pass."
            if post_gate_pass
            else "Post-G1 gate did not pass cleanly.",
        ),
        AuditItem(
            "RAW-PHY-RATE",
            "Raw PHY capacity supports 4 Mbit/s per lane, 32 Mbit/s 8-lane half-duplex, and 16 Mbit/s per direction 4+4 full-duplex.",
            "PASS_SIM_RAW_ONLY" if phy_rate_pass else "MISSING",
            rel(post_summary),
            "Simulation model passes: 64 MHz, 4992-cycle frame busy window, raw capacity targets match."
            if phy_rate_pass
            else "Missing raw PHY capacity evidence.",
        ),
        AuditItem(
            "PAYLOAD-THROUGHPUT",
            "Effective payload/end-to-end throughput reaches the final 32 Mbit/s half-duplex and 16 Mbit/s per-direction full-duplex target if that target is interpreted above raw PHY.",
            "BOUNDARY_PROVED_RAW_ONLY" if effective_payload_missing and rate_boundary_proof_pass else ("NOT_MET_CURRENT_FORMAT" if effective_payload_missing else ("PASS" if real_payload_throughput_evidence else "MISSING")),
            rel(post_summary),
            "A separate rate-boundary proof shows the 32/16 Mbit/s target can only be claimed as raw PHY capacity under the current 8 x 4 Mbit/s physical budget; effective payload remains reported separately."
            if effective_payload_missing and rate_boundary_proof_pass
            else f"Current optimistic no-ACK payload upper bounds are half={half_payload_upper} Mbit/s, fdx={fdx_payload_upper} Mbit/s; this is below final payload-rate targets."
            if effective_payload_missing
            else "No current effective payload/end-to-end throughput evidence found.",
        ),
        AuditItem(
            "RATE-BOUNDARY-PROOF",
            "32/16 Mbit/s is classified as raw PHY capacity for the current target, while effective payload is bounded below raw capacity.",
            "PASS_BOUNDARY_PROOF" if rate_boundary_proof_pass else "MISSING",
            rel(rate_boundary_md),
            "Proof passes: current 8 x 4 Mbit/s raw budget reaches 32/16 only as raw PHY; current reliable payload models require 9 half-duplex lanes or 5 lanes per direction to hit 32/16 as payload."
            if rate_boundary_proof_pass
            else "Missing rate boundary proof evidence.",
        ),
        AuditItem(
            "PAYLOAD-RATE-OPTIONS",
            "Effective payload design-space exploration documents what the current PHY and framing can support.",
            "PASS_MODEL" if rate_options_pass else "MISSING",
            rel(rate_options_md),
            (
                f"Best packet-ACK sweep result is half={best_half_packet_ack} Mbit/s and fdx={best_fdx_packet_ack} Mbit/s; "
                f"{packet_ack_meets_16_8} options meet 16/8, {packet_ack_meets_32_16} options meet 32/16."
            )
            if rate_options_pass
            else "Missing effective payload rate option model.",
        ),
        AuditItem(
            "PAYLOAD-GAP-CLOSURE",
            "The remaining gap between current effective payload and the 32/16 raw target is quantified with explicit closure conditions.",
            "PASS_RAW_ONLY_GAP_CLASSIFIED" if payload_gap_closure_pass else "MISSING",
            rel(payload_gap_closure_md),
            "Gap-closure model records current packet-ACK payload 28.966/14.483 Mbit/s, gap 3.034/1.517 Mbit/s, required raw lane rate about 4.419 Mbit/s, or 9 half-duplex lanes / 5 lanes per direction if 32/16 is reinterpreted as effective payload."
            if payload_gap_closure_pass
            else "Missing payload gap-closure model evidence.",
        ),
        AuditItem(
            "MULTI-LANE-DIGITAL",
            "Multi-lane digital expansion, 8-lane packet loopback, 8-lane max-fragment loopback, 8-lane autoroute, 4+4 full-duplex partition, failover/degradation, route changes, and full-duplex lane partition pass simulation.",
            "PASS_SIM_8LANE_INCLUDED" if multi_sim_pass else "MISSING",
            rel(post_csv),
            "4-lane stream, 4-lane packet loopback, 8-lane packet loopback, 8-lane max-fragment loopback, 8-lane autoroute, 4+4 full-duplex, impair, degrade, route, autoroute, and fdx cases pass."
            if multi_sim_pass
            else "Missing multi-lane simulation coverage.",
        ),
        AuditItem(
            "EIGHT-LANE-DIGITAL-SIM",
            "8-lane digital packet loopback uses all eight lanes concurrently.",
            "PASS_SIM_8LANE" if eight_lane_sim_pass else "MISSING",
            rel(post_summary),
            "multi_8lane passes with max_busy_lanes=8, max_inflight_frags=8, and 512 bytes delivered."
            if eight_lane_sim_pass
            else "Missing 8-lane digital loopback evidence.",
        ),
        AuditItem(
            "EIGHT-LANE-MAX-FRAGMENT-SIM",
            "8-lane RTL packet loopback works at the current 255-byte protocol fragment limit.",
            "PASS_SIM_8LANE_MAX_FRAGMENT" if max_fragment_8lane_sim_pass else "MISSING",
            rel(post_summary),
            "max_fragment_8lane passes with payload_bytes=2040, fragment_bytes=255, max_busy_lanes=8, and max_inflight_frags=8."
            if max_fragment_8lane_sim_pass
            else "Missing 8-lane max-fragment RTL evidence.",
        ),
        AuditItem(
            "EIGHT-LANE-AUTOROUTE-SIM",
            "8-lane automatic route finding covers changing TX/RX correspondence and every source lane.",
            "PASS_SIM_8LANE_AUTOROUTE" if eight_lane_autoroute_sim_pass else "MISSING",
            rel(post_summary),
            "autoroute_8lane passes with good_src_coverage=11111111 and tx_attempt_coverage=11111111."
            if eight_lane_autoroute_sim_pass
            else "Missing 8-lane autoroute evidence.",
        ),
        AuditItem(
            "FULL-DUPLEX-4PLUS4-SIM",
            "8-lane full-duplex digital partition uses four lanes per direction concurrently.",
            "PASS_SIM_4PLUS4" if fdx_4plus4_sim_pass else "MISSING",
            rel(post_summary),
            "fdx_4plus4 passes with max_a_busy=4, max_b_busy=4, max_total_busy=8, and 512 bytes delivered per direction."
            if fdx_4plus4_sim_pass
            else "Missing 4+4 full-duplex digital partition evidence.",
        ),
        AuditItem(
            "TWO-LANE-PERF-SIM",
            "2-lane bidirectional/asymmetric stream performance is covered by simulation.",
            "PASS_SIM" if two_lane_perf_pass else "MISSING",
            rel(post_csv),
            "2-lane B0 bidirectional and asymmetric parallel performance cases pass."
            if two_lane_perf_pass
            else "Missing 2-lane performance simulation evidence.",
        ),
        AuditItem(
            "ROTATING-AUTOROUTE-SIM",
            "Rotating-side automatic route finding is covered for changing correspondence and 20 cm / 600 rpm metadata.",
            "PASS_SIM" if rotating_stress_pass else "MISSING",
            rel(post_summary),
            "Rotating autoroute stress passes with rpm=600 and shaft_diameter_mm=200."
            if rotating_stress_pass
            else "Missing rotating autoroute stress evidence.",
        ),
        AuditItem(
            "ROTATING-2H-MODEL",
            "2-hour rotating autoroute model covers the target 7200 s / 72000 rotations / 288000 sector changes.",
            "PASS_MODEL_ONLY" if rotating_model_pass else "MISSING",
            rel(post_summary),
            "Model passes and includes ACK loss/retry coverage; this is not physical shaft evidence."
            if rotating_model_pass
            else "Missing 2-hour rotating model evidence.",
        ),
        AuditItem(
            "ROTATING-8LANE-CAPPED-MODEL",
            "8-lane rotating-side automatic route finding is covered under the active 10-minute continuous-test cap.",
            "PASS_MODEL_CAPPED_10MIN" if rotating_8lane_model_pass else "MISSING",
            rel(post_summary),
            "Model passes with lane_count=8, runtime_cap_seconds=600, rotations=6000, sectors=48000, and all lane coverage."
            if rotating_8lane_model_pass
            else "Missing 8-lane capped rotating autoroute model evidence.",
        ),
        AuditItem(
            "ROTATING-AUTOROUTE-OFFLINE-EVIDENCE",
            "A consolidated no-hardware report ties together rotating autoroute stress, 8-lane autoroute, capped rotating model, two-hour model, two-AX7010 offline routing, and network fault recovery.",
            "PASS_OFFLINE_NOT_HARDWARE" if rotating_autoroute_offline_evidence_pass else "MISSING",
            rel(rotating_autoroute_offline_md),
            "Offline evidence is consolidated and explicitly records no FPGA programming, no UART write, no TFDU drive, and REAL_ROTATING_SHAFT_ACCEPTANCE=0."
            if rotating_autoroute_offline_evidence_pass
            else "Missing consolidated rotating autoroute offline evidence.",
        ),
        AuditItem(
            "PS-PC-OFFLINE",
            "PS-to-PC protocol path has offline TCP/DHCP/reconnect coverage.",
            "PASS_OFFLINE_ONLY" if pc_offline_pass else "MISSING",
            rel(post_summary),
            "Static checks, host tests, offline mock traffic, and reconnect cycles pass."
            if pc_offline_pass
            else "Missing PC/PS offline coverage.",
        ),
        AuditItem(
            "PS-PC-PROTOCOL-ROBUSTNESS",
            "PC/PS RFCM handling gives explicit diagnostics for malformed protocol input and preserves reconnect/mock traffic coverage offline.",
            "PASS_OFFLINE_ROBUSTNESS" if ps_pc_protocol_robustness_ok else "MISSING",
            rel(ps_pc_offline_summary),
            "Latest PC/PS offline gate passes 64 PS static checks, 21 host unit tests, 64 x 256-byte mock traffic with clean log acceptance, and 4 reconnect cycles; source checks cover PS bad-magic/unsupported-version errors, while host tests cover ProtocolError diagnostics for bad magic/version/oversize payload and malformed status payload lengths."
            if ps_pc_protocol_robustness_ok
            else "Missing current PC/PS robustness evidence.",
        ),
        AuditItem(
            "NO-ETHERNET-NETWORK-OFFLINE",
            "Under the current no-Ethernet condition, network-related PS/PC and two-AX7010 acceptance evidence is reproducible offline without programming hardware, writing UART, sending real TX data, or driving TFDU boards.",
            "PASS_OFFLINE_NO_ETHERNET" if no_ethernet_network_offline_ok else "MISSING",
            rel(no_ethernet_network_summary),
            "No-Ethernet network gate passes 11/11 cases: PS bridge static DHCP/TCP checks, host unit tests, offline mock traffic/reconnect, network fault recovery model, direct two-AX7010 model, board TCP safe no-Ethernet blocker, two-AX7010 wrapper offline model/cap dry-run, rotating/product-loop safe cap dry-runs, and reduced 8-lane fragment=16 hardware safe cap dry-run with raw 32/16 Mbit/s bitstream precondition."
            if no_ethernet_network_offline_ok
            else "Missing no-Ethernet network offline acceptance evidence.",
        ),
        AuditItem(
            "NO-ETHERNET-NETWORK-BOUNDARY",
            "Host/PS TCP boundary behavior is stress-tested offline while the development board has no Ethernet cable, without overclaiming real TCP/DHCP acceptance.",
            "PASS_OFFLINE_NO_ETHERNET" if no_ethernet_network_boundary_ok else "MISSING",
            rel(no_ethernet_network_boundary_md),
            "Boundary evidence passes 8/8 localhost scenarios: TCP fragmentation/coalescing, missing ACK timeout, TX ERROR failure, oversize payload rejection, reconnect payload exchange, independent 4+4 full-duplex lane masks, protocol-desync diagnostics, and explicit no-real-board boundary markers."
            if no_ethernet_network_boundary_ok
            else "Missing no-Ethernet network boundary evidence.",
        ),
        AuditItem(
            "HOST-STATUS-SNAPSHOT",
            "The PC host view can display device, link, TX/RX, error, timing, lane-coverage, and reconnect status fields under the current no-Ethernet boundary.",
            "PASS_OFFLINE_NO_ETHERNET" if host_status_snapshot_ok else "MISSING",
            rel(host_status_snapshot_md),
            "Host status snapshot passes with explicit device/network state, TX/RX packets and rates, errors=0, pending=0, RTT fields, HDX lane coverage 0xff, 4+4 FDX A->B 0x0f / B->A 0xf0 lane masks, reconnect status, and no hardware/UART/TFDU side effects."
            if host_status_snapshot_ok
            else "Missing explicit host status display snapshot.",
        ),
        AuditItem(
            "EXTERNAL-PRECONDITIONS",
            "The current host and external connection state is recorded by a read-only preflight before attempting future real hardware acceptance.",
            "PASS_RECORDED_NO_ETHERNET_BLOCKER" if external_preconditions_ok else "MISSING",
            rel(external_preconditions_md),
            "Read-only preflight records Realtek Ethernet disconnected, COM3 CP210x present, Vivado 2023.1 present, shutdown/candidate bitstreams present, active project restored to 2-lane/PORT1, and no hardware/UART/TFDU side effects."
            if external_preconditions_ok
            else "Missing read-only external precondition snapshot.",
        ),
        AuditItem(
            "REAL-ACCEPTANCE-RUNBOOK",
            "An ordered runbook exists for future real N03/N04/A01/S05/A02 acceptance, including safe commands, validation commands, shutdown boundaries, and current blockers.",
            "PASS_WAITING_FOR_ETHERNET" if real_acceptance_runbook_ok else "MISSING",
            rel(real_acceptance_runbook_md),
            "Runbook covers five remaining real-acceptance stages, preserves the 600 s cap and no-side-effect generator markers, and currently blocks all stages on the recorded no-Ethernet condition."
            if real_acceptance_runbook_ok
            else "Missing generated real-acceptance runbook.",
        ),
        AuditItem(
            "REAL-ACCEPTANCE-SEQUENCE-SAFE",
            "The top-level real-acceptance entry point always runs external preflight and remaining-readiness gates first, then blocks real wrappers under the current no-Ethernet condition.",
            "PASS_BLOCKED_NO_ETHERNET" if real_acceptance_sequence_ok else "MISSING",
            rel(real_acceptance_sequence_md),
            "Safe sequence refreshes external preconditions/runbook/readiness, plans all five real-acceptance stages, classifies the five remaining blockers, blocks each wrapper on ethernet_link plus TCP blockers, executes zero hardware wrappers, and records no hardware programming, no UART write, and no TFDU drive."
            if real_acceptance_sequence_ok
            else "Missing safe top-level real-acceptance sequence evidence.",
        ),
        AuditItem(
            "RFCM-PROTOCOL-CONTRACT",
            "The PS lwIP bridge and PC client share the same RFCM wire contract, status payload layout, config bits, and final 8-lane/4+4 lane-mask encodings.",
            "PASS_OFFLINE_CONTRACT" if protocol_contract_ok else "MISSING",
            rel(protocol_contract_md),
            "Protocol contract check passes 25 source-level checks: RFCM magic/version/header/payload limit, 9 frame types, 4 config bits, 16 status fields, 8-lane half-duplex mask, and 4+4 full-duplex TX/RX masks; no hardware, UART, or TFDU side effects."
            if protocol_contract_ok
            else "Missing RFCM protocol contract evidence.",
        ),
        AuditItem(
            "PS-LWIP-BRIDGE-STATIC-SOURCE",
            "The PS lwIP bridge source has structured offline evidence for DHCP, static fallback, TCP listen/reconnect handling, RFCM parsing, status/error forwarding, and PC compatibility.",
            "PASS_SOURCE_NO_ETHERNET" if ps_lwip_bridge_static_ok else "MISSING",
            rel(ps_lwip_bridge_static_md),
            "Static source evidence passes 64 checks, records DHCP/static/TCP/RFCM readiness, preserves the hard constraint hash, and explicitly marks itself as no-hardware/no-UART/no-TFDU/no-real-board TCP-DHCP evidence."
            if ps_lwip_bridge_static_ok
            else "Missing structured PS lwIP bridge static source evidence.",
        ),
        AuditItem(
            "TWO-AX7010-OFFLINE-END-TO-END",
            "Two independent AX7010-style PS bridge endpoints exchange bidirectional PC traffic through an offline IR link model.",
            "PASS_OFFLINE_MODEL" if two_system_offline_pass else "MISSING",
            rel(two_ax7010_model_md),
            "Offline model passes with two RFCM TCP endpoints, bidirectional payload integrity, 8-lane HDX mask coverage 0xff, 4+4 FDX configured over RFCM with A->B TX/RX 0x0f and B->A TX/RX 0xf0, route probing, recovery events, and queued RX after reconnect."
            if two_system_offline_pass
            else "Missing two-endpoint offline end-to-end model evidence.",
        ),
        AuditItem(
            "FULL-SYSTEM-CAPPED-DIGITAL-TWIN",
            "One offline model covers two AX7010 endpoints, PC/PS TCP-DHCP behavior, 8-lane rotating autoroute, short impairments, and the active 10-minute cap.",
            "PASS_OFFLINE_MODEL" if full_system_capped_model_pass else "MISSING",
            rel(full_system_twin_md),
            "Offline model passes with 600 s cap, 6000 rotations, 48000 sector changes, all 8 lanes/routes covered, TCP/DHCP/reconnect events, raw-PHY-only rate claim, half-duplex coverage 0xff, and explicit full-duplex A->B TX 0x0f / B->A TX 0xf0 coverage."
            if full_system_capped_model_pass
            else "Missing full-system capped digital-twin model evidence.",
        ),
        AuditItem(
            "FULL-SYSTEM-OFFLINE-TARGET-ENVELOPE",
            "The full-system digital twin is checked against the target-level offline envelope while preserving the real-hardware and no-Ethernet blockers.",
            "PASS_OFFLINE_TARGET_ENVELOPE_NOT_HARDWARE" if full_system_offline_envelope_pass else "MISSING",
            rel(full_system_envelope_md),
            "Envelope passes 15/15 checks: 600 s cap, 200 mm / 600 rpm rotating metadata, 8-lane raw 32 Mbit/s half-duplex, 4+4 raw 16 Mbit/s full-duplex per direction, half/full-duplex lane coverage, autoroute search, dynamic TX/RX permutation relearn, CRC/ACK/blockage recovery, TCP reconnect, DHCP/static fallback, queued RX, and explicit real-acceptance=0/no-Ethernet boundaries."
            if full_system_offline_envelope_pass
            else "Missing full-system offline target-envelope evidence.",
        ),
        AuditItem(
            "BOARD-TCP-DHCP",
            "Real board PS-to-PC TCP/DHCP communication passes with reconnect/fallback behavior.",
            "MISSING_HARDWARE" if not board_tcp_evidence else "PASS",
            rel(board_tcp_summary) if board_tcp_summary is not None else rel(post_status),
            "Latest board TCP/DHCP safe run is blocked by the current no-Ethernet-cable condition; no real board TCP/DHCP pass evidence is present."
            if ethernet_link_unavailable_now and not board_tcp_evidence
            else "Latest board TCP/DHCP safe run is blocked by hardware/network precondition; no real board TCP/DHCP pass evidence is present."
            if board_tcp_blocked and not board_tcp_evidence
            else "Offline gate passes, but no real board TCP/DHCP evidence is present."
            if not board_tcp_evidence
            else "Real board TCP/DHCP evidence found.",
        ),
        AuditItem(
            "TWO-AX7010-SAFE-HARNESS",
            "A real two-AX7010 end-to-end acceptance entrypoint exists, stays safe by default, caps continuous operation at 600 s, requires shutdown-after-run for real traffic, and records offline/no-Ethernet blockers without driving TFDU boards.",
            "PASS_READY_NO_ETHERNET" if two_ax7010_safe_wrapper_ok else "MISSING",
            rel(two_ax7010_safe_wrapper),
            "Safe wrapper evidence includes offline model pass, dry-run duration cap to 600 s, no FPGA/UART writes, no TX/TFDU drive unless explicitly allowed, a required shutdown-after-run gate for future real traffic, and current no-Ethernet blocker."
            if two_ax7010_safe_wrapper_ok
            else "Missing complete safe-wrapper evidence for two-AX7010 end-to-end acceptance.",
        ),
        AuditItem(
            "ROTATING-SHAFT-SAFE-HARNESS",
            "A real rotating-shaft acceptance entrypoint exists, stays safe by default, caps continuous operation at 600 s, requires shutdown-after-run for real traffic, and records a no-hardware dry-run.",
            "PASS_READY_NO_ETHERNET" if rotating_shaft_safe_wrapper_ok else "MISSING",
            rel(rotating_shaft_dryrun_summary) if rotating_shaft_dryrun_summary is not None else rel(rotating_shaft_safe_wrapper),
            "Safe wrapper dry-run records 20 cm / 600 rpm target metadata, caps a 7200 s request to 600 s, sends no real TX data, drives no TFDU boards, and requires shutdown-after-run before any future real traffic."
            if rotating_shaft_safe_wrapper_ok
            else "Missing complete safe-wrapper evidence for rotating-shaft acceptance.",
        ),
        AuditItem(
            "ROTATING-FIXTURE-LOG-VALIDATOR",
            "A structured fixture-log template and validator exist for future 20 cm / 600 rpm rotating-shaft evidence without treating template rows as real acceptance.",
            "PASS_TEMPLATE_READY_NO_HARDWARE" if rotating_fixture_log_validator_ok else "MISSING",
            rel(rotating_fixture_validation_md),
            "Validator/template evidence records target diameter 200 mm, target 600 rpm, a 600 s continuous segment cap, template-only status, and no FPGA/UART/TFDU action."
            if rotating_fixture_log_validator_ok
            else "Missing structured rotating fixture log template/validator evidence.",
        ),
        AuditItem(
            "REAL-ACCEPTANCE-EVIDENCE-VALIDATOR",
            "A structured evidence template and validator exist for future real PS-PC TCP/DHCP, two-AX7010, product-loop, rotating-shaft, and 8-lane hardware acceptance logs without treating templates as real evidence.",
            "PASS_TEMPLATE_READY_NO_HARDWARE" if real_acceptance_evidence_validator_ok else "MISSING",
            rel(real_acceptance_validation_md),
            "Validator/template evidence covers five future real-acceptance modes, records no FPGA/UART/TFDU action by the validator, requires the 600 s cap where relevant, requires raw/effective throughput separation for real IR traffic claims, and keeps template-only output marked as REAL_ACCEPTANCE_EVIDENCE=0."
            if real_acceptance_evidence_validator_ok
            else "Missing structured real-acceptance evidence template/validator output.",
        ),
        AuditItem(
            "REAL-ACCEPTANCE-VALIDATOR-SELFTEST",
            "The real-acceptance evidence validator rejects synthetic false-real logs before future hardware evidence can be promoted to PASS.",
            "PASS_FALSE_REAL_REJECTED" if real_acceptance_validator_selftest_ok else "MISSING",
            rel(real_acceptance_validator_selftest_md),
            "Self-test passes 12/12 negative cases: all template summaries, dry-run/no-Ethernet blocker logs, missing shutdown-after-run, duration over 600 s, payload-over-raw overclaim, rotating template fixture evidence, missing 8-lane shutdown-before-run, and missing physical-matrix PASS gate are all rejected without producing real acceptance evidence."
            if real_acceptance_validator_selftest_ok
            else "Missing or failing real-acceptance validator self-test.",
        ),
        AuditItem(
            "REAL-ACCEPTANCE-PROMOTION-GATE",
            "The remaining real-acceptance items cannot be promoted to true PASS unless the current evidence chain proves the corresponding real hardware or network acceptance.",
            "PASS_PROMOTION_BLOCKED_CORRECTLY" if real_acceptance_promotion_gate_ok else "MISSING",
            rel(real_acceptance_promotion_gate_md),
            "Promotion gate blocks N03, N04, S05, A01, and A02 with promotable=0 because the board Ethernet link is unavailable and not changeable now, current evidence is template/offline only, and no hardware/UART/TFDU action was executed."
            if real_acceptance_promotion_gate_ok
            else "Missing or failing real-acceptance promotion gate.",
        ),
        AuditItem(
            "DURATION-CAP-COMPLIANCE",
            "The active safety rule caps physical continuous TFDU/TX operation at 600 seconds, and legacy 2-hour naming cannot become a live 7200-second hardware command.",
            "PASS_600S_CAP_ENFORCED" if duration_cap_compliance_ok else "MISSING",
            rel(duration_cap_compliance_md),
            "Duration-cap gate passes 16/16 checks: host acceptance, PS lwIP README, safe wrappers, validators, runbook, sequence, readiness, promotion gate, and dry-run evidence all preserve the 600 s cap with no hardware/UART/TFDU action."
            if duration_cap_compliance_ok
            else "Missing or failing duration-cap compliance evidence.",
        ),
        AuditItem(
            "SAFE-WRAPPER-GUARD-CONTRACT",
            "Future real-acceptance wrappers keep explicit guards before any real traffic, TFDU drive, or hardware-side claim can be executed or promoted.",
            "PASS_GUARDS_STATICALLY_PROVED" if safe_wrapper_guard_ok else "MISSING",
            rel(safe_wrapper_guard_md),
            "Guard contract passes 25/25 checks: no wrapper is executed by the check, real traffic requires AllowTraffic, real TFDU traffic requires shutdown-after-run and the physical lane matrix gate, the physical gate has a passing synthetic self-test, P1 lane-mapping wrappers have emergency/finally shutdown guards, failed-link retests are guarded against stale repeated physical failures, 8-lane use requires review plus shutdown-before/after, and the current no-Ethernet sequence executes zero wrappers."
            if safe_wrapper_guard_ok
            else "Missing or failing safe-wrapper guard-contract evidence.",
        ),
        AuditItem(
            "DRC-RELEASE-GATE",
            "DRC/methodology status blocks release or 4/8-lane expansion until pre-release actions are fixed, validated, or formally waived, while allowing debug progress.",
            "BLOCK_RELEASE_NOT_READY_DEBUG_CAN_CONTINUE" if drc_release_gate_ok else "MISSING",
            rel(drc_release_gate_md),
            "DRC release gate passes all row checks with no hardware/UART/TFDU/Vivado side effects: debug can continue, TIMING-24/TIMING-28 and ULMTCS-2 are cleared by the release-personality evidence, but release_ready=0 because REQP-181 remains a pre-release action."
            if drc_release_gate_ok
            else "Missing or failing DRC release gate evidence.",
        ),
        AuditItem(
            "PRODUCT-LOOP-SAFE-HARNESS",
            "A real PC-PS-PL-IR-external-IR product-loop acceptance entrypoint exists, stays safe by default, caps continuous operation at 600 s, requires shutdown-after-run for real traffic, and records a no-hardware dry-run.",
            "PASS_READY_NO_ETHERNET" if product_loop_safe_wrapper_ok else "MISSING",
            rel(product_loop_dryrun_summary) if product_loop_dryrun_summary is not None else rel(product_loop_safe_wrapper),
            "Safe wrapper dry-run records the two-AX7010 product-loop topology, caps a 7200 s request to 600 s, sends no real TX data, drives no TFDU boards, and requires shutdown-after-run before any future real traffic."
            if product_loop_safe_wrapper_ok
            else "Missing complete safe-wrapper evidence for product-loop acceptance.",
        ),
        AuditItem(
            "EIGHT-LANE-HARDWARE-SAFE-HARNESS",
            "A real 8-lane TFDU hardware acceptance entrypoint exists, stays safe by default, caps continuous operation at 600 s, requires pinmap review plus shutdown-before/after for real traffic, and records a no-hardware dry-run.",
            "PASS_READY_NO_ETHERNET" if eightlane_hw_safe_wrapper_ok else "MISSING",
            rel(eightlane_hw_dryrun_summary) if eightlane_hw_dryrun_summary is not None else rel(eightlane_hw_safe_wrapper),
            "Safe wrapper dry-run records 8-lane candidate pin coverage, caps a 7200 s request to 600 s, carries the reduced fragment=16 raw 32/16 Mbit/s bitstream precondition, sends no real TX data, drives no TFDU boards, and previews the current no-Ethernet blocker."
            if eightlane_hw_safe_wrapper_ok
            else "Missing complete safe-wrapper evidence for 8-lane hardware acceptance.",
        ),
        AuditItem(
            "TWO-AX7010-SYSTEMS",
            "Two complete AX7010 systems communicate through the infrared link.",
            "MISSING_HARDWARE" if not two_system_evidence else "PASS",
            rel(two_ax7010_real_summary) if two_ax7010_real_summary is not None else rel(post_status),
            "Current hardware evidence is single-board/single-lane scoped; no two-complete-system evidence found."
            if not two_system_evidence
            else "Two-system evidence found.",
        ),
        AuditItem(
            "EIGHT-LANE-HARDWARE",
            "Up to 8 TFDU lanes are physically wired and validated.",
            "MISSING_HARDWARE" if not eight_lane_hw_evidence else "PASS",
            rel(eightlane_hw_real_summary) if eightlane_hw_real_summary is not None else rel(post_status),
            "Current post-G1 evidence is simulation/offline for expansion; no 8-lane hardware validation found."
            if not eight_lane_hw_evidence
            else "8-lane hardware evidence found.",
        ),
        AuditItem(
            "REAL-ROTATING-SHAFT",
            "Real 20 cm diameter, 600 rpm rotating-shaft optical communication is validated.",
            "MISSING_HARDWARE" if not real_rotation_evidence else "PASS",
            rel(rotating_shaft_real_summary) if rotating_shaft_real_summary is not None else rel(post_status),
            "Simulation/model coverage exists, but no physical rotating shaft evidence found."
            if not real_rotation_evidence
            else "Physical rotating-shaft evidence found.",
        ),
        AuditItem(
            "RUNTIME-SAFETY",
            "Physical runs obey the active runtime cap and program shutdown after runs.",
            "PASS" if shutdown_bitstream_ok and g1_capped_pass else "MISSING",
            rel(g1_config),
            "Current cap is 600 s; latest G1 window to shutdown end is 582.2 s and shutdown bitstream hash is recorded."
            if shutdown_bitstream_ok and g1_capped_pass
            else "Missing runtime/shutdown evidence.",
        ),
        AuditItem(
            "HOST-ACCEPTANCE-RUNTIME-CAP",
            "PC acceptance wrapper caps continuous traffic modes at 600 seconds, including historical soak_2h commands and manual duration overrides.",
            "PASS" if host_acceptance_runtime_cap_ok else "MISSING",
            rel(host_acceptance),
            "run_acceptance.ps1 defines MaxContinuousRunSeconds=600, caps requested durations with Math.Min, and maps soak_2h default duration to the cap."
            if host_acceptance_runtime_cap_ok
            else "Missing host-side acceptance runtime cap enforcement.",
        ),
        AuditItem(
            "BOOT-ARTIFACTS",
            "Zynq BOOT.BIN packages for PS lwIP bridge and PS-PS loopback are current against their BIF components.",
            "PASS" if boot_artifacts_ok else "MISSING",
            rel(boot_audit_md),
            "Boot audit passes for ps_lwip_bridge and ps_ps_loopback; both BOOT.BIN files are present, non-stale, and contain expected application markers."
            if boot_artifacts_ok
            else "Missing or stale BOOT.BIN package evidence.",
        ),
        AuditItem(
            "ARTIFACT-TRACEABILITY",
            "Evidence can be traced to scripts, bitstream, XSA, ELF, and report hashes.",
            "PASS" if artifact_hashes_ok else "MISSING",
            rel(g1_artifacts),
            "G1 artifact hash file records current generated bit/ltx/xsa/elf and evidence hashes."
            if artifact_hashes_ok
            else "Missing artifact hash evidence.",
        ),
        AuditItem(
            "STATUS-CONSISTENCY",
            "The status report, target matrix, strict audit, remaining plan, hash manifest, and active project state reference the same latest offline evidence set.",
            "PASS" if status_consistency_ok else "MISSING",
            rel(status_consistency_md),
            "Status consistency gate passes without programming hardware, writing UART, or driving TFDU boards."
            if status_consistency_ok
            else "Missing or failing full-target status consistency evidence.",
        ),
    ]

    meta = {
        "post_gate_csv": rel(post_csv),
        "post_gate_summary": rel(post_summary),
        "g1_report": rel(g1_report),
        "post_status": rel(post_status),
        "rate_options_md": rel(rate_options_md),
        "rate_options_csv": rel(rate_options_csv),
        "rate_boundary_md": rel(rate_boundary_md),
        "rate_boundary_json": rel(rate_boundary_json),
        "payload_gap_closure_md": rel(payload_gap_closure_md),
        "payload_gap_closure_json": rel(payload_gap_closure_json),
        "payload_gap_closure_csv": rel(payload_gap_closure_csv),
        "target_consistency_md": rel(target_consistency_md),
        "target_consistency_json": rel(target_consistency_json),
        "status_consistency_md": rel(status_consistency_md),
        "status_consistency_json": rel(status_consistency_json),
        "status_consistency_csv": rel(status_consistency_csv),
        "external_preconditions_md": rel(external_preconditions_md),
        "external_preconditions_json": rel(external_preconditions_json),
        "external_preconditions_csv": rel(external_preconditions_csv),
        "real_acceptance_runbook_md": rel(real_acceptance_runbook_md),
        "real_acceptance_runbook_json": rel(real_acceptance_runbook_json),
        "real_acceptance_runbook_csv": rel(real_acceptance_runbook_csv),
        "real_acceptance_sequence_summary": rel(real_acceptance_sequence_summary),
        "real_acceptance_sequence_md": rel(real_acceptance_sequence_md),
        "real_acceptance_sequence_json": rel(real_acceptance_sequence_json),
        "real_acceptance_sequence_csv": rel(real_acceptance_sequence_csv),
        "protocol_contract_md": rel(protocol_contract_md),
        "protocol_contract_json": rel(protocol_contract_json),
        "protocol_contract_csv": rel(protocol_contract_csv),
        "ps_lwip_bridge_static_md": rel(ps_lwip_bridge_static_md),
        "ps_lwip_bridge_static_json": rel(ps_lwip_bridge_static_json),
        "ps_lwip_bridge_static_csv": rel(ps_lwip_bridge_static_csv),
        "ps_pc_offline_summary": rel(ps_pc_offline_summary),
        "ps_pc_offline_unittest": rel(ps_pc_offline_unittest),
        "ps_pc_offline_acceptance": rel(ps_pc_offline_acceptance),
        "two_ax7010_model_md": rel(two_ax7010_model_md),
        "two_ax7010_model_json": rel(two_ax7010_model_json),
        "two_ax7010_model_csv": rel(two_ax7010_model_csv),
        "host_status_snapshot_md": rel(host_status_snapshot_md),
        "host_status_snapshot_json": rel(host_status_snapshot_json),
        "host_status_snapshot_csv": rel(host_status_snapshot_csv),
        "no_ethernet_network_boundary_md": rel(no_ethernet_network_boundary_md),
        "no_ethernet_network_boundary_json": rel(no_ethernet_network_boundary_json),
        "no_ethernet_network_boundary_csv": rel(no_ethernet_network_boundary_csv),
        "target_matrix_md": rel(target_matrix_md),
        "target_matrix_json": rel(target_matrix_json),
        "target_matrix_csv": rel(target_matrix_csv),
        "full_system_twin_md": rel(full_system_twin_md),
        "full_system_twin_json": rel(full_system_twin_json),
        "full_system_twin_csv": rel(full_system_twin_csv),
        "full_system_envelope_md": rel(full_system_envelope_md),
        "full_system_envelope_json": rel(full_system_envelope_json),
        "full_system_envelope_csv": rel(full_system_envelope_csv),
        "rotating_autoroute_offline_md": rel(rotating_autoroute_offline_md),
        "rotating_autoroute_offline_json": rel(rotating_autoroute_offline_json),
        "rotating_autoroute_offline_csv": rel(rotating_autoroute_offline_csv),
        "topology_capacity_md": rel(topology_capacity_md),
        "topology_capacity_json": rel(topology_capacity_json),
        "topology_capacity_csv": rel(topology_capacity_csv),
        "remaining_hw_plan_md": rel(remaining_hw_plan_md),
        "remaining_hw_plan_json": rel(remaining_hw_plan_json),
        "remaining_hw_plan_csv": rel(remaining_hw_plan_csv),
        "remaining_acceptance_readiness_md": rel(remaining_acceptance_readiness_md),
        "remaining_acceptance_readiness_json": rel(remaining_acceptance_readiness_json),
        "remaining_acceptance_readiness_csv": rel(remaining_acceptance_readiness_csv),
        "rotating_fixture_validator": rel(rotating_fixture_validator),
        "rotating_fixture_template": rel(rotating_fixture_template),
        "rotating_fixture_validation_md": rel(rotating_fixture_validation_md),
        "rotating_fixture_validation_json": rel(rotating_fixture_validation_json),
        "rotating_fixture_validation_csv": rel(rotating_fixture_validation_csv),
        "real_acceptance_validation_md": rel(real_acceptance_validation_md),
        "real_acceptance_validation_json": rel(real_acceptance_validation_json),
        "real_acceptance_validation_csv": rel(real_acceptance_validation_csv),
        "real_acceptance_validator_selftest_md": rel(real_acceptance_validator_selftest_md),
        "real_acceptance_validator_selftest_json": rel(real_acceptance_validator_selftest_json),
        "real_acceptance_validator_selftest_csv": rel(real_acceptance_validator_selftest_csv),
        "real_acceptance_promotion_gate_md": rel(real_acceptance_promotion_gate_md),
        "real_acceptance_promotion_gate_json": rel(real_acceptance_promotion_gate_json),
        "real_acceptance_promotion_gate_csv": rel(real_acceptance_promotion_gate_csv),
        "duration_cap_compliance_md": rel(duration_cap_compliance_md),
        "duration_cap_compliance_json": rel(duration_cap_compliance_json),
        "duration_cap_compliance_csv": rel(duration_cap_compliance_csv),
        "safe_wrapper_guard_md": rel(safe_wrapper_guard_md),
        "safe_wrapper_guard_json": rel(safe_wrapper_guard_json),
        "safe_wrapper_guard_csv": rel(safe_wrapper_guard_csv),
        "drc_release_gate_md": rel(drc_release_gate_md),
        "drc_release_gate_json": rel(drc_release_gate_json),
        "drc_release_gate_csv": rel(drc_release_gate_csv),
        "eightlane_readiness_md": rel(eightlane_readiness_md),
        "eightlane_readiness_json": rel(eightlane_readiness_json),
        "eightlane_readiness_csv": rel(eightlane_readiness_csv),
        "eightlane_external_project_md": rel(eightlane_external_project_md),
        "eightlane_external_project_json": rel(eightlane_external_project_json),
        "eightlane_external_project_csv": rel(eightlane_external_project_csv),
        "external_lane_scan_md": rel(external_lane_scan_md),
        "external_lane_scan_json": rel(external_lane_scan_json),
        "external_lane_scan_csv": rel(external_lane_scan_csv),
        "external_option_scan_md": rel(external_option_scan_md),
        "external_option_scan_json": rel(external_option_scan_json),
        "external_option_scan_csv": rel(external_option_scan_csv),
        "external_reduced_lane_scan_md": rel(external_reduced_lane_scan_md),
        "external_reduced_lane_scan_json": rel(external_reduced_lane_scan_json),
        "external_reduced_lane_scan_csv": rel(external_reduced_lane_scan_csv),
        "external_reduced_5to8_md": rel(external_reduced_5to8_md),
        "external_reduced_5to8_json": rel(external_reduced_5to8_json),
        "external_reduced_5to8_csv": rel(external_reduced_5to8_csv),
        "external_reduced_5lane_frag32_md": rel(external_reduced_5lane_frag32_md),
        "external_reduced_5lane_frag32_json": rel(external_reduced_5lane_frag32_json),
        "external_reduced_5lane_frag32_csv": rel(external_reduced_5lane_frag32_csv),
        "external_reduced_5lane_frag32_route_md": rel(external_reduced_5lane_frag32_route_md),
        "external_reduced_5lane_frag32_route_json": rel(external_reduced_5lane_frag32_route_json),
        "external_reduced_5lane_frag32_route_csv": rel(external_reduced_5lane_frag32_route_csv),
        "external_reduced_5lane_frag32_bitstream_md": rel(external_reduced_5lane_frag32_bitstream_md),
        "external_reduced_5lane_frag32_bitstream_json": rel(external_reduced_5lane_frag32_bitstream_json),
        "external_reduced_5lane_frag32_bitstream_csv": rel(external_reduced_5lane_frag32_bitstream_csv),
        "external_reduced_8lane_frag16_bitstream_md": rel(external_reduced_8lane_frag16_bitstream_md),
        "external_reduced_8lane_frag16_bitstream_json": rel(external_reduced_8lane_frag16_bitstream_json),
        "external_reduced_8lane_frag16_bitstream_csv": rel(external_reduced_8lane_frag16_bitstream_csv),
        "external_reduced_route_md": rel(external_reduced_route_md),
        "external_reduced_route_json": rel(external_reduced_route_json),
        "external_reduced_route_csv": rel(external_reduced_route_csv),
        "external_reduced_4lane_route_md": rel(external_reduced_4lane_route_md),
        "external_reduced_4lane_route_json": rel(external_reduced_4lane_route_json),
        "external_reduced_4lane_route_csv": rel(external_reduced_4lane_route_csv),
        "external_reduced_4lane_bitstream_md": rel(external_reduced_4lane_bitstream_md),
        "external_reduced_4lane_bitstream_json": rel(external_reduced_4lane_bitstream_json),
        "external_reduced_4lane_bitstream_csv": rel(external_reduced_4lane_bitstream_csv),
        "external_reduced_4lane_bringup_md": rel(external_reduced_4lane_bringup_md),
        "external_reduced_4lane_bringup_json": rel(external_reduced_4lane_bringup_json),
        "external_reduced_4lane_bringup_csv": rel(external_reduced_4lane_bringup_csv),
        "board_tcp_summary": rel(board_tcp_summary),
        "no_ethernet_network_summary": rel(no_ethernet_network_summary),
        "no_ethernet_network_csv": rel(no_ethernet_network_csv),
        "two_ax7010_safe_wrapper": rel(two_ax7010_safe_wrapper),
        "rotating_shaft_safe_wrapper": rel(rotating_shaft_safe_wrapper),
        "rotating_shaft_dryrun_summary": rel(rotating_shaft_dryrun_summary),
        "product_loop_safe_wrapper": rel(product_loop_safe_wrapper),
        "product_loop_dryrun_summary": rel(product_loop_dryrun_summary),
        "eightlane_hw_safe_wrapper": rel(eightlane_hw_safe_wrapper),
        "eightlane_hw_dryrun_summary": rel(eightlane_hw_dryrun_summary),
        "two_ax7010_offline_summary": rel(two_ax7010_offline_summary),
        "two_ax7010_dryrun_summary": rel(two_ax7010_dryrun_summary),
        "two_ax7010_blocked_summary": rel(two_ax7010_blocked_summary),
        "two_ax7010_real_summary": rel(two_ax7010_real_summary),
        "rotating_shaft_real_summary": rel(rotating_shaft_real_summary),
        "eightlane_hw_real_summary": rel(eightlane_hw_real_summary),
        "boot_audit_md": rel(boot_audit_md),
        "boot_audit_json": rel(boot_audit_json),
        "host_acceptance": rel(host_acceptance),
        "host_client": rel(host_client),
        "host_client_tests": rel(host_client_tests),
        "host_mock_server": rel(host_mock_server),
    }
    return items, meta


def overall_status(items: list[AuditItem]) -> str:
    statuses = {item.item_id: item.status for item in items}
    hard_fail = any(item.status == "FAIL" for item in items)
    missing_hardware = any(item.status == "MISSING_HARDWARE" for item in items)
    payload_not_met = statuses.get("PAYLOAD-THROUGHPUT") == "NOT_MET_CURRENT_FORMAT"
    missing = any(item.status == "MISSING" for item in items)
    if hard_fail:
        return "FAIL"
    if missing_hardware or payload_not_met or missing:
        return "INCOMPLETE_SIM_OFFLINE_PROGRESS"
    return "FULL_TARGET_PASS"


def next_action(items: list[AuditItem]) -> str:
    statuses = {item.item_id: item.status for item in items}
    if statuses.get("PAYLOAD-THROUGHPUT") == "NOT_MET_CURRENT_FORMAT":
        if statuses.get("PAYLOAD-RATE-OPTIONS") == "PASS_MODEL":
            return (
                "Decide whether final 32/16 Mbit/s is raw PHY capacity or effective payload/end-to-end throughput; "
                "the current model shows 16/8 payload is reachable with larger fragments, but 32/16 payload needs more PHY capacity, more lanes, lower overhead, or a different ACK strategy."
            )
        return (
            "Choose whether final speed is raw PHY capacity or effective payload/end-to-end throughput; "
            "if payload, redesign framing/parallelism before claiming 32/16 Mbit/s."
        )
    if statuses.get("BOARD-TCP-DHCP") == "MISSING_HARDWARE":
        if statuses.get("TWO-AX7010-SAFE-HARNESS") == "PASS_READY_NO_ETHERNET":
            return (
                "Ethernet cable is currently unavailable, so do not retry real board TCP/DHCP; "
                "continue simulation/offline work and run the safe board/TCP acceptance only after an Ethernet link exists."
            )
        return "Run real board PS-to-PC TCP/DHCP test with reconnect/fallback evidence."
    if statuses.get("TWO-AX7010-SYSTEMS") == "MISSING_HARDWARE":
        return "Prepare two complete AX7010 systems and run end-to-end infrared communication acceptance."
    if statuses.get("REAL-ROTATING-SHAFT") == "MISSING_HARDWARE":
        return "Build rotating-shaft test fixture evidence for 20 cm diameter and 600 rpm."
    return "Full target appears complete; perform manual completion audit before marking goal complete."


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    items, meta = build_audit()
    status = overall_status(items)
    action = next_action(items)
    generated = datetime.now().isoformat(timespec="seconds")

    md_path = REPORTS / f"full_target_audit_current_{DATE_TAG}.md"
    json_path = REPORTS / f"full_target_audit_current_{DATE_TAG}.json"

    rows = [[item.item_id, item.requirement, item.status, item.evidence, item.note] for item in items]
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1

    md = [
        "# RF_COMM Full Target Audit",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{status}`",
        f"- Next action: `{action}`",
        "",
        "This audit is intentionally stricter than the G1 and post-G1 simulation gates. It separates simulation/offline progress from physical product acceptance.",
        "",
        "## Status Counts",
        "",
        md_table(["status", "count"], [[k, str(v)] for k, v in sorted(counts.items())]),
        "",
        "## Evidence Table",
        "",
        md_table(["id", "requirement", "status", "evidence", "note"], rows),
        "",
        f"RF_COMM_FULL_TARGET_AUDIT overall={status}",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": status,
        "next_action": action,
        "meta": meta,
        "items": [asdict(item) for item in items],
        "status_counts": counts,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"RF_COMM_FULL_TARGET_AUDIT overall={status} next_action={action}")
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
