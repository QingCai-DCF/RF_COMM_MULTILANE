from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT = REPORTS / "full_target_artifacts_hashes.txt"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


EXPLICIT_PATHS = [
    "tools/update_full_target_artifact_hashes.py",
    "reports/post_g1_target_status_current.md",
    "tools/run_post_g1_target_sim_gate.ps1",
    "tools/prove_rate_boundary.py",
    "tools/model_payload_gap_closure.py",
    "tools/run_ps_pc_tcp_dhcp_acceptance_safe.ps1",
    "tools/run_two_ax7010_end_to_end_acceptance_safe.ps1",
    "tools/run_rotating_shaft_acceptance_safe.ps1",
    "tools/validate_rotating_fixture_log.py",
    "tools/validate_real_acceptance_evidence.py",
    "tools/analyze_2lane_ila_csv.py",
    "tools/classify_2lane_physical_matrix.py",
    "tools/check_2lane_ila_analyzer_selftest.py",
    "tools/build_2lane_physical_failure_snapshot.py",
    "tools/check_repeat_physical_failure_guard.py",
    "tools/check_physical_matrix_gate.ps1",
    "tools/check_physical_matrix_gate_selftest.py",
    "tools/check_real_acceptance_validator_selftest.py",
    "tools/check_real_acceptance_promotion_gate.py",
    "tools/check_duration_cap_compliance.py",
    "tools/check_safe_wrapper_guard_contract.py",
    "tools/check_plan_readiness.py",
    "tools/audit_drc_triage.py",
    "tools/check_drc_release_gate.py",
    "tools/build_drc_release_action_map.py",
    "tools/model_axi_dma_writefirst_fifo_safety.py",
    "tools/analyze_control_sets_release_blocker.py",
    "tools/report_release_personality_from_dcp.tcl",
    "tools/run_release_personality_dcp_report.ps1",
    "tools/analyze_release_personality_dcp_report.py",
    "tools/analyze_release_control_set_hotspots.py",
    "tools/query_vivado_synth_control_set_options.tcl",
    "tools/query_vivado_impl_control_set_options.tcl",
    "tools/run_active_2lane_route_methodology.ps1",
    "tools/active_2lane_route_methodology.tcl",
    "tools/run_product_loop_acceptance_safe.ps1",
    "tools/run_8lane_hardware_acceptance_safe.ps1",
    "tools/run_no_ethernet_network_offline_acceptance.ps1",
    "tools/run_p1_lane_mapping_matrix_safe.ps1",
    "tools/run_failed_2lane_links_safe.ps1",
    "tools/run_2lane_matrix_safe.ps1",
    "tools/run_2lane_hw_prearmed_ila_safe.ps1",
    "tools/build_no_ethernet_network_boundary_evidence.py",
    "tools/check_external_preconditions.py",
    "tools/build_real_acceptance_runbook.py",
    "tools/run_real_acceptance_sequence_safe.ps1",
    "tools/check_full_target_status_consistency.py",
    "tools/build_constrained_2lane_static_baseline.py",
    "tools/build_target_acceptance_matrix.py",
    "tools/build_topology_capacity_plan.py",
    "tools/build_remaining_hardware_acceptance_plan.py",
    "tools/check_remaining_acceptance_readiness.py",
    "tools/audit_full_target.py",
    "tools/check_8lane_hardware_readiness.py",
    "tools/build_8lane_candidate_pinmap.py",
    "tools/build_8lane_shutdown_candidate.py",
    "tools/check_8lane_shutdown_build.py",
    "tools/check_8lane_candidate_project_build.py",
    "tools/build_8lane_candidate_project_bitstream.tcl",
    "tools/build_8lane_a_only_candidate_xdc.py",
    "tools/build_8lane_external_project_bitstream.tcl",
    "tools/check_8lane_external_project_build.py",
    "tools/build_external_lane_scan_xdcs.py",
    "tools/run_external_lane_resource_scan.tcl",
    "tools/check_external_lane_resource_scan.py",
    "tools/check_external_resource_option_scan.py",
    "tools/run_external_reduced_lane_resource_scan.ps1",
    "tools/check_external_reduced_lane_resource_scan.py",
    "tools/check_external_reduced_5to8_extension_scan.py",
    "tools/check_external_reduced_5lane_frag32_scan.py",
    "tools/run_external_reduced_2lane_route_build.ps1",
    "tools/run_external_reduced_4lane_route_build.ps1",
    "tools/run_external_reduced_5lane_frag32_route_build.ps1",
    "tools/build_external_reduced_2lane_route.tcl",
    "tools/run_external_reduced_5lane_frag32_bitstream.ps1",
    "tools/write_external_reduced_5lane_frag32_bitstream.tcl",
    "tools/check_external_reduced_5lane_frag32_bitstream.py",
    "tools/run_external_reduced_8lane_frag16_route_build.ps1",
    "tools/run_external_reduced_8lane_frag16_bitstream.ps1",
    "tools/write_external_reduced_8lane_frag16_bitstream.tcl",
    "tools/check_external_reduced_8lane_frag16_bitstream.py",
    "tools/check_external_reduced_2lane_route.py",
    "tools/write_external_reduced_4lane_bitstream.ps1",
    "tools/write_external_reduced_4lane_bitstream.tcl",
    "tools/check_external_reduced_4lane_bitstream.py",
    "tools/build_external_reduced_4lane_bringup_plan.py",
    "tools/configure_lane0_ab_hw_loopback.tcl",
    "tools/model_full_system_capped_soak.py",
    "tools/model_rotating_dynamic_permutation_autoroute.py",
    "tools/check_full_system_offline_target_envelope.py",
    "tools/build_rotating_autoroute_offline_evidence.py",
    "software/host_client/rf_comm_client.py",
    "software/host_client/test_rf_comm_client.py",
    "software/host_client/mock_rfcm_server.py",
    "software/host_client/check_protocol_contract.py",
    "software/host_client/run_acceptance.ps1",
    "software/host_client/two_ax7010_end_to_end_model.py",
    "software/host_client/build_host_status_snapshot.py",
    "software/host_client/network_fault_recovery_model.py",
    "software/ps_lwip_bridge/check_ps_bridge_static.py",
    "software/README.md",
    "software/ps_lwip_bridge/README.md",
    "software/_boot/BOOT.BIN",
    "software/_boot/rf_comm_boot.bif",
    "software/_boot_ps_ps_loopback/BOOT.BIN",
    "software/_boot_ps_ps_loopback/rf_comm_ps_ps_loopback.bif",
    "IPs/ip_ir_array/run_loopback_single_lane.ps1",
    "IPs/ip_ir_array/src/ir_array_top.sv",
    "IPs/ip_ir_array/src/ir_array_top_axi.sv",
    "IPs/ip_ir_array/src/ir_rx_4ppm_frame.sv",
    "IPs/ip_ir_array/src/ir_lane_frame_sink.sv",
    "IPs/ip_ir_array/src/ir_lane_frame_source.sv",
    "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.xpr",
    "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/sources_1/bd/design_shiboqi/design_shiboqi.bd",
    "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/sources_1/imports/hdl/design_shiboqi_wrapper.v",
    "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/target_ir_array_8lane_candidate.xdc",
    "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/target_ir_array_8lane_a_only_candidate.xdc",
    "tools/tfdu_shutdown_8lane_candidate_top.v",
    "tools/tfdu_shutdown_8lane_candidate.xdc",
    "tools/build_tfdu_shutdown_8lane_candidate.tcl",
    "tools/program_tfdu_shutdown_8lane_candidate.tcl",
    "shutdown_bitstream/tfdu_shutdown_8lane_candidate.bit",
    "shutdown_bitstream/tfdu_shutdown_8lane_candidate_routed.dcp",
    "shutdown_bitstream/tfdu_shutdown_8lane_candidate_drc.rpt",
    "shutdown_bitstream/tfdu_shutdown_8lane_candidate_timing_summary.rpt",
    "shutdown_bitstream/tfdu_shutdown_8lane_candidate_io.rpt",
    "shutdown_bitstream/tfdu_shutdown_8lane_candidate_utilization.rpt",
]


GLOB_PATTERNS = [
    "IPs/ip_ir_array/sim/tb_ir_array_loopback_8lane*.sv",
    "IPs/ip_ir_array/sim/tb_ir_rotating_autoroute_8lane_soak_model.sv",
    "IPs/ip_ir_array/sim/tb_ir_array_loopback_full_duplex_lane_partition.sv",
    "IPs/ip_ir_array/sim/tb_ir_phy_rate_model.sv",
    "IPs/ip_ir_array/sim/tb_ir_payload_throughput_budget.sv",
    "reports/post_g1_target_sim_gate_20260627_*",
    "reports/post_g1_target_sim_gate_20260627_*/*",
    "reports/rtl_reset_trim_post_g1_gate_20260627_*.*",
    "reports/rtl_reset_trim_8lane_route_driver_20260627_*.*",
    "reports/rtl_sink_common_enable_post_g1_gate_20260627_*.*",
    "reports/rtl_sink_common_enable_8lane_route_driver_20260627_*.*",
    "reports/rx_reset_trim_post_g1_gate_20260627_*.*",
    "reports/rx_reset_trim_8lane_route_driver_20260627_*.*",
    "reports/rx_reset_trim_disablecache_8lane_route_driver_20260627_*.*",
    "reports/rx_reset_restore_disablecache_8lane_route_driver_20260627_*.*",
    "reports/rx_reset_restore_post_g1_gate_20260627_*.*",
    "reports/sink_shift_post_g1_gate_20260627_*.*",
    "reports/sink_shift_disablecache_8lane_route_driver_20260627_*.*",
    "reports/sink_shift_external_reduced_8lane_frag16_route_current.*",
    "reports/sink_shift_restore_disablecache_8lane_route_driver_20260627_*.*",
    "reports/sink_shift_restore_post_g1_gate_20260627_*.*",
    "reports/rate_boundary_proof_20260627*",
    "reports/rate_boundary_proof_manual_20260627.json",
    "reports/payload_gap_closure_current.*",
    "reports/full_system_capped_digital_twin_manual_20260627.json",
    "reports/full_system_capped_digital_twin_current.*",
    "reports/full_system_offline_target_envelope_current.*",
    "reports/rotating_autoroute_offline_evidence_current.*",
    "reports/rotating_dynamic_permutation_autoroute_current.*",
    "reports/two_ax7010_end_to_end_model_current.*",
    "reports/host_status_snapshot_current.*",
    "reports/two_ax7010_end_to_end_model_current/*.csv",
    "reports/two_ax7010_end_to_end_model_current/*.log",
    "reports/effective_payload_rate_options_20260626.*",
    "reports/target_consistency_check_20260626.*",
    "reports/full_target_status_consistency_current.*",
    "reports/drc_triage_current_20260626.*",
    "reports/drc_release_gate_current.*",
    "reports/drc_release_action_map_current.*",
    "reports/axi_dma_writefirst_fifo_safety_current.*",
    "reports/control_sets_release_blocker_current.*",
    "reports/release_personality_dcp_evidence_current.*",
    "reports/release_control_set_hotspots_current.*",
    "reports/query_vivado_synth_control_set_options.*",
    "reports/query_vivado_impl_control_set_options.*",
    "reports/release_personality_dcp_report_20260627_*.*",
    "reports/release_personality_dcp_report_20260627_*/*",
    "reports/active_2lane_route_methodology_20260627_*.*",
    "reports/active_2lane_route_methodology_20260627_*/*",
    "reports/constrained_2lane_static_plan_review_current.md",
    "reports/constrained_2lane_static_baseline_current.summary.txt",
    "reports/constrained_2lane_static_baseline_manifest_current.*",
    "reports/constrained_2lane_static_acceptance_matrix_current.*",
    "reports/external_preconditions_current.*",
    "reports/real_acceptance_runbook_current.*",
    "reports/real_acceptance_sequence_safe_current.*",
    "reports/real_acceptance_sequence_safe_20260627_*",
    "reports/protocol_contract_current.*",
    "reports/ps_lwip_bridge_static_current.*",
    "reports/ps_pc_offline_gates_20260627_*",
    "reports/ps_pc_offline_acceptance_20260627_*/*.csv",
    "reports/ps_pc_offline_acceptance_20260627_*/*.log",
    "reports/target_acceptance_matrix_current.*",
    "reports/topology_capacity_plan_current.*",
    "reports/remaining_hardware_acceptance_plan_current.*",
    "reports/remaining_acceptance_readiness_current.*",
    "reports/8lane_hardware_readiness_current.*",
    "reports/8lane_candidate_pinmap_current.*",
    "reports/8lane_shutdown_candidate_current.*",
    "reports/8lane_shutdown_build_current.*",
    "reports/8lane_candidate_project_build_current.*",
    "reports/8lane_a_only_candidate_xdc_current.*",
    "reports/8lane_external_project_build_current.*",
    "reports/external_lane_scan_xdcs_current.*",
    "reports/external_lane_scan_xdcs/*.xdc",
    "reports/external_lane_resource_scan_current.*",
    "reports/external_lane_resource_scan_20260627_024421.*",
    "reports/external_lane_resource_scan_20260627_024421/lane_*/drc_opted.rpt",
    "reports/external_lane_resource_scan_20260627_024421/lane_*/impl_1_runme.log",
    "reports/external_lane_resource_scan_20260627_024421/lane_*/synth_1_runme.log",
    "reports/external_resource_option_scan_current.*",
    "reports/external_resource_option_scan_20260627_032528.*",
    "reports/external_resource_option_scan_20260627_032528/lane_*/drc_opted.rpt",
    "reports/external_resource_option_scan_20260627_032528/lane_*/impl_1_runme.log",
    "reports/external_resource_option_scan_20260627_032528/lane_*/synth_1_runme.log",
    "reports/external_reduced_lane_resource_scan_current.*",
    "reports/external_reduced_lane_resource_scan_20260627_035349.*",
    "reports/external_reduced_lane_resource_scan_20260627_035349/lane_*/drc_opted.rpt",
    "reports/external_reduced_lane_resource_scan_20260627_035349/lane_*/impl_1_runme.log",
    "reports/external_reduced_lane_resource_scan_20260627_035349/lane_*/synth_1_runme.log",
    "reports/external_reduced_lane_resource_scan_20260627_035349/lane_*/utilization_synth.rpt",
    "reports/external_reduced_5to8_extension_current.*",
    "reports/external_reduced_5lane_frag32_current.*",
    "reports/external_reduced_5lane_frag32_route_current.*",
    "reports/external_reduced_5lane_frag32_bitstream_current.*",
    "reports/external_reduced_8lane_frag16_route_current.*",
    "reports/release_reroute_driver_20260627_*.*",
    "reports/external_reduced_8lane_frag16_bitstream_current.*",
    "reports/external_reduced_lane_scan_5to8_wrapper_20260627_051238.*",
    "reports/external_reduced_lane_scan_5to8_wrapper_20260627_051257.*",
    "reports/external_reduced_lane_resource_scan_20260627_051257.*",
    "reports/external_reduced_lane_resource_scan_20260627_051257/lane_*/drc_opted.rpt",
    "reports/external_reduced_lane_resource_scan_20260627_051257/lane_*/impl_1_runme.log",
    "reports/external_reduced_lane_resource_scan_20260627_051257/lane_*/synth_1_runme.log",
    "reports/external_reduced_lane_resource_scan_20260627_051257/lane_*/utilization_synth.rpt",
    "reports/external_reduced_lane_resource_scan_20260627_055032.*",
    "reports/external_reduced_lane_resource_scan_20260627_055032/lane_*/drc_opted.rpt",
    "reports/external_reduced_lane_resource_scan_20260627_055032/lane_*/impl_1_runme.log",
    "reports/external_reduced_lane_resource_scan_20260627_055032/lane_*/synth_1_runme.log",
    "reports/external_reduced_lane_resource_scan_20260627_055032/lane_*/utilization_synth.rpt",
    "reports/external_reduced_lane_resource_scan_20260627_055814.*",
    "reports/external_reduced_lane_resource_scan_20260627_055814/lane_*/control_sets_placed.rpt",
    "reports/external_reduced_lane_resource_scan_20260627_055814/lane_*/drc_opted.rpt",
    "reports/external_reduced_lane_resource_scan_20260627_055814/lane_*/impl_1_runme.log",
    "reports/external_reduced_lane_resource_scan_20260627_055814/lane_*/io_placed.rpt",
    "reports/external_reduced_lane_resource_scan_20260627_055814/lane_*/synth_1_runme.log",
    "reports/external_reduced_lane_resource_scan_20260627_055814/lane_*/utilization_placed.rpt",
    "reports/external_reduced_lane_resource_scan_20260627_055814/lane_*/utilization_synth.rpt",
    "reports/external_reduced_lane5_frag32_launcher_20260627_055814.*",
    "reports/build_external_reduced_5lane_frag32_route_20260627_061115.*",
    "reports/build_external_reduced_5lane_frag32_route_20260627_061115/*",
    "reports/external_reduced_5lane_frag32_route_launcher_20260627_061115.*",
    "reports/external_reduced_5lane_frag32_bitstream_20260627_062308.*",
    "reports/external_reduced_5lane_frag32_bitstream_20260627_062308/*",
    "reports/external_reduced_5lane_frag32_bitstream_launcher_20260627_062308.*",
    "reports/external_reduced_lane_resource_scan_20260627_063315.*",
    "reports/external_reduced_lane_resource_scan_20260627_063315/*",
    "reports/external_reduced_lane_resource_scan_20260627_063728.*",
    "reports/external_reduced_lane_resource_scan_20260627_063728/*",
    "reports/build_external_reduced_8lane_frag16_route_20260627_*.*",
    "reports/build_external_reduced_8lane_frag16_route_20260627_*/*",
    "reports/release_controlset16_route_driver_20260627_*.*",
    "reports/external_reduced_8lane_frag16_bitstream_20260627_*.*",
    "reports/external_reduced_8lane_frag16_bitstream_20260627_*/*",
    "reports/restore_active_2lane_after_5to8_scan_20260627_053636.*",
    "reports/external_reduced_2lane_route_current.*",
    "reports/build_external_reduced_2lane_route_20260627_034122.*",
    "reports/build_external_reduced_2lane_route_20260627_034122/*",
    "reports/external_reduced_4lane_route_current.*",
    "reports/build_external_reduced_4lane_route_20260627_041301.*",
    "reports/build_external_reduced_4lane_route_20260627_041301/*",
    "reports/external_reduced_4lane_bitstream_current.*",
    "reports/external_reduced_4lane_bitstream_20260627_042242.*",
    "reports/external_reduced_4lane_bitstream_20260627_042242/*",
    "reports/external_reduced_4lane_bringup_plan_current.*",
    "reports/build_tfdu_shutdown_8lane_candidate_20260627_014859.*",
    "reports/build_8lane_candidate_project_20260627_020747.*",
    "reports/build_8lane_external_project_20260627_022301.*",
    "reports/restore_2lane_stream_bidir_20260627_023647.*",
    "reports/boot_artifact_audit_current.*",
    "reports/host_acceptance_runtime_cap_20260627.md",
    "reports/failed_2lane_links_safe_*.summary.txt",
    "reports/ps_pc_tcp_dhcp_acceptance_safe_20260627_*.summary.txt",
    "reports/ps_pc_tcp_dhcp_acceptance_safe_20260627_*.md",
    "reports/two_ax7010_end_to_end_acceptance_safe_20260627_*.summary.txt",
    "reports/two_ax7010_end_to_end_acceptance_safe_20260627_*.md",
    "reports/two_ax7010_end_to_end_acceptance_safe_20260627_*.criteria.csv",
    "reports/rotating_shaft_acceptance_safe_20260627_*",
    "reports/rotating_fixture_log_template.csv",
    "reports/rotating_fixture_log_validation_current.*",
    "reports/real_acceptance_evidence_validation_current.*",
    "reports/real_acceptance_validator_selftest_current.*",
    "reports/real_acceptance_validator_selftest_current/*",
    "reports/ila_analyzer_selftest_current.*",
    "reports/ila_analyzer_selftest_current/*",
    "reports/2lane_physical_failure_snapshot_current.*",
    "reports/repeat_physical_failure_guard_current.*",
    "reports/repeat_physical_failure_guard_20260627_*",
    "reports/physical_matrix_gate_selftest_current.*",
    "reports/physical_matrix_gate_selftest_current/*",
    "reports/plan_readiness_current.*",
    "reports/real_acceptance_promotion_gate_current.*",
    "reports/duration_cap_compliance_current.*",
    "reports/safe_wrapper_guard_contract_current.*",
    "reports/real_acceptance_template/*",
    "reports/network_fault_recovery_model_current.*",
    "reports/product_loop_acceptance_safe_20260627_*",
    "reports/8lane_hardware_acceptance_safe_20260627_*",
    "reports/no_ethernet_network_offline_acceptance_20260627_*",
    "reports/no_ethernet_network_boundary_evidence_current.*",
    "reports/full_target_audit_current_20260626.*",
    "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/synth_1/runme.log",
    "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/impl_1/runme.log",
    "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/impl_1/design_shiboqi_wrapper_drc_opted.rpt",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT)).replace("\\", "/")


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def collect_paths() -> list[Path]:
    paths: dict[str, Path] = {}
    for item in EXPLICIT_PATHS:
        path = ROOT / item
        if path.exists() and path.is_file():
            paths[rel(path)] = path
    for pattern in GLOB_PATTERNS:
        for path in ROOT.glob(pattern):
            if path.exists() and path.is_file():
                paths[rel(path)] = path
    return [paths[key] for key in sorted(paths)]


def latest_path(pattern: str) -> Path | None:
    matches = [path for path in ROOT.glob(pattern) if path.exists() and path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def first_marker(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return match.group(0) if match else "MISSING"


def first_marker_any(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        marker = first_marker(text, pattern)
        if marker != "MISSING":
            return marker
    return "MISSING"


def find_constraint_file() -> Path:
    candidates = [
        ROOT / "\u9879\u76ee\u7ea6\u675f(\u76ee\u6807\uff09.txt",
        ROOT / "\u9879\u76ee\u7ea6\u675f(\u76ee\u6807).txt",
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    for path in ROOT.glob("*.txt"):
        if path.is_file():
            try:
                if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
                    return path
            except OSError:
                continue
    raise FileNotFoundError("hard project constraint file was not found")


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    constraint = find_constraint_file()
    paths = collect_paths()
    audit_text = read_text(REPORTS / "full_target_audit_current_20260626.md")
    readiness_text = read_text(REPORTS / "8lane_hardware_readiness_current.md")
    external_scan_text = read_text(REPORTS / "external_lane_resource_scan_current.md")
    external_option_text = read_text(REPORTS / "external_resource_option_scan_current.md")
    external_reduced_lane_text = read_text(REPORTS / "external_reduced_lane_resource_scan_current.md")
    external_reduced_5to8_text = read_text(REPORTS / "external_reduced_5to8_extension_current.md")
    external_reduced_5lane_frag32_text = read_text(REPORTS / "external_reduced_5lane_frag32_current.md")
    external_reduced_5lane_frag32_route_text = read_text(REPORTS / "external_reduced_5lane_frag32_route_current.md")
    external_reduced_5lane_frag32_bitstream_text = read_text(REPORTS / "external_reduced_5lane_frag32_bitstream_current.md")
    external_reduced_8lane_frag16_route_text = read_text(REPORTS / "external_reduced_8lane_frag16_route_current.md")
    external_reduced_8lane_frag16_bitstream_text = read_text(REPORTS / "external_reduced_8lane_frag16_bitstream_current.md")
    external_route_text = read_text(REPORTS / "external_reduced_2lane_route_current.md")
    external_route_4lane_text = read_text(REPORTS / "external_reduced_4lane_route_current.md")
    external_bitstream_4lane_text = read_text(REPORTS / "external_reduced_4lane_bitstream_current.md")
    external_bringup_4lane_text = read_text(REPORTS / "external_reduced_4lane_bringup_plan_current.md")
    topology_capacity_text = read_text(REPORTS / "topology_capacity_plan_current.md")
    full_system_offline_envelope_text = read_text(REPORTS / "full_system_offline_target_envelope_current.md")
    rotating_autoroute_offline_text = read_text(REPORTS / "rotating_autoroute_offline_evidence_current.md")
    rotating_dynamic_text = read_text(REPORTS / "rotating_dynamic_permutation_autoroute_current.md")
    rotating_fixture_text = read_text(REPORTS / "rotating_fixture_log_validation_current.md")
    real_acceptance_evidence_text = read_text(REPORTS / "real_acceptance_evidence_validation_current.md")
    real_acceptance_validator_selftest_text = read_text(REPORTS / "real_acceptance_validator_selftest_current.md")
    ila_analyzer_selftest_text = read_text(REPORTS / "ila_analyzer_selftest_current.md")
    physical_failure_snapshot_text = read_text(REPORTS / "2lane_physical_failure_snapshot_current.md")
    repeat_physical_failure_guard_text = read_text(REPORTS / "repeat_physical_failure_guard_current.md")
    physical_matrix_gate_selftest_text = read_text(REPORTS / "physical_matrix_gate_selftest_current.md")
    real_acceptance_promotion_gate_text = read_text(REPORTS / "real_acceptance_promotion_gate_current.md")
    duration_cap_text = read_text(REPORTS / "duration_cap_compliance_current.md")
    safe_wrapper_guard_text = read_text(REPORTS / "safe_wrapper_guard_contract_current.md")
    network_fault_text = read_text(REPORTS / "network_fault_recovery_model_current.md")
    network_boundary_text = read_text(REPORTS / "no_ethernet_network_boundary_evidence_current.md")
    status_consistency_text = read_text(REPORTS / "full_target_status_consistency_current.md")
    axi_dma_fifo_safety_text = read_text(REPORTS / "axi_dma_writefirst_fifo_safety_current.md")
    control_sets_release_text = read_text(REPORTS / "control_sets_release_blocker_current.md")
    release_personality_text = read_text(REPORTS / "release_personality_dcp_evidence_current.md")
    external_preconditions_text = read_text(REPORTS / "external_preconditions_current.md")
    real_acceptance_runbook_text = read_text(REPORTS / "real_acceptance_runbook_current.md")
    real_acceptance_sequence_text = read_text(REPORTS / "real_acceptance_sequence_safe_current.md")
    real_acceptance_sequence_summary_text = read_text(REPORTS / "real_acceptance_sequence_safe_current.summary.txt")
    protocol_contract_text = read_text(REPORTS / "protocol_contract_current.md")
    ps_pc_offline_text = read_text(latest_path("reports/ps_pc_offline_gates_*.summary.txt"))
    rotating_shaft_text = read_text(latest_path("reports/rotating_shaft_acceptance_safe_*.summary.txt"))
    product_loop_text = read_text(latest_path("reports/product_loop_acceptance_safe_*.summary.txt"))
    eightlane_hw_text = read_text(latest_path("reports/8lane_hardware_acceptance_safe_*.summary.txt"))
    failed_link_retest_text = read_text(latest_path("reports/failed_2lane_links_safe_*.summary.txt"))
    remaining_text = read_text(REPORTS / "remaining_hardware_acceptance_plan_current.md")
    remaining_readiness_text = read_text(REPORTS / "remaining_acceptance_readiness_current.md")
    plan_readiness_text = read_text(REPORTS / "plan_readiness_current.md")

    lines = [
        "RF_COMM full target artifact hashes",
        f"Generated: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %z')}",
        "",
        "Hard constraint:",
        f"{sha256(constraint)}  {rel(constraint)}",
        "",
        "Tracked artifacts:",
    ]
    for path in paths:
        lines.append(f"{sha256(path)}  {rel(path)}")

    lines.extend(
        [
            "",
            "Latest strict audit verdict:",
            first_marker(audit_text, r"RF_COMM_FULL_TARGET_AUDIT overall=\S+"),
            "",
            "8-lane hardware readiness:",
            first_marker(readiness_text, r"RF_COMM_8LANE_HARDWARE_READINESS overall=\S+.*"),
            "",
            "External A-only lane resource scan:",
            first_marker(external_scan_text, r"RF_COMM_EXTERNAL_LANE_RESOURCE_SCAN overall=\S+.*"),
            "",
            "External A-only reduced-resource option scan:",
            first_marker(external_option_text, r"RF_COMM_EXTERNAL_RESOURCE_OPTION_SCAN overall=\S+.*"),
            "",
            "External A-only reduced-resource 1..4 lane scan:",
            first_marker(external_reduced_lane_text, r"RF_COMM_EXTERNAL_REDUCED_LANE_RESOURCE_SCAN overall=\S+.*"),
            "",
            "External A-only reduced-resource 5..8 extension boundary:",
            first_marker(external_reduced_5to8_text, r"RF_COMM_EXTERNAL_REDUCED_5TO8_EXTENSION overall=\S+.*"),
            "",
            "External A-only reduced-resource 5-lane fragment=32 probe:",
            first_marker(external_reduced_5lane_frag32_text, r"RF_COMM_EXTERNAL_REDUCED_5LANE_FRAG32 overall=\S+.*"),
            "",
            "External A-only reduced-resource 5-lane fragment=32 route:",
            first_marker(external_reduced_5lane_frag32_route_text, r"RF_COMM_EXTERNAL_REDUCED_5LANE_FRAG32_ROUTE overall=\S+.*"),
            "",
            "External A-only reduced-resource 5-lane fragment=32 candidate bitstream:",
            first_marker(external_reduced_5lane_frag32_bitstream_text, r"RF_COMM_EXTERNAL_REDUCED_5LANE_FRAG32_BITSTREAM overall=\S+.*"),
            "",
            "External A-only reduced-resource 8-lane fragment=16 route:",
            first_marker(external_reduced_8lane_frag16_route_text, r"RF_COMM_EXTERNAL_REDUCED_8LANE_FRAG16_ROUTE overall=\S+.*"),
            "",
            "External A-only reduced-resource 8-lane fragment=16 candidate bitstream:",
            first_marker(external_reduced_8lane_frag16_bitstream_text, r"RF_COMM_EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM overall=\S+.*"),
            "",
            "External A-only reduced-resource 2-lane route:",
            first_marker(external_route_text, r"RF_COMM_EXTERNAL_REDUCED_2LANE_ROUTE overall=\S+.*"),
            "",
            "External A-only reduced-resource 4-lane route:",
            first_marker(external_route_4lane_text, r"RF_COMM_EXTERNAL_REDUCED_4LANE_ROUTE overall=\S+.*"),
            "",
            "External A-only reduced-resource 4-lane candidate bitstream:",
            first_marker(external_bitstream_4lane_text, r"RF_COMM_EXTERNAL_REDUCED_4LANE_BITSTREAM overall=\S+.*"),
            "",
            "External A-only reduced-resource 4-lane bring-up plan:",
            first_marker(external_bringup_4lane_text, r"RF_COMM_EXTERNAL_REDUCED_4LANE_BRINGUP_PLAN overall=\S+.*"),
            "",
            "Topology capacity plan:",
            first_marker(topology_capacity_text, r"RF_COMM_TOPOLOGY_CAPACITY_PLAN overall=\S+.*"),
            "",
            "Full-system offline target envelope:",
            first_marker(full_system_offline_envelope_text, r"RF_COMM_FULL_SYSTEM_OFFLINE_TARGET_ENVELOPE overall=\S+.*"),
            first_marker(full_system_offline_envelope_text, r"REAL_BOARD_TCP_DHCP_ACCEPTANCE=0"),
            first_marker(full_system_offline_envelope_text, r"REAL_8LANE_TFDU_ACCEPTANCE=0"),
            "",
            "Rotating autoroute offline evidence:",
            first_marker(rotating_autoroute_offline_text, r"RF_COMM_ROTATING_AUTOROUTE_OFFLINE_EVIDENCE overall=\S+.*"),
            first_marker(rotating_autoroute_offline_text, r"REAL_ROTATING_SHAFT_ACCEPTANCE=0"),
            "",
            "Rotating dynamic TX/RX permutation autoroute model:",
            first_marker(rotating_dynamic_text, r"RF_COMM_ROTATING_DYNAMIC_PERMUTATION_AUTOROUTE overall=\S+.*"),
            first_marker(rotating_dynamic_text, r"REAL_ROTATING_SHAFT_ACCEPTANCE=0"),
            "",
            "Rotating-shaft safe acceptance wrapper latest no-drive evidence:",
            first_marker_any(rotating_shaft_text, [r"ROTATING_SHAFT_DRY_RUN=1", r"ROTATING_SHAFT_REAL_ACCEPTANCE_BLOCKED=1"]),
            first_marker(rotating_shaft_text, r"DURATION_SECONDS_EFFECTIVE=600"),
            first_marker_any(rotating_shaft_text, [r"NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1", r"NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT_FINAL=1"]),
            "",
            "Rotating fixture log validator/template:",
            first_marker(rotating_fixture_text, r"RF_COMM_ROTATING_FIXTURE_LOG_VALIDATION overall=\S+.*"),
            first_marker(rotating_fixture_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(rotating_fixture_text, r"NO_TFDU_DRIVE=1"),
            "",
            "Real acceptance evidence validator/template:",
            first_marker(real_acceptance_evidence_text, r"RF_COMM_REAL_ACCEPTANCE_EVIDENCE_VALIDATION overall=\S+.*"),
            first_marker(real_acceptance_evidence_text, r"REAL_ACCEPTANCE_EVIDENCE=0"),
            first_marker(real_acceptance_evidence_text, r"NO_TFDU_DRIVE=1"),
            "",
            "Real acceptance validator self-test:",
            first_marker(real_acceptance_validator_selftest_text, r"RF_COMM_REAL_ACCEPTANCE_VALIDATOR_SELFTEST overall=\S+.*"),
            first_marker(real_acceptance_validator_selftest_text, r"REAL_ACCEPTANCE_EVIDENCE_PRODUCED=0"),
            "",
            "Physical matrix gate self-test:",
            first_marker(ila_analyzer_selftest_text, r"RF_COMM_2LANE_ILA_ANALYZER_SELFTEST overall=\S+.*"),
            first_marker(ila_analyzer_selftest_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(ila_analyzer_selftest_text, r"NO_TFDU_DRIVE=1"),
            first_marker(physical_failure_snapshot_text, r"RF_COMM_2LANE_PHYSICAL_FAILURE_SNAPSHOT overall=\S+.*"),
            first_marker(physical_failure_snapshot_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(physical_failure_snapshot_text, r"NO_TFDU_DRIVE=1"),
            first_marker(repeat_physical_failure_guard_text, r"RF_COMM_REPEAT_PHYSICAL_FAILURE_GUARD overall=\S+.*"),
            first_marker(repeat_physical_failure_guard_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(repeat_physical_failure_guard_text, r"NO_TFDU_DRIVE=1"),
            first_marker(physical_matrix_gate_selftest_text, r"RF_COMM_PHYSICAL_MATRIX_GATE_SELFTEST overall=\S+.*"),
            first_marker(physical_matrix_gate_selftest_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(physical_matrix_gate_selftest_text, r"NO_TFDU_DRIVE=1"),
            "",
            "Failed 2-lane link targeted retest latest no-drive evidence:",
            first_marker(failed_link_retest_text, r"SELECTED_FAILED_LINKS=.*"),
            first_marker(failed_link_retest_text, r"SELECTED_TRIGGER_MODES=.*"),
            first_marker(failed_link_retest_text, r"EFFECTIVE_DRY_RUN=1"),
            first_marker(failed_link_retest_text, r"NO_TFDU_DRIVE=1"),
            "",
            "Real acceptance promotion gate:",
            first_marker(real_acceptance_promotion_gate_text, r"RF_COMM_REAL_ACCEPTANCE_PROMOTION_GATE overall=\S+.*"),
            first_marker(real_acceptance_promotion_gate_text, r"PROMOTED_TO_REAL_PASS_BY_THIS_SCRIPT=0"),
            first_marker(real_acceptance_promotion_gate_text, r"TEMPLATE_OR_DRY_RUN_PROMOTION_ALLOWED=0"),
            "",
            "Duration cap compliance:",
            first_marker(duration_cap_text, r"RF_COMM_DURATION_CAP_COMPLIANCE overall=\S+.*"),
            first_marker(duration_cap_text, r"MAX_CONTINUOUS_RUN_SECONDS=600"),
            first_marker(duration_cap_text, r"REAL_PHYSICAL_RUN_GT_600_ALLOWED=0"),
            "",
            "Safe wrapper guard contract:",
            first_marker(safe_wrapper_guard_text, r"RF_COMM_SAFE_WRAPPER_GUARD_CONTRACT overall=\S+.*"),
            first_marker(safe_wrapper_guard_text, r"WRAPPER_EXECUTION_DONE_BY_THIS_CHECK=0"),
            first_marker(safe_wrapper_guard_text, r"REAL_TRAFFIC_REQUIRES_ALLOW_TRAFFIC=1"),
            first_marker(safe_wrapper_guard_text, r"CURRENT_NO_ETHERNET_EXECUTES_ZERO_WRAPPERS=1"),
            "",
            "Network fault recovery offline model:",
            first_marker(network_fault_text, r"RF_COMM_NETWORK_FAULT_RECOVERY_MODEL overall=\S+.*"),
            first_marker(network_fault_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(network_fault_text, r"NO_TFDU_DRIVE=1"),
            "",
            "No-Ethernet network boundary evidence:",
            first_marker(network_boundary_text, r"RF_COMM_NO_ETHERNET_NETWORK_BOUNDARY_EVIDENCE overall=\S+.*"),
            first_marker(network_boundary_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(network_boundary_text, r"NO_REAL_BOARD_TCP_DHCP=1"),
            "",
            "AXI DMA WRITE_FIRST FIFO offline evidence:",
            first_marker(axi_dma_fifo_safety_text, r"RF_COMM_AXI_DMA_WRITEFIRST_FIFO_SAFETY overall=\S+.*"),
            first_marker(axi_dma_fifo_safety_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(axi_dma_fifo_safety_text, r"NO_TFDU_DRIVE=1"),
            "",
            "Control-set release blocker evidence:",
            first_marker(control_sets_release_text, r"RF_COMM_CONTROL_SETS_RELEASE_BLOCKER overall=\S+.*"),
            first_marker(control_sets_release_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(control_sets_release_text, r"NO_TFDU_DRIVE=1"),
            "",
            "Release-personality DCP evidence:",
            first_marker(release_personality_text, r"RF_COMM_RELEASE_PERSONALITY_DCP_EVIDENCE overall=\S+.*"),
            first_marker(release_personality_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(release_personality_text, r"NO_TFDU_DRIVE=1"),
            first_marker(release_personality_text, r"NO_SYNTHESIS=1"),
            first_marker(release_personality_text, r"NO_IMPLEMENTATION=1"),
            first_marker(release_personality_text, r"NO_BITSTREAM=1"),
            "",
            "Full-target status consistency gate:",
            first_marker(status_consistency_text, r"RF_COMM_FULL_TARGET_STATUS_CONSISTENCY overall=\S+.*"),
            first_marker(status_consistency_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(status_consistency_text, r"NO_TFDU_DRIVE=1"),
            "",
            "External preconditions read-only snapshot:",
            first_marker(external_preconditions_text, r"RF_COMM_EXTERNAL_PRECONDITIONS overall=\S+.*"),
            first_marker(external_preconditions_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(external_preconditions_text, r"NO_TFDU_DRIVE=1"),
            "",
            "Real acceptance runbook:",
            first_marker(real_acceptance_runbook_text, r"RF_COMM_REAL_ACCEPTANCE_RUNBOOK overall=\S+.*"),
            first_marker(real_acceptance_runbook_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(real_acceptance_runbook_text, r"NO_TFDU_DRIVE=1"),
            "",
            "Real acceptance safe sequence entry:",
            first_marker(real_acceptance_sequence_text, r"RF_COMM_REAL_ACCEPTANCE_SEQUENCE overall=\S+.*"),
            first_marker(real_acceptance_sequence_summary_text, r"PREFLIGHT_OVERALL=BLOCKED_NO_ETHERNET"),
            first_marker(real_acceptance_sequence_summary_text, r"EXECUTED_WRAPPERS=0"),
            first_marker(real_acceptance_sequence_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(real_acceptance_sequence_text, r"NO_TFDU_DRIVE=1"),
            "",
            "RFCM protocol contract:",
            first_marker(protocol_contract_text, r"RF_COMM_PROTOCOL_CONTRACT overall=\S+.*"),
            first_marker(protocol_contract_text, r"NO_HARDWARE_PROGRAMMING=1"),
            first_marker(protocol_contract_text, r"NO_TFDU_DRIVE=1"),
            "",
            "PS/PC offline protocol robustness gate:",
            first_marker(ps_pc_offline_text, r"PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1"),
            first_marker(ps_pc_offline_text, r"STEP_STDERR name=host_client_unittest Ran 21 tests.*"),
            first_marker(ps_pc_offline_text, r"STEP_STDOUT name=host_offline_mock_acceptance log_acceptance PASS"),
            "",
            "Product-loop safe acceptance wrapper latest no-drive evidence:",
            first_marker_any(product_loop_text, [r"PRODUCT_LOOP_DRY_RUN=1", r"PRODUCT_LOOP_REAL_ACCEPTANCE_BLOCKED=1"]),
            first_marker(product_loop_text, r"DURATION_SECONDS_EFFECTIVE=600"),
            first_marker_any(product_loop_text, [r"NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1", r"NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT_FINAL=1"]),
            "",
            "8-lane hardware safe acceptance wrapper latest no-drive evidence:",
            first_marker_any(eightlane_hw_text, [r"EIGHT_LANE_HARDWARE_DRY_RUN=1", r"EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_BLOCKED=1"]),
            first_marker(eightlane_hw_text, r"DURATION_SECONDS_EFFECTIVE=600"),
            first_marker_any(eightlane_hw_text, [r"PROFILE=reduced_8lane_frag16_external", r"PROFILE=full_8lane_stream_bidir"]),
            first_marker(eightlane_hw_text, r"CANDIDATE_A_LANE_COUNT=8"),
            first_marker(eightlane_hw_text, r"REDUCED_8LANE_FRAG16_BITSTREAM_READY_FOR_REVIEW=1"),
            first_marker(eightlane_hw_text, r"REDUCED_8LANE_FRAG16_RAW_HALF_MBPS=32\.0"),
            first_marker(eightlane_hw_text, r"REDUCED_8LANE_FRAG16_RAW_FDX_PER_DIR_MBPS=16\.0"),
            first_marker_any(eightlane_hw_text, [r"EIGHT_LANE_HARDWARE_DRY_RUN_BLOCKED_REASON_PREVIEW=ethernet_link_not_up", r"EIGHT_LANE_HARDWARE_BLOCKED_REASON=ethernet_link_not_up"]),
            first_marker_any(eightlane_hw_text, [r"NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1", r"NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT_FINAL=1"]),
            "",
            "Remaining hardware plan:",
            first_marker(remaining_text, r"RF_COMM_REMAINING_HARDWARE_ACCEPTANCE_PLAN overall=\S+.*"),
            "",
            "Remaining acceptance readiness gate:",
            first_marker(remaining_readiness_text, r"RF_COMM_REMAINING_ACCEPTANCE_READINESS overall=\S+.*"),
            first_marker(remaining_readiness_text, r"REAL_ACCEPTANCE_EXECUTED=0"),
            "",
            "Plan readiness gate:",
            first_marker(plan_readiness_text, r"PLAN_READINESS_SUMMARY .*overall=\S+"),
            first_marker(plan_readiness_text, r"\| ila_analyzer_selftest \| PASS \|"),
            first_marker(plan_readiness_text, r"\| physical_failure_snapshot \| BLOCK_FAR_END_RX_MISSING \|"),
            first_marker(plan_readiness_text, r"\| physical_matrix_gate_selftest \| PASS \|"),
            first_marker(plan_readiness_text, r"\| physical_matrix_overall \| BLOCK_REQUIRED_LINK_NOT_PASSING \|"),
            "",
            "Current next action:",
            "Ethernet cable is currently unavailable, so do not retry real board TCP/DHCP; continue simulation/offline work and run the safe board/TCP acceptance only after an Ethernet link exists.",
        ]
    )
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"WROTE={OUT}")
    print(f"TRACKED_ARTIFACTS={len(paths)}")
    print(first_marker(external_scan_text, r"RF_COMM_EXTERNAL_LANE_RESOURCE_SCAN overall=\S+.*"))
    print(first_marker(external_reduced_lane_text, r"RF_COMM_EXTERNAL_REDUCED_LANE_RESOURCE_SCAN overall=\S+.*"))
    print(first_marker(external_reduced_5to8_text, r"RF_COMM_EXTERNAL_REDUCED_5TO8_EXTENSION overall=\S+.*"))
    print(first_marker(external_reduced_5lane_frag32_text, r"RF_COMM_EXTERNAL_REDUCED_5LANE_FRAG32 overall=\S+.*"))
    print(first_marker(external_reduced_5lane_frag32_route_text, r"RF_COMM_EXTERNAL_REDUCED_5LANE_FRAG32_ROUTE overall=\S+.*"))
    print(first_marker(external_reduced_5lane_frag32_bitstream_text, r"RF_COMM_EXTERNAL_REDUCED_5LANE_FRAG32_BITSTREAM overall=\S+.*"))
    print(first_marker(external_reduced_8lane_frag16_route_text, r"RF_COMM_EXTERNAL_REDUCED_8LANE_FRAG16_ROUTE overall=\S+.*"))
    print(first_marker(external_reduced_8lane_frag16_bitstream_text, r"RF_COMM_EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM overall=\S+.*"))
    print(first_marker(external_route_4lane_text, r"RF_COMM_EXTERNAL_REDUCED_4LANE_ROUTE overall=\S+.*"))
    print(first_marker(external_bitstream_4lane_text, r"RF_COMM_EXTERNAL_REDUCED_4LANE_BITSTREAM overall=\S+.*"))
    print(first_marker(external_bringup_4lane_text, r"RF_COMM_EXTERNAL_REDUCED_4LANE_BRINGUP_PLAN overall=\S+.*"))
    print(first_marker(full_system_offline_envelope_text, r"RF_COMM_FULL_SYSTEM_OFFLINE_TARGET_ENVELOPE overall=\S+.*"))
    print(first_marker(rotating_autoroute_offline_text, r"RF_COMM_ROTATING_AUTOROUTE_OFFLINE_EVIDENCE overall=\S+.*"))
    print(first_marker(rotating_dynamic_text, r"RF_COMM_ROTATING_DYNAMIC_PERMUTATION_AUTOROUTE overall=\S+.*"))
    print(first_marker(rotating_fixture_text, r"RF_COMM_ROTATING_FIXTURE_LOG_VALIDATION overall=\S+.*"))
    print(first_marker(real_acceptance_evidence_text, r"RF_COMM_REAL_ACCEPTANCE_EVIDENCE_VALIDATION overall=\S+.*"))
    print(first_marker(real_acceptance_validator_selftest_text, r"RF_COMM_REAL_ACCEPTANCE_VALIDATOR_SELFTEST overall=\S+.*"))
    print(first_marker(ila_analyzer_selftest_text, r"RF_COMM_2LANE_ILA_ANALYZER_SELFTEST overall=\S+.*"))
    print(first_marker(physical_failure_snapshot_text, r"RF_COMM_2LANE_PHYSICAL_FAILURE_SNAPSHOT overall=\S+.*"))
    print(first_marker(repeat_physical_failure_guard_text, r"RF_COMM_REPEAT_PHYSICAL_FAILURE_GUARD overall=\S+.*"))
    print(first_marker(physical_matrix_gate_selftest_text, r"RF_COMM_PHYSICAL_MATRIX_GATE_SELFTEST overall=\S+.*"))
    print(first_marker(failed_link_retest_text, r"SELECTED_TRIGGER_MODES=.*"))
    print(first_marker(real_acceptance_promotion_gate_text, r"RF_COMM_REAL_ACCEPTANCE_PROMOTION_GATE overall=\S+.*"))
    print(first_marker(duration_cap_text, r"RF_COMM_DURATION_CAP_COMPLIANCE overall=\S+.*"))
    print(first_marker(safe_wrapper_guard_text, r"RF_COMM_SAFE_WRAPPER_GUARD_CONTRACT overall=\S+.*"))
    print(first_marker(network_fault_text, r"RF_COMM_NETWORK_FAULT_RECOVERY_MODEL overall=\S+.*"))
    print(first_marker(release_personality_text, r"RF_COMM_RELEASE_PERSONALITY_DCP_EVIDENCE overall=\S+.*"))
    print(first_marker(status_consistency_text, r"RF_COMM_FULL_TARGET_STATUS_CONSISTENCY overall=\S+.*"))
    print(first_marker(external_preconditions_text, r"RF_COMM_EXTERNAL_PRECONDITIONS overall=\S+.*"))
    print(first_marker(real_acceptance_runbook_text, r"RF_COMM_REAL_ACCEPTANCE_RUNBOOK overall=\S+.*"))
    print(first_marker(real_acceptance_sequence_text, r"RF_COMM_REAL_ACCEPTANCE_SEQUENCE overall=\S+.*"))
    print(first_marker(protocol_contract_text, r"RF_COMM_PROTOCOL_CONTRACT overall=\S+.*"))
    print(first_marker(ps_pc_offline_text, r"PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1"))
    print(first_marker(remaining_readiness_text, r"RF_COMM_REMAINING_ACCEPTANCE_READINESS overall=\S+.*"))
    print(first_marker(plan_readiness_text, r"PLAN_READINESS_SUMMARY .*overall=\S+"))
    print(first_marker_any(rotating_shaft_text, [r"ROTATING_SHAFT_DRY_RUN=1", r"ROTATING_SHAFT_REAL_ACCEPTANCE_BLOCKED=1"]))
    print(first_marker_any(product_loop_text, [r"PRODUCT_LOOP_DRY_RUN=1", r"PRODUCT_LOOP_REAL_ACCEPTANCE_BLOCKED=1"]))
    print(first_marker_any(eightlane_hw_text, [r"EIGHT_LANE_HARDWARE_DRY_RUN=1", r"EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_BLOCKED=1"]))
    if sha256(constraint) != EXPECTED_CONSTRAINT_SHA256:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
