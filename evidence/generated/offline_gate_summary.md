# Offline Gate Summary

P1_OFFLINE_HARDENING: PASS
BOOTSTRAP_STATUS: PASS
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Generated Summaries

- evidence/generated/offline_gate_summary.md
- evidence/generated/p1_offline_hardening_summary.md
- evidence/generated/no_hardware_action_static_scan.md
- evidence/generated/tfdu6102_offline_contract_summary.md
- evidence/generated/constraint_uniqueness_summary.md
- evidence/generated/rtl_offline_lint_summary.md
- evidence/generated/ps_driver_sequence_summary.md
- evidence/generated/host_offline_stub_summary.md

## PASS

- git_precheck
- directory_integrity_check
- bootstrap_manifest_check
- agents_policy_check
- required_docs_check
- project_status_check
- tools_manifest_check
- no_hardware_action_static_scan
- tfdu6102_safety_contract_check
- constraint_uniqueness_check
- active_profile_check
- rtl_source_manifest_check
- software_source_manifest_check
- ps_driver_sequence_static_check
- host_offline_stub_run_check
- profile_check
- vivado_project_generation_dry_check
- ip_packaging_dry_check
- software_no_real_io_check
- bootstrap_legacy_offline_gates
- manifest_generation
- evidence_consistency_check
- git_cleanliness_report

## FAIL

- none

## SKIP_WITH_REASON

- none

## Gate Details

### git_precheck: PASS

REASON: repository root recorded
SUMMARY: evidence/generated/p1_git_precheck.txt

### directory_integrity_check: PASS

REASON: required directories exist
SUMMARY: evidence/generated/p1_directory_check.md

### bootstrap_manifest_check: PASS

REASON: bootstrap evidence reviewed
SUMMARY: evidence/generated/p1_bootstrap_evidence_review.md

### agents_policy_check: PASS

REASON: AGENTS.md policy markers checked
SUMMARY: evidence/generated/agents_policy_check.md

### required_docs_check: PASS

REASON: required docs present
SUMMARY: evidence/generated/required_docs_manifest.md

### project_status_check: PASS

REASON: PROJECT_STATUS.md checked
SUMMARY: evidence/generated/project_status_check.md

### tools_manifest_check: PASS

REASON: tools manifest generated
SUMMARY: evidence/generated/tools_manifest.md

### no_hardware_action_static_scan: PASS

REASON: hardware action static scan completed
SUMMARY: evidence/generated/no_hardware_action_static_scan.md

### tfdu6102_safety_contract_check: PASS

REASON: TFDU6102 contract checked
SUMMARY: evidence/generated/tfdu6102_offline_contract_summary.md

### constraint_uniqueness_check: PASS

REASON: constraint checks completed
SUMMARY: evidence/generated/constraint_uniqueness_summary.md

### active_profile_check: PASS

REASON: active profile checked
SUMMARY: evidence/generated/active_profile_check.md

### rtl_source_manifest_check: PASS

REASON: RTL manifest generated
SUMMARY: evidence/generated/rtl_source_manifest.md

### software_source_manifest_check: PASS

REASON: software manifest generated
SUMMARY: evidence/generated/software_source_manifest.md

### ps_driver_sequence_static_check: PASS

REASON: PS driver sequence checked
SUMMARY: evidence/generated/ps_driver_sequence_summary.md

### host_offline_stub_run_check: PASS

REASON: host offline stub checked
SUMMARY: evidence/generated/host_offline_stub_summary.md

### profile_check: PASS

REASON: profiles checked
SUMMARY: evidence/generated/profile_check_summary.md

### vivado_project_generation_dry_check: PASS

REASON: Vivado scripts audited
SUMMARY: evidence/generated/vivado_script_audit.md

### ip_packaging_dry_check: PASS

REASON: IP packaging dry check completed
SUMMARY: evidence/generated/ip_packaging_dry_check.md

### software_no_real_io_check: PASS

REASON: software real IO scan complete
SUMMARY: evidence/generated/software_no_real_io_summary.md

### bootstrap_legacy_offline_gates: PASS

REASON: existing offline gates completed
SUMMARY: evidence/generated/p1_bootstrap_legacy_gate_run.md

### manifest_generation: PASS

REASON: manifests generated
SUMMARY: evidence/generated/required_docs_manifest.md

### evidence_consistency_check: PASS

REASON: evidence consistency checked
SUMMARY: evidence/generated/evidence_consistency_summary.md

### git_cleanliness_report: PASS

REASON: git status recorded
SUMMARY: evidence/generated/git_cleanliness_report.md

## P2 Simulation Gate

P2_SIMULATION_BASELINE: PASS
COMBINED_OFFLINE_STATUS: PASS
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW
SUMMARY: evidence/generated/simulation_gate_summary.md
RESULTS: evidence/simulation/sim_results.json

### P2 Failures

- none

### P2 Skips

- none
