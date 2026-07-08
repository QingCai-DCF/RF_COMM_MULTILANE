from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
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


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def norm(value: str | None) -> str:
    return (value or "").replace("\\", "/")


def latest(pattern: str) -> Path | None:
    matches = [path for path in ROOT.glob(pattern) if path.exists() and path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def latest_containing(pattern: str, needles: Iterable[str]) -> Path | None:
    for path in sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True):
        text = read_text(path)
        if all(needle in text for needle in needles):
            return path
    return None


def contains_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def add(rows: list[CheckRow], check: str, ok: bool, expected: str, actual: str, note: str) -> None:
    rows.append(CheckRow(check, "PASS" if ok else "FAIL", expected, actual, note))


def hash_line(path: Path | None) -> str:
    if path is None:
        return ""
    return f"{sha256(path)}  {rel(path)}"


def manifest_has_hash(manifest_text: str, path: Path | None) -> bool:
    if path is None:
        return False
    return hash_line(path) in manifest_text


def meta_path(payload: dict[str, Any], key: str) -> str:
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return ""
    value = meta.get(key)
    return norm(value if isinstance(value, str) else "")


def md_table(rows: list[CheckRow]) -> str:
    out = [
        "| check | status | expected | actual | note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        out.append(
            "| "
            + " | ".join(
                cell.replace("\n", " ").replace("|", "/")
                for cell in [row.check, row.status, row.expected, row.actual, row.note]
            )
            + " |"
        )
    return "\n".join(out)


def build_rows() -> tuple[list[CheckRow], dict[str, str]]:
    rows: list[CheckRow] = []

    constraint = find_hard_constraint()
    status_md = REPORTS / "post_g1_target_status_current.md"
    matrix_md = REPORTS / "target_acceptance_matrix_current.md"
    matrix_json = REPORTS / "target_acceptance_matrix_current.json"
    audit_md = REPORTS / "full_target_audit_current_20260626.md"
    audit_json = REPORTS / "full_target_audit_current_20260626.json"
    remaining_md = REPORTS / "remaining_hardware_acceptance_plan_current.md"
    remaining_readiness_md = REPORTS / "remaining_acceptance_readiness_current.md"
    remaining_readiness_json = REPORTS / "remaining_acceptance_readiness_current.json"
    remaining_readiness_csv = REPORTS / "remaining_acceptance_readiness_current.csv"
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
    full_system_envelope_md = REPORTS / "full_system_offline_target_envelope_current.md"
    full_system_envelope_json = REPORTS / "full_system_offline_target_envelope_current.json"
    full_system_envelope_csv = REPORTS / "full_system_offline_target_envelope_current.csv"
    rotating_dynamic_md = REPORTS / "rotating_dynamic_permutation_autoroute_current.md"
    rotating_dynamic_json = REPORTS / "rotating_dynamic_permutation_autoroute_current.json"
    rotating_dynamic_csv = REPORTS / "rotating_dynamic_permutation_autoroute_current.csv"
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
    repeat_physical_failure_guard_md = REPORTS / "repeat_physical_failure_guard_current.md"
    repeat_physical_failure_guard_json = REPORTS / "repeat_physical_failure_guard_current.json"
    repeat_physical_failure_guard_csv = REPORTS / "repeat_physical_failure_guard_current.csv"
    drc_release_gate_md = REPORTS / "drc_release_gate_current.md"
    drc_release_gate_json = REPORTS / "drc_release_gate_current.json"
    drc_release_gate_csv = REPORTS / "drc_release_gate_current.csv"
    ps_pc_offline_summary = latest_containing(
        "reports/ps_pc_offline_gates_*.summary.txt",
        [
            "PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1",
            "PS_BRIDGE_STATIC_CHECKS_PASS checks=64",
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
    hash_manifest = REPORTS / "full_target_artifacts_hashes.txt"
    xpr = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.xpr"
    wrapper = (
        ROOT
        / "TFDU_VFIR_Client_Array"
        / "TFDU_VFIR_Client.srcs"
        / "sources_1"
        / "imports"
        / "hdl"
        / "design_shiboqi_wrapper.v"
    )

    post_summary = latest_containing(
        "reports/post_g1_target_sim_gate_*.summary.txt",
        ["POST_G1_TARGET_SIM_GATE_PASS=1", "POST_G1_TARGET_SIM_GATE_PASS_COUNT=23"],
    )
    post_cases = None if post_summary is None else post_summary.with_name(post_summary.name.replace(".summary.txt", ".cases.csv"))
    post_md = None if post_summary is None else post_summary.with_name(post_summary.name.replace(".summary.txt", ".md"))
    post_dir = None if post_summary is None else post_summary.with_name(post_summary.name.replace(".summary.txt", ""))

    no_eth_summary = latest_containing(
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
    no_eth_cases = None if no_eth_summary is None else no_eth_summary.with_name(no_eth_summary.name.replace(".summary.txt", ".cases.csv"))
    no_eth_md = None if no_eth_summary is None else no_eth_summary.with_name(no_eth_summary.name.replace(".summary.txt", ".md"))
    no_eth_dir = None if no_eth_summary is None else no_eth_summary.with_name(no_eth_summary.name.replace(".summary.txt", ""))
    no_eth_boundary_md = REPORTS / "no_ethernet_network_boundary_evidence_current.md"
    no_eth_boundary_json = REPORTS / "no_ethernet_network_boundary_evidence_current.json"
    no_eth_boundary_csv = REPORTS / "no_ethernet_network_boundary_evidence_current.csv"

    status_text = read_text(status_md)
    matrix_text = read_text(matrix_md)
    audit_text = read_text(audit_md)
    remaining_text = read_text(remaining_md)
    remaining_readiness_text = read_text(remaining_readiness_md)
    remaining_readiness_json_text = read_text(remaining_readiness_json)
    remaining_readiness_csv_text = read_text(remaining_readiness_csv)
    external_preconditions_text = read_text(external_preconditions_md)
    real_acceptance_runbook_text = read_text(real_acceptance_runbook_md)
    real_acceptance_sequence_text = read_text(real_acceptance_sequence_md)
    real_acceptance_sequence_summary_text = read_text(real_acceptance_sequence_summary)
    real_acceptance_sequence_json_text = read_text(real_acceptance_sequence_json)
    real_acceptance_sequence_csv_text = read_text(real_acceptance_sequence_csv)
    protocol_contract_text = read_text(protocol_contract_md)
    protocol_contract_csv_text = read_text(protocol_contract_csv)
    ps_lwip_bridge_static_text = read_text(ps_lwip_bridge_static_md)
    ps_lwip_bridge_static_csv_text = read_text(ps_lwip_bridge_static_csv)
    full_system_envelope_text = read_text(full_system_envelope_md)
    full_system_envelope_json_text = read_text(full_system_envelope_json)
    full_system_envelope_csv_text = read_text(full_system_envelope_csv)
    rotating_dynamic_text = read_text(rotating_dynamic_md)
    rotating_dynamic_json_text = read_text(rotating_dynamic_json)
    rotating_dynamic_csv_text = read_text(rotating_dynamic_csv)
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
    repeat_physical_failure_guard_text = read_text(repeat_physical_failure_guard_md)
    repeat_physical_failure_guard_json_text = read_text(repeat_physical_failure_guard_json)
    repeat_physical_failure_guard_csv_text = read_text(repeat_physical_failure_guard_csv)
    drc_release_gate_text = read_text(drc_release_gate_md)
    drc_release_gate_json_text = read_text(drc_release_gate_json)
    drc_release_gate_csv_text = read_text(drc_release_gate_csv)
    ps_pc_offline_text = read_text(ps_pc_offline_summary)
    manifest_text = read_text(hash_manifest)
    matrix_payload = read_json(matrix_json)
    audit_payload = read_json(audit_json)
    xpr_text = read_text(xpr)
    wrapper_text = read_text(wrapper)
    post_text = read_text(post_summary)
    no_eth_text = read_text(no_eth_summary)
    no_eth_boundary_text = read_text(no_eth_boundary_md)
    no_eth_boundary_json_text = read_text(no_eth_boundary_json)
    no_eth_boundary_csv_text = read_text(no_eth_boundary_csv)

    add(
        rows,
        "hard_constraint_hash",
        constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256,
        EXPECTED_CONSTRAINT_SHA256,
        sha256(constraint),
        "Root hard constraint file remains unchanged.",
    )
    add(
        rows,
        "latest_post_g1_gate_pass",
        contains_all(
            post_text,
            [
                "POST_G1_TARGET_SIM_GATE_PASS=1",
                "POST_G1_TARGET_SIM_GATE_PASS_COUNT=23",
                "POST_G1_TARGET_SIM_GATE_FAIL_COUNT=0",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_TFDU_DRIVE=1",
            ],
        ),
        "latest passing post-G1 simulation/offline gate",
        rel(post_summary),
        "Latest post-G1 gate must be simulation/offline only and pass all 23 cases.",
    )
    add(
        rows,
        "latest_no_ethernet_gate_pass",
        contains_all(
            no_eth_text,
            [
                "NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS=1",
                "NO_ETHERNET_NETWORK_OFFLINE_PASS_COUNT=11",
                "NO_ETHERNET_NETWORK_OFFLINE_FAIL_COUNT=0",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
                "NO_REAL_BOARD_TCP_DHCP=1",
                "NO_REAL_TWO_AX7010_TRAFFIC=1",
            ],
        ),
        "latest passing no-Ethernet offline gate",
        rel(no_eth_summary),
        "No-Ethernet gate must pass without real board TCP/DHCP or TFDU drive.",
    )

    for path in [post_summary, post_cases, post_md, post_dir, no_eth_summary, no_eth_cases, no_eth_md, no_eth_dir]:
        expected = rel(path)
        actual = "present" if expected and expected in status_text else "missing"
        add(
            rows,
            f"status_report_references_{Path(expected).name if expected else 'missing'}",
            bool(expected and expected in status_text),
            expected,
            actual,
            "Status report should point at the latest generated evidence path.",
        )

    for path in [no_eth_boundary_md, no_eth_boundary_json, no_eth_boundary_csv]:
        expected = rel(path)
        actual = "present" if expected and expected in status_text else "missing"
        add(
            rows,
            f"status_report_references_{Path(expected).name if expected else 'missing'}",
            bool(expected and expected in status_text),
            expected,
            actual,
            "Status report should point at the current no-Ethernet TCP boundary evidence.",
        )

    for path in [external_preconditions_md, external_preconditions_json, external_preconditions_csv]:
        expected = rel(path)
        actual = "present" if expected and expected in status_text else "missing"
        add(
            rows,
            f"status_report_references_{Path(expected).name if expected else 'missing'}",
            bool(expected and expected in status_text),
            expected,
            actual,
            "Status report should point at the current external precondition snapshot.",
        )

    for path in [real_acceptance_runbook_md, real_acceptance_runbook_json, real_acceptance_runbook_csv]:
        expected = rel(path)
        actual = "present" if expected and expected in status_text else "missing"
        add(
            rows,
            f"status_report_references_{Path(expected).name if expected else 'missing'}",
            bool(expected and expected in status_text),
            expected,
            actual,
            "Status report should point at the current real acceptance runbook.",
        )

    for path in [real_acceptance_sequence_summary, real_acceptance_sequence_md, real_acceptance_sequence_json, real_acceptance_sequence_csv]:
        expected = rel(path)
        actual = "present" if expected and expected in status_text else "missing"
        add(
            rows,
            f"status_report_references_{Path(expected).name if expected else 'missing'}",
            bool(expected and expected in status_text),
            expected,
            actual,
            "Status report should point at the current safe real acceptance sequence entry evidence.",
        )

    for path in [protocol_contract_md, protocol_contract_json, protocol_contract_csv]:
        expected = rel(path)
        actual = "present" if expected and expected in status_text else "missing"
        add(
            rows,
            f"status_report_references_{Path(expected).name if expected else 'missing'}",
            bool(expected and expected in status_text),
            expected,
            actual,
            "Status report should point at the current RFCM protocol contract evidence.",
        )

    for path in [ps_lwip_bridge_static_md, ps_lwip_bridge_static_json, ps_lwip_bridge_static_csv]:
        expected = rel(path)
        actual = "present" if expected and expected in status_text else "missing"
        add(
            rows,
            f"status_report_references_{Path(expected).name if expected else 'missing'}",
            bool(expected and expected in status_text),
            expected,
            actual,
            "Status report should point at the current structured PS lwIP bridge static source evidence.",
        )

    for path in [ps_pc_offline_summary, ps_pc_offline_unittest, ps_pc_offline_acceptance]:
        expected = rel(path)
        actual = "present" if expected and expected in status_text else "missing"
        add(
            rows,
            f"status_report_references_{Path(expected).name if expected else 'missing'}",
            bool(expected and expected in status_text),
            expected,
            actual,
            "Status report should point at the current PS/PC offline robustness gate evidence.",
        )

    for path in [drc_release_gate_md, drc_release_gate_json, drc_release_gate_csv]:
        expected = rel(path)
        actual = "present" if expected and expected in status_text else "missing"
        add(
            rows,
            f"status_report_references_{Path(expected).name if expected else 'missing'}",
            bool(expected and expected in status_text),
            expected,
            actual,
            "Status report should point at the current DRC release gate evidence.",
        )

    add(
        rows,
        "matrix_meta_uses_latest_post_gate",
        meta_path(matrix_payload, "post_summary") == rel(post_summary)
        and meta_path(matrix_payload, "post_cases") == rel(post_cases),
        f"{rel(post_summary)} / {rel(post_cases)}",
        f"{meta_path(matrix_payload, 'post_summary')} / {meta_path(matrix_payload, 'post_cases')}",
        "Acceptance matrix should be generated from the latest post-G1 gate.",
    )
    add(
        rows,
        "matrix_meta_uses_latest_no_ethernet_gate",
        meta_path(matrix_payload, "no_ethernet_summary") == rel(no_eth_summary)
        and meta_path(matrix_payload, "no_ethernet_csv") == rel(no_eth_cases),
        f"{rel(no_eth_summary)} / {rel(no_eth_cases)}",
        f"{meta_path(matrix_payload, 'no_ethernet_summary')} / {meta_path(matrix_payload, 'no_ethernet_csv')}",
        "Acceptance matrix should be generated from the latest no-Ethernet gate.",
    )
    add(
        rows,
        "matrix_meta_records_no_ethernet_network_boundary",
        meta_path(matrix_payload, "no_ethernet_boundary") == rel(no_eth_boundary_md)
        and meta_path(matrix_payload, "no_ethernet_boundary_csv") == rel(no_eth_boundary_csv)
        and "RF_COMM_NO_ETHERNET_NETWORK_BOUNDARY_EVIDENCE overall=PASS_OFFLINE_NETWORK_BOUNDARY checks=8"
        in no_eth_boundary_text
        and '"overall": "PASS_OFFLINE_NETWORK_BOUNDARY"' in no_eth_boundary_json_text
        and "fragmented_and_coalesced_tcp_frames,PASS" in no_eth_boundary_csv_text,
        f"{rel(no_eth_boundary_md)} / {rel(no_eth_boundary_csv)}",
        f"{meta_path(matrix_payload, 'no_ethernet_boundary')} / {meta_path(matrix_payload, 'no_ethernet_boundary_csv')}",
        "Acceptance matrix should reference the current no-Ethernet TCP boundary evidence, not only the dated offline gate.",
    )
    add(
        rows,
        "matrix_meta_records_ps_lwip_bridge_static",
        meta_path(matrix_payload, "ps_lwip_bridge_static") == rel(ps_lwip_bridge_static_md)
        and meta_path(matrix_payload, "ps_lwip_bridge_static_csv") == rel(ps_lwip_bridge_static_csv)
        and "N02" in matrix_text
        and (
            rel(ps_lwip_bridge_static_md) in matrix_text
            or rel(ps_lwip_bridge_static_md).replace("/", "\\") in matrix_text
        ),
        f"{rel(ps_lwip_bridge_static_md)} / {rel(ps_lwip_bridge_static_csv)}",
        f"{meta_path(matrix_payload, 'ps_lwip_bridge_static')} / {meta_path(matrix_payload, 'ps_lwip_bridge_static_csv')}",
        "Acceptance matrix should tie N02 DHCP/static source readiness directly to the structured PS lwIP bridge static report.",
    )
    add(
        rows,
        "audit_meta_uses_latest_post_gate",
        meta_path(audit_payload, "post_gate_summary") == rel(post_summary)
        and meta_path(audit_payload, "post_gate_csv") == rel(post_cases),
        f"{rel(post_summary)} / {rel(post_cases)}",
        f"{meta_path(audit_payload, 'post_gate_summary')} / {meta_path(audit_payload, 'post_gate_csv')}",
        "Strict audit should be generated from the latest post-G1 gate.",
    )
    add(
        rows,
        "audit_meta_uses_latest_no_ethernet_gate",
        meta_path(audit_payload, "no_ethernet_network_summary") == rel(no_eth_summary)
        and meta_path(audit_payload, "no_ethernet_network_csv") == rel(no_eth_cases),
        f"{rel(no_eth_summary)} / {rel(no_eth_cases)}",
        f"{meta_path(audit_payload, 'no_ethernet_network_summary')} / {meta_path(audit_payload, 'no_ethernet_network_csv')}",
        "Strict audit should be generated from the latest no-Ethernet gate.",
    )
    add(
        rows,
        "audit_meta_records_no_ethernet_network_boundary",
        meta_path(audit_payload, "no_ethernet_network_boundary_md") == rel(no_eth_boundary_md)
        and meta_path(audit_payload, "no_ethernet_network_boundary_json") == rel(no_eth_boundary_json)
        and meta_path(audit_payload, "no_ethernet_network_boundary_csv") == rel(no_eth_boundary_csv)
        and "| NO-ETHERNET-NETWORK-BOUNDARY |" in audit_text
        and "| PASS_OFFLINE_NO_ETHERNET | reports\\no_ethernet_network_boundary_evidence_current.md |" in audit_text,
        f"{rel(no_eth_boundary_md)} / {rel(no_eth_boundary_json)} / {rel(no_eth_boundary_csv)}",
        f"{meta_path(audit_payload, 'no_ethernet_network_boundary_md')} / {meta_path(audit_payload, 'no_ethernet_network_boundary_json')} / {meta_path(audit_payload, 'no_ethernet_network_boundary_csv')}",
        "Strict audit should reference the current no-Ethernet TCP boundary evidence.",
    )
    add(
        rows,
        "audit_meta_records_external_preconditions",
        meta_path(audit_payload, "external_preconditions_md") == rel(external_preconditions_md)
        and meta_path(audit_payload, "external_preconditions_csv") == rel(external_preconditions_csv),
        f"{rel(external_preconditions_md)} / {rel(external_preconditions_csv)}",
        f"{meta_path(audit_payload, 'external_preconditions_md')} / {meta_path(audit_payload, 'external_preconditions_csv')}",
        "Strict audit should reference the current read-only external precondition snapshot.",
    )
    add(
        rows,
        "audit_meta_records_real_acceptance_runbook",
        meta_path(audit_payload, "real_acceptance_runbook_md") == rel(real_acceptance_runbook_md)
        and meta_path(audit_payload, "real_acceptance_runbook_csv") == rel(real_acceptance_runbook_csv),
        f"{rel(real_acceptance_runbook_md)} / {rel(real_acceptance_runbook_csv)}",
        f"{meta_path(audit_payload, 'real_acceptance_runbook_md')} / {meta_path(audit_payload, 'real_acceptance_runbook_csv')}",
        "Strict audit should reference the generated real acceptance runbook.",
    )
    add(
        rows,
        "audit_meta_records_real_acceptance_sequence",
        meta_path(audit_payload, "real_acceptance_sequence_md") == rel(real_acceptance_sequence_md)
        and meta_path(audit_payload, "real_acceptance_sequence_csv") == rel(real_acceptance_sequence_csv),
        f"{rel(real_acceptance_sequence_md)} / {rel(real_acceptance_sequence_csv)}",
        f"{meta_path(audit_payload, 'real_acceptance_sequence_md')} / {meta_path(audit_payload, 'real_acceptance_sequence_csv')}",
        "Strict audit should reference the safe top-level real acceptance sequence entry evidence.",
    )
    add(
        rows,
        "audit_meta_records_protocol_contract",
        meta_path(audit_payload, "protocol_contract_md") == rel(protocol_contract_md)
        and meta_path(audit_payload, "protocol_contract_csv") == rel(protocol_contract_csv),
        f"{rel(protocol_contract_md)} / {rel(protocol_contract_csv)}",
        f"{meta_path(audit_payload, 'protocol_contract_md')} / {meta_path(audit_payload, 'protocol_contract_csv')}",
        "Strict audit should reference the current RFCM protocol contract evidence.",
    )
    add(
        rows,
        "audit_meta_records_ps_lwip_bridge_static",
        meta_path(audit_payload, "ps_lwip_bridge_static_md") == rel(ps_lwip_bridge_static_md)
        and meta_path(audit_payload, "ps_lwip_bridge_static_csv") == rel(ps_lwip_bridge_static_csv),
        f"{rel(ps_lwip_bridge_static_md)} / {rel(ps_lwip_bridge_static_csv)}",
        f"{meta_path(audit_payload, 'ps_lwip_bridge_static_md')} / {meta_path(audit_payload, 'ps_lwip_bridge_static_csv')}",
        "Strict audit should reference the structured PS lwIP bridge static source evidence.",
    )
    add(
        rows,
        "audit_meta_records_full_system_offline_envelope",
        meta_path(audit_payload, "full_system_envelope_md") == rel(full_system_envelope_md)
        and meta_path(audit_payload, "full_system_envelope_csv") == rel(full_system_envelope_csv),
        f"{rel(full_system_envelope_md)} / {rel(full_system_envelope_csv)}",
        f"{meta_path(audit_payload, 'full_system_envelope_md')} / {meta_path(audit_payload, 'full_system_envelope_csv')}",
        "Strict audit should reference the full-system offline target-envelope evidence.",
    )
    add(
        rows,
        "audit_meta_records_real_acceptance_validator_selftest",
        meta_path(audit_payload, "real_acceptance_validator_selftest_md") == rel(real_acceptance_validator_selftest_md)
        and meta_path(audit_payload, "real_acceptance_validator_selftest_csv") == rel(real_acceptance_validator_selftest_csv),
        f"{rel(real_acceptance_validator_selftest_md)} / {rel(real_acceptance_validator_selftest_csv)}",
        f"{meta_path(audit_payload, 'real_acceptance_validator_selftest_md')} / {meta_path(audit_payload, 'real_acceptance_validator_selftest_csv')}",
        "Strict audit should reference the validator self-test evidence.",
    )
    add(
        rows,
        "audit_meta_records_real_acceptance_promotion_gate",
        meta_path(audit_payload, "real_acceptance_promotion_gate_md") == rel(real_acceptance_promotion_gate_md)
        and meta_path(audit_payload, "real_acceptance_promotion_gate_csv") == rel(real_acceptance_promotion_gate_csv),
        f"{rel(real_acceptance_promotion_gate_md)} / {rel(real_acceptance_promotion_gate_csv)}",
        f"{meta_path(audit_payload, 'real_acceptance_promotion_gate_md')} / {meta_path(audit_payload, 'real_acceptance_promotion_gate_csv')}",
        "Strict audit should reference the real-acceptance promotion gate evidence.",
    )
    add(
        rows,
        "audit_meta_records_duration_cap_compliance",
        meta_path(audit_payload, "duration_cap_compliance_md") == rel(duration_cap_compliance_md)
        and meta_path(audit_payload, "duration_cap_compliance_csv") == rel(duration_cap_compliance_csv),
        f"{rel(duration_cap_compliance_md)} / {rel(duration_cap_compliance_csv)}",
        f"{meta_path(audit_payload, 'duration_cap_compliance_md')} / {meta_path(audit_payload, 'duration_cap_compliance_csv')}",
        "Strict audit should reference the duration-cap compliance evidence.",
    )
    add(
        rows,
        "audit_meta_records_safe_wrapper_guard_contract",
        meta_path(audit_payload, "safe_wrapper_guard_md") == rel(safe_wrapper_guard_md)
        and meta_path(audit_payload, "safe_wrapper_guard_csv") == rel(safe_wrapper_guard_csv),
        f"{rel(safe_wrapper_guard_md)} / {rel(safe_wrapper_guard_csv)}",
        f"{meta_path(audit_payload, 'safe_wrapper_guard_md')} / {meta_path(audit_payload, 'safe_wrapper_guard_csv')}",
        "Strict audit should reference the safe-wrapper guard-contract evidence.",
    )
    add(
        rows,
        "audit_meta_records_drc_release_gate",
        meta_path(audit_payload, "drc_release_gate_md") == rel(drc_release_gate_md)
        and meta_path(audit_payload, "drc_release_gate_csv") == rel(drc_release_gate_csv),
        f"{rel(drc_release_gate_md)} / {rel(drc_release_gate_csv)}",
        f"{meta_path(audit_payload, 'drc_release_gate_md')} / {meta_path(audit_payload, 'drc_release_gate_csv')}",
        "Strict audit should reference the DRC release gate evidence.",
    )
    add(
        rows,
        "audit_meta_records_ps_pc_offline_robustness",
        meta_path(audit_payload, "ps_pc_offline_summary") == rel(ps_pc_offline_summary)
        and meta_path(audit_payload, "ps_pc_offline_unittest") == rel(ps_pc_offline_unittest)
        and meta_path(audit_payload, "ps_pc_offline_acceptance") == rel(ps_pc_offline_acceptance),
        f"{rel(ps_pc_offline_summary)} / {rel(ps_pc_offline_unittest)} / {rel(ps_pc_offline_acceptance)}",
        f"{meta_path(audit_payload, 'ps_pc_offline_summary')} / {meta_path(audit_payload, 'ps_pc_offline_unittest')} / {meta_path(audit_payload, 'ps_pc_offline_acceptance')}",
        "Strict audit should reference the current PS/PC offline robustness gate evidence.",
    )

    for path in [
        post_summary,
        post_cases,
        post_md,
        no_eth_summary,
        no_eth_cases,
        no_eth_md,
        no_eth_boundary_md,
        no_eth_boundary_json,
        no_eth_boundary_csv,
        status_md,
        matrix_md,
        matrix_json,
        audit_md,
        audit_json,
        remaining_md,
        remaining_readiness_md,
        remaining_readiness_json,
        remaining_readiness_csv,
        external_preconditions_md,
        external_preconditions_json,
        external_preconditions_csv,
        real_acceptance_runbook_md,
        real_acceptance_runbook_json,
        real_acceptance_runbook_csv,
        real_acceptance_sequence_summary,
        real_acceptance_sequence_md,
        real_acceptance_sequence_json,
        real_acceptance_sequence_csv,
        protocol_contract_md,
        protocol_contract_json,
        protocol_contract_csv,
        ps_lwip_bridge_static_md,
        ps_lwip_bridge_static_json,
        ps_lwip_bridge_static_csv,
        full_system_envelope_md,
        full_system_envelope_json,
        full_system_envelope_csv,
        rotating_dynamic_md,
        rotating_dynamic_json,
        rotating_dynamic_csv,
        real_acceptance_validator_selftest_md,
        real_acceptance_validator_selftest_json,
        real_acceptance_validator_selftest_csv,
        real_acceptance_promotion_gate_md,
        real_acceptance_promotion_gate_json,
        real_acceptance_promotion_gate_csv,
        duration_cap_compliance_md,
        duration_cap_compliance_json,
        duration_cap_compliance_csv,
        safe_wrapper_guard_md,
        safe_wrapper_guard_json,
        safe_wrapper_guard_csv,
        repeat_physical_failure_guard_md,
        repeat_physical_failure_guard_json,
        repeat_physical_failure_guard_csv,
        drc_release_gate_md,
        drc_release_gate_json,
        drc_release_gate_csv,
        ps_pc_offline_summary,
        ps_pc_offline_unittest,
        ps_pc_offline_acceptance,
    ]:
        add(
            rows,
            f"hash_manifest_tracks_{Path(rel(path)).name if path else 'missing'}",
            manifest_has_hash(manifest_text, path),
            hash_line(path),
            "present" if manifest_has_hash(manifest_text, path) else "missing",
            "Hash manifest should contain the current hash of each key evidence file.",
        )

    add(
        rows,
        "matrix_and_audit_remain_incomplete",
        "RF_COMM_TARGET_ACCEPTANCE_MATRIX overall=INCOMPLETE_REQUIREMENT_MATRIX" in matrix_text
        and "RF_COMM_FULL_TARGET_AUDIT overall=INCOMPLETE_SIM_OFFLINE_PROGRESS" in audit_text,
        "incomplete matrix and incomplete strict audit",
        "matrix_incomplete="
        + str("RF_COMM_TARGET_ACCEPTANCE_MATRIX overall=INCOMPLETE_REQUIREMENT_MATRIX" in matrix_text)
        + " audit_incomplete="
        + str("RF_COMM_FULL_TARGET_AUDIT overall=INCOMPLETE_SIM_OFFLINE_PROGRESS" in audit_text),
        "Offline progress must not be overclaimed as full target completion.",
    )
    generic_missing_audit_rows = [
        line
        for line in audit_text.splitlines()
        if "| MISSING |" in line
        and not line.startswith("| MISSING |")
        and "| STATUS-CONSISTENCY |" not in line
    ]
    add(
        rows,
        "strict_audit_has_no_generic_missing_gate",
        not generic_missing_audit_rows
        and "| REAL-ACCEPTANCE-EVIDENCE-VALIDATOR |" in audit_text
        and "| PASS_TEMPLATE_READY_NO_HARDWARE | reports\\real_acceptance_evidence_validation_current.md |" in audit_text
        and "| SAFE-WRAPPER-GUARD-CONTRACT |" in audit_text
        and "| PASS_GUARDS_STATICALLY_PROVED | reports\\safe_wrapper_guard_contract_current.md |" in audit_text
        and "| DRC-RELEASE-GATE |" in audit_text
        and "| BLOCK_RELEASE_NOT_READY_DEBUG_CAN_CONTINUE | reports\\drc_release_gate_current.md |" in audit_text
        and "Guard contract passes 25/25 checks" in audit_text,
        "strict audit should have no generic MISSING rows except the self-referential STATUS-CONSISTENCY row before the final consistency rerun",
        "present"
        if not generic_missing_audit_rows
        else "generic MISSING rows present: " + "; ".join(row[:160] for row in generic_missing_audit_rows[:3]),
        "Strict audit may still contain MISSING_HARDWARE for real external blockers, but template/validator, safe-wrapper, and DRC release evidence should not be stale generic MISSING rows.",
    )
    add(
        rows,
        "remaining_plan_waits_for_external_hardware",
        "RF_COMM_REMAINING_HARDWARE_ACCEPTANCE_PLAN overall=WAITING_FOR_EXTERNAL_HARDWARE items=5" in remaining_text,
        "WAITING_FOR_EXTERNAL_HARDWARE items=5",
        "present" if "RF_COMM_REMAINING_HARDWARE_ACCEPTANCE_PLAN overall=WAITING_FOR_EXTERNAL_HARDWARE items=5" in remaining_text else "missing",
        "Remaining plan should preserve the five real hardware/network blockers.",
    )
    add(
        rows,
        "remaining_readiness_records_unlock_actions",
        "RF_COMM_REMAINING_ACCEPTANCE_READINESS overall=BLOCKED_EXTERNAL_PRECONDITIONS items=5" in remaining_readiness_text
        and "start when" in remaining_readiness_text
        and "unlock action" in remaining_readiness_text
        and "CURRENT_BOARD_ETHERNET_CABLE_AVAILABLE=0" in remaining_readiness_text
        and "CURRENT_BOARD_ETHERNET_CONDITION_CHANGEABLE_NOW=0" in remaining_readiness_text
        and "CURRENT_NO_ETHERNET_CABLE_UNCHANGEABLE_NOW=1" in remaining_readiness_text
        and '"current_board_ethernet_cable_available": false' in remaining_readiness_json_text
        and '"current_board_ethernet_condition_changeable_now": false' in remaining_readiness_json_text
        and "current_board_ethernet_cable_unavailable" in remaining_readiness_csv_text
        and "current_board_ethernet_condition_not_changeable_now" in remaining_readiness_csv_text
        and "Connect the board Ethernet path" in remaining_readiness_text
        and "two_complete_ax7010_systems_ready;optical_lanes_ready" in remaining_readiness_csv_text
        and "real_20cm_600rpm_fixture_log_valid;rotating_optical_path_ready" in remaining_readiness_csv_text
        and "pinmap_reviewed;shutdown_bitstream_reviewed;real_8lane_tfdu_wiring_validated" in remaining_readiness_csv_text
        and '"unlock_action": "Review the 8-lane pinmap and shutdown bitstream' in remaining_readiness_json_text
        and '"safety_requirement": "Real 8-lane TFDU use requires -AllowTraffic' in remaining_readiness_json_text,
        "readiness report with current no-Ethernet boundary and per-item start_when/unlock_action/safety_requirement",
        "present"
        if "RF_COMM_REMAINING_ACCEPTANCE_READINESS overall=BLOCKED_EXTERNAL_PRECONDITIONS items=5" in remaining_readiness_text
        else "missing",
        "Remaining acceptance readiness should preserve the current no-Ethernet-cable blocker and tell the user exactly what external action unlocks each real acceptance item.",
    )
    add(
        rows,
        "full_system_offline_envelope_preserves_target_boundary",
        "RF_COMM_FULL_SYSTEM_OFFLINE_TARGET_ENVELOPE overall=PASS_OFFLINE_TARGET_ENVELOPE_NOT_HARDWARE checks=15 failures=0" in full_system_envelope_text
        and "NO_HARDWARE_PROGRAMMING=1" in full_system_envelope_text
        and "NO_UART_WRITE=1" in full_system_envelope_text
        and "NO_TFDU_DRIVE=1" in full_system_envelope_text
        and "REAL_BOARD_TCP_DHCP_ACCEPTANCE=0" in full_system_envelope_text
        and "REAL_TWO_AX7010_TRAFFIC_ACCEPTANCE=0" in full_system_envelope_text
        and "REAL_ROTATING_SHAFT_ACCEPTANCE=0" in full_system_envelope_text
        and "REAL_8LANE_TFDU_ACCEPTANCE=0" in full_system_envelope_text
        and "RAW_RATE_CLAIM_ONLY=1" in full_system_envelope_text
        and '"overall": "PASS_OFFLINE_TARGET_ENVELOPE_NOT_HARDWARE"' in full_system_envelope_json_text
        and '"failures": 0' in full_system_envelope_json_text
        and "raw_rate_target_envelope,rate,PASS" in full_system_envelope_csv_text
        and "full_duplex_4plus4_partition,lane_coverage,PASS" in full_system_envelope_csv_text
        and "rotating_dynamic_permutation_autoroute,autoroute,PASS" in full_system_envelope_csv_text
        and "network_recovery_paths,network,PASS" in full_system_envelope_csv_text
        and "real_acceptance_boundary,boundary,PASS_BOUNDARY_NOT_HARDWARE" in full_system_envelope_csv_text,
        "offline target envelope pass while real acceptance remains 0",
        "present"
        if "RF_COMM_FULL_SYSTEM_OFFLINE_TARGET_ENVELOPE overall=PASS_OFFLINE_TARGET_ENVELOPE_NOT_HARDWARE checks=15 failures=0" in full_system_envelope_text
        else "missing",
        "Full-system offline envelope should strengthen target-level model evidence without overclaiming real hardware acceptance.",
    )
    add(
        rows,
        "rotating_dynamic_permutation_autoroute_pass",
        "RF_COMM_ROTATING_DYNAMIC_PERMUTATION_AUTOROUTE overall=PASS_OFFLINE_DYNAMIC_PERMUTATION_AUTOROUTE" in rotating_dynamic_text
        and "half_pairs=64/64" in rotating_dynamic_text
        and "fdx_a_to_b_pairs=16/16" in rotating_dynamic_text
        and "fdx_b_to_a_pairs=16/16" in rotating_dynamic_text
        and "stale_cache_events=" in rotating_dynamic_text
        and "unrecovered_errors=0" in rotating_dynamic_text
        and "deadlock_events=0" in rotating_dynamic_text
        and "NO_HARDWARE_PROGRAMMING=1" in rotating_dynamic_text
        and "NO_UART_WRITE=1" in rotating_dynamic_text
        and "NO_TFDU_DRIVE=1" in rotating_dynamic_text
        and '"overall": "PASS_OFFLINE_DYNAMIC_PERMUTATION_AUTOROUTE"' in rotating_dynamic_json_text
        and '"real_rotating_shaft_acceptance": false' in rotating_dynamic_json_text
        and "half_pair_coverage_count,64" in rotating_dynamic_csv_text
        and "fdx_a_to_b_pair_coverage_count,16" in rotating_dynamic_csv_text
        and "fdx_b_to_a_pair_coverage_count,16" in rotating_dynamic_csv_text
        and ",FAIL," not in rotating_dynamic_csv_text,
        "dynamic permutation autoroute model pass with half 64/64 and FDX 16/16 pair coverage",
        "present"
        if "RF_COMM_ROTATING_DYNAMIC_PERMUTATION_AUTOROUTE overall=PASS_OFFLINE_DYNAMIC_PERMUTATION_AUTOROUTE" in rotating_dynamic_text
        else "missing",
        "Dynamic rotating model should prove offline TX/RX correspondence relearn without overclaiming real shaft acceptance.",
    )
    add(
        rows,
        "real_acceptance_validator_selftest_rejects_false_real_evidence",
        "RF_COMM_REAL_ACCEPTANCE_VALIDATOR_SELFTEST overall=PASS_VALIDATOR_REJECTS_FALSE_REAL_EVIDENCE cases=12 failures=0" in real_acceptance_validator_selftest_text
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
        and ",FAIL," not in real_acceptance_validator_selftest_csv_text,
        "validator self-test pass with 12 false-real rejection cases",
        "present"
        if "RF_COMM_REAL_ACCEPTANCE_VALIDATOR_SELFTEST overall=PASS_VALIDATOR_REJECTS_FALSE_REAL_EVIDENCE cases=12 failures=0" in real_acceptance_validator_selftest_text
        else "missing",
        "Validator self-test should prove that templates, dry-runs, missing shutdown, over-cap duration, payload overclaim, and template rotating-fixture evidence cannot be promoted to real acceptance.",
    )
    add(
        rows,
        "real_acceptance_promotion_gate_blocks_unproven_real_pass",
        "RF_COMM_REAL_ACCEPTANCE_PROMOTION_GATE overall=BLOCKED_NOT_PROMOTABLE items=5 promotable=0" in real_acceptance_promotion_gate_text
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
        and ",PROMOTABLE_TO_REAL_PASS," not in real_acceptance_promotion_gate_csv_text,
        "promotion gate blocked all five remaining real-acceptance items",
        "present"
        if "RF_COMM_REAL_ACCEPTANCE_PROMOTION_GATE overall=BLOCKED_NOT_PROMOTABLE items=5 promotable=0" in real_acceptance_promotion_gate_text
        else "missing",
        "Promotion gate should keep N03/N04/S05/A01/A02 unpromoted while Ethernet is unavailable and only template/offline evidence exists.",
    )
    add(
        rows,
        "duration_cap_compliance_enforces_600s",
        "RF_COMM_DURATION_CAP_COMPLIANCE overall=PASS_DURATION_CAP_600S checks=16 failures=0" in duration_cap_compliance_text
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
        and ",FAIL," not in duration_cap_compliance_csv_text,
        "600 s duration cap compliance gate pass",
        "present"
        if "RF_COMM_DURATION_CAP_COMPLIANCE overall=PASS_DURATION_CAP_600S checks=16 failures=0" in duration_cap_compliance_text
        else "missing",
        "Duration-cap gate should keep all physical continuous-run acceptance paths capped at 600 seconds and prevent stale 7200-second live commands.",
    )
    add(
        rows,
        "safe_wrapper_guard_contract_passes",
        "RF_COMM_SAFE_WRAPPER_GUARD_CONTRACT overall=PASS_SAFE_WRAPPER_GUARDS guards=25 failures=0" in safe_wrapper_guard_text
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
        and ",FAIL," not in safe_wrapper_guard_csv_text,
        "safe-wrapper guard contract pass with 25 static guard checks",
        "present"
        if "RF_COMM_SAFE_WRAPPER_GUARD_CONTRACT overall=PASS_SAFE_WRAPPER_GUARDS guards=25 failures=0" in safe_wrapper_guard_text
        else "missing",
        "Safe-wrapper guard contract should prove future real traffic remains gated and current no-Ethernet sequence executes zero wrappers.",
    )
    add(
        rows,
        "drc_release_gate_blocks_unready_release",
        "RF_COMM_DRC_RELEASE_GATE overall=BLOCK_RELEASE_NOT_READY_DEBUG_CAN_CONTINUE release_ready=0 debug_can_continue=1 release_blocking=2 row_failures=0" in drc_release_gate_text
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
        and ",FAIL," not in drc_release_gate_csv_text,
        "DRC release gate blocks release/4-or-8-lane expansion while allowing debug progress",
        "present"
        if "RF_COMM_DRC_RELEASE_GATE overall=BLOCK_RELEASE_NOT_READY_DEBUG_CAN_CONTINUE" in drc_release_gate_text
        else "missing",
        "DRC release gate should prevent release overclaiming while preserving debug bring-up when routed timing is clean and no critical DRC exists.",
    )
    add(
        rows,
        "repeat_physical_failure_guard_blocks_stale_retests",
        "RF_COMM_REPEAT_PHYSICAL_FAILURE_GUARD overall=BLOCK_REPEAT_FAILURE_REQUIRES_PHYSICAL_ADJUSTMENT" in repeat_physical_failure_guard_text
        and "NO_HARDWARE_PROGRAMMING=1" in repeat_physical_failure_guard_text
        and "NO_UART_WRITE=1" in repeat_physical_failure_guard_text
        and "NO_TFDU_DRIVE=1" in repeat_physical_failure_guard_text
        and '"overall": "BLOCK_REPEAT_FAILURE_REQUIRES_PHYSICAL_ADJUSTMENT"' in repeat_physical_failure_guard_json_text
        and "A_TO_B_LANE1" in repeat_physical_failure_guard_csv_text
        and "BLOCK_REPEAT_FAILURE_REQUIRES_PHYSICAL_ADJUSTMENT" in repeat_physical_failure_guard_csv_text,
        "repeat physical failure guard blocks stale A_TO_B_LANE1 retests with no side effects",
        "present"
        if "RF_COMM_REPEAT_PHYSICAL_FAILURE_GUARD overall=BLOCK_REPEAT_FAILURE_REQUIRES_PHYSICAL_ADJUSTMENT" in repeat_physical_failure_guard_text
        else "missing",
        "Repeat physical failure guard should prevent another identical real TFDU retest until physical adjustment is declared.",
    )
    add(
        rows,
        "external_preconditions_record_no_ethernet",
        "RF_COMM_EXTERNAL_PRECONDITIONS overall=BLOCKED_NO_ETHERNET" in external_preconditions_text
        and "NO_HARDWARE_PROGRAMMING=1" in external_preconditions_text
        and "NO_UART_WRITE=1" in external_preconditions_text
        and "NO_TFDU_DRIVE=1" in external_preconditions_text,
        "BLOCKED_NO_ETHERNET with no side effects",
        "present"
        if "RF_COMM_EXTERNAL_PRECONDITIONS overall=BLOCKED_NO_ETHERNET" in external_preconditions_text
        else "missing",
        "External preflight should record the current no-Ethernet condition without touching hardware.",
    )
    add(
        rows,
        "real_acceptance_runbook_waits_for_ethernet",
        "RF_COMM_REAL_ACCEPTANCE_RUNBOOK overall=WAITING_FOR_ETHERNET stages=5" in real_acceptance_runbook_text
        and "NO_HARDWARE_PROGRAMMING=1" in real_acceptance_runbook_text
        and "NO_UART_WRITE=1" in real_acceptance_runbook_text
        and "NO_TFDU_DRIVE=1" in real_acceptance_runbook_text,
        "WAITING_FOR_ETHERNET stages=5 with no side effects",
        "present"
        if "RF_COMM_REAL_ACCEPTANCE_RUNBOOK overall=WAITING_FOR_ETHERNET stages=5" in real_acceptance_runbook_text
        else "missing",
        "Generated real-acceptance runbook should preserve current no-Ethernet blocker and side-effect-free generation.",
    )
    add(
        rows,
        "real_acceptance_sequence_blocks_no_ethernet",
        "RF_COMM_REAL_ACCEPTANCE_SEQUENCE overall=BLOCKED_NO_ETHERNET stages=5" in real_acceptance_sequence_text
        and "RF_COMM_REAL_ACCEPTANCE_SEQUENCE overall=BLOCKED_NO_ETHERNET stages=5" in real_acceptance_sequence_summary_text
        and "PREFLIGHT_OVERALL=BLOCKED_NO_ETHERNET" in real_acceptance_sequence_summary_text
        and "PREFLIGHT_BLOCKERS=ethernet_link,tcp_quick_probe_single_board,tcp_quick_probe_two_ax7010" in real_acceptance_sequence_summary_text
        and "REMAINING_READINESS_OVERALL=BLOCKED_EXTERNAL_PRECONDITIONS" in real_acceptance_sequence_summary_text
        and "REMAINING_READINESS_ITEMS=5" in real_acceptance_sequence_summary_text
        and "- Remaining readiness gate: `BLOCKED_EXTERNAL_PRECONDITIONS`" in real_acceptance_sequence_text
        and '"remaining_readiness_overall":  "BLOCKED_EXTERNAL_PRECONDITIONS"' in real_acceptance_sequence_json_text
        and "EXECUTED_WRAPPERS=0" in real_acceptance_sequence_summary_text
        and "NO_HARDWARE_PROGRAMMING=1" in real_acceptance_sequence_text
        and "NO_UART_WRITE=1" in real_acceptance_sequence_text
        and "NO_TFDU_DRIVE=1" in real_acceptance_sequence_text
        and all(item_id in real_acceptance_sequence_csv_text for item_id in ["N03", "N04", "A01", "S05", "A02"])
        and real_acceptance_sequence_csv_text.count('"0","1"') >= 5
        and real_acceptance_sequence_csv_text.count("preflight_blockers=ethernet_link;tcp_quick_probe_single_board;tcp_quick_probe_two_ax7010") >= 5,
        "BLOCKED_NO_ETHERNET with readiness blockers, all five stages blocked, and zero real wrappers",
        "present"
        if "RF_COMM_REAL_ACCEPTANCE_SEQUENCE overall=BLOCKED_NO_ETHERNET stages=5" in real_acceptance_sequence_text
        else "missing",
        "Safe top-level entry should plan all five real-acceptance stages, classify remaining readiness blockers, and stop before wrappers under the current no-Ethernet condition.",
    )
    add(
        rows,
        "protocol_contract_pass",
        "RF_COMM_PROTOCOL_CONTRACT overall=PASS checks=25 status_fields=16 frame_types=9 config_bits=4" in protocol_contract_text
        and "NO_HARDWARE_PROGRAMMING=1" in protocol_contract_text
        and "NO_UART_WRITE=1" in protocol_contract_text
        and "NO_TFDU_DRIVE=1" in protocol_contract_text
        and "status_payload_layout,PASS" in protocol_contract_csv_text
        and "final_half_duplex_8lane_mask,PASS" in protocol_contract_csv_text
        and "final_full_duplex_4plus4_masks,PASS" in protocol_contract_csv_text,
        "PASS with status layout and final lane masks",
        "present"
        if "RF_COMM_PROTOCOL_CONTRACT overall=PASS" in protocol_contract_text
        else "missing",
        "RFCM protocol contract should prove PS/PC wire compatibility and final target lane-mask encodings offline.",
    )
    add(
        rows,
        "ps_lwip_bridge_static_source_pass",
        "RF_COMM_PS_LWIP_BRIDGE_STATIC overall=PASS checks=64 failures=0" in ps_lwip_bridge_static_text
        and "DHCP_SOURCE_READY=1" in ps_lwip_bridge_static_text
        and "STATIC_FALLBACK_SOURCE_READY=1" in ps_lwip_bridge_static_text
        and "TCP_BRIDGE_SOURCE_READY=1" in ps_lwip_bridge_static_text
        and "RFCM_PROTOCOL_SOURCE_READY=1" in ps_lwip_bridge_static_text
        and "NO_REAL_BOARD_TCP_DHCP=1" in ps_lwip_bridge_static_text
        and "dhcp_start,dhcp_static_network,PASS" in ps_lwip_bridge_static_csv_text
        and "tcp_new_bind_listen,tcp_connection,PASS" in ps_lwip_bridge_static_csv_text,
        "PASS with 64 source checks and explicit no-real-board boundary",
        "present"
        if "RF_COMM_PS_LWIP_BRIDGE_STATIC overall=PASS" in ps_lwip_bridge_static_text
        else "missing",
        "PS lwIP bridge static source evidence should cover DHCP/static fallback, TCP bridge behavior, RFCM source compatibility, and no-hardware boundary markers.",
    )
    add(
        rows,
        "ps_pc_offline_robustness_pass",
        "PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1" in ps_pc_offline_text
        and "PS_BRIDGE_STATIC_CHECKS_PASS checks=64 dhcp=1 tcp=1 protocol=1 reconnect=1" in ps_pc_offline_text
        and "STEP_STDERR name=host_client_unittest Ran 21 tests" in ps_pc_offline_text
        and "STEP_STDERR name=host_client_unittest OK" in ps_pc_offline_text
        and "STEP_STDOUT name=host_offline_mock_acceptance log_acceptance PASS" in ps_pc_offline_text
        and "sent_packets=64 sent_bytes=16384" in ps_pc_offline_text
        and "reconnect cycle 4/4" in ps_pc_offline_text,
        "PASS with 21 host tests, clean mock traffic, and reconnect cycles",
        "present"
        if "PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1" in ps_pc_offline_text
        else "missing",
        "PS/PC offline robustness gate should capture the expanded host protocol boundary tests.",
    )

    add(
        rows,
        "active_project_restored_2lane_port1",
        'Path="$PSRCDIR/constrs_1/new/PORT1.xdc"' in xpr_text
        and 'Name="TargetConstrsFile" Val="$PSRCDIR/constrs_1/new/PORT1.xdc"' in xpr_text
        and "[1:0]ir_rx_in_0" in wrapper_text
        and "[1:0]loop_rx_b0" in wrapper_text,
        "PORT1 target constraints and 2-lane wrapper",
        "PORT1="
        + str('Path="$PSRCDIR/constrs_1/new/PORT1.xdc"' in xpr_text)
        + " wrapper_2lane="
        + str("[1:0]ir_rx_in_0" in wrapper_text and "[1:0]loop_rx_b0" in wrapper_text),
        "Current active Vivado project should remain restored to the safe 2-lane/PORT1 state.",
    )
    add(
        rows,
        "status_report_records_no_ethernet_boundary",
        "Development board Ethernet: not connected." in status_text
        and "Do not keep retrying real network acceptance while the Ethernet link is unavailable." in status_text,
        "no-Ethernet boundary recorded",
        "present"
        if "Development board Ethernet: not connected." in status_text
        and "Do not keep retrying real network acceptance while the Ethernet link is unavailable." in status_text
        else "missing",
        "Status report should preserve the current external network boundary.",
    )

    meta = {
        "constraint": rel(constraint),
        "post_summary": rel(post_summary),
        "post_cases": rel(post_cases),
        "post_md": rel(post_md),
        "no_ethernet_summary": rel(no_eth_summary),
        "no_ethernet_cases": rel(no_eth_cases),
        "no_ethernet_md": rel(no_eth_md),
        "no_ethernet_boundary_md": rel(no_eth_boundary_md),
        "no_ethernet_boundary_json": rel(no_eth_boundary_json),
        "no_ethernet_boundary_csv": rel(no_eth_boundary_csv),
        "status_md": rel(status_md),
        "matrix_md": rel(matrix_md),
        "matrix_json": rel(matrix_json),
        "audit_md": rel(audit_md),
        "audit_json": rel(audit_json),
        "remaining_md": rel(remaining_md),
        "remaining_readiness_md": rel(remaining_readiness_md),
        "remaining_readiness_json": rel(remaining_readiness_json),
        "remaining_readiness_csv": rel(remaining_readiness_csv),
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
        "full_system_envelope_md": rel(full_system_envelope_md),
        "full_system_envelope_json": rel(full_system_envelope_json),
        "full_system_envelope_csv": rel(full_system_envelope_csv),
        "rotating_dynamic_md": rel(rotating_dynamic_md),
        "rotating_dynamic_json": rel(rotating_dynamic_json),
        "rotating_dynamic_csv": rel(rotating_dynamic_csv),
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
        "repeat_physical_failure_guard_md": rel(repeat_physical_failure_guard_md),
        "repeat_physical_failure_guard_json": rel(repeat_physical_failure_guard_json),
        "repeat_physical_failure_guard_csv": rel(repeat_physical_failure_guard_csv),
        "drc_release_gate_md": rel(drc_release_gate_md),
        "drc_release_gate_json": rel(drc_release_gate_json),
        "drc_release_gate_csv": rel(drc_release_gate_csv),
        "ps_pc_offline_summary": rel(ps_pc_offline_summary),
        "ps_pc_offline_unittest": rel(ps_pc_offline_unittest),
        "ps_pc_offline_acceptance": rel(ps_pc_offline_acceptance),
        "hash_manifest": rel(hash_manifest),
        "xpr": rel(xpr),
        "wrapper": rel(wrapper),
    }
    return rows, meta


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows, meta = build_rows()
    overall = "PASS" if all(row.status == "PASS" for row in rows) else "FAIL"
    generated = datetime.now().isoformat(timespec="seconds")
    md_path = REPORTS / "full_target_status_consistency_current.md"
    json_path = REPORTS / "full_target_status_consistency_current.json"
    csv_path = REPORTS / "full_target_status_consistency_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    md = [
        "# Full Target Status Consistency",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "",
        "This check verifies that the status report, target matrix, strict audit, remaining plan, hash manifest, and active project point at the same latest offline evidence set.",
        "",
        "## Checks",
        "",
        md_table(rows),
        "",
        "```text",
        f"RF_COMM_FULL_TARGET_STATUS_CONSISTENCY overall={overall} checks={len(rows)}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "meta": meta,
        "checks": [asdict(row) for row in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_FULL_TARGET_STATUS_CONSISTENCY overall={overall} checks={len(rows)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
