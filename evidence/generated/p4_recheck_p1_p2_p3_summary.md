# P4 Recheck P1 P2 P3 Summary

generated_at_utc: 2026-07-08T15:13:31+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
RESULT: PASS
REASON: P1/P2/P3 recheck markers are acceptable
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P1_RECHECK: PASS
P2_RECHECK: PASS
P3_RECHECK: PASS
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Commands

- `C:\Users\user\AppData\Local\Programs\Python\Python314\python.exe tools/run_offline_gate.py --allow-skips --json-summary --include-simulation --include-pre-hw-package` -> rc=0
- `powershell -NoProfile -ExecutionPolicy Bypass -File tools/run_offline_gate.ps1 -AllowSkips -JsonSummary -IncludeSimulation -IncludePreHwPackage` -> rc=0
- `C:\Users\user\AppData\Local\Programs\Python\Python314\python.exe tools/run_simulation_gate.py --json-summary --allow-skips` -> rc=0
- `C:\Users\user\AppData\Local\Programs\Python\Python314\python.exe tools/run_pre_hw_acceptance_package_gate.py --json-summary --allow-skips` -> rc=0
- `C:\Users\user\AppData\Local\Programs\Python\Python314\python.exe tools/summarize_gate.py` -> rc=0

## Command Evidence

```json
[
  {
    "cmd": "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python314\\python.exe tools/run_offline_gate.py --allow-skips --json-summary --include-simulation --include-pre-hw-package",
    "returncode": 0,
    "stdout_tail": "{\"P1_OFFLINE_HARDENING\": \"PASS\", \"P2_SIMULATION_BASELINE\": \"PASS\", \"P3_PRE_HW_ACCEPTANCE_PACKAGE\": \"PASS\", \"COMBINED_OFFLINE_STATUS\": \"PASS\", \"NO_HARDWARE_ACTIONS_EXECUTED\": true, \"HARDWARE_ACCEPTANCE\": \"PENDING_HW\", \"failed\": [], \"skipped\": []}\n",
    "stderr_tail": ""
  },
  {
    "cmd": "powershell -NoProfile -ExecutionPolicy Bypass -File tools/run_offline_gate.ps1 -AllowSkips -JsonSummary -IncludeSimulation -IncludePreHwPackage",
    "returncode": 0,
    "stdout_tail": "RF_COMM_MULTILANE P1 offline gate\nPWD=C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\nGIT_HEAD=4768ef76c1d9bc6042d4058f52eef5fc0da5ca01\nNO_HARDWARE_ACTIONS_EXECUTED: true\nHARDWARE_ACCEPTANCE: PENDING_HW\n{\"P1_OFFLINE_HARDENING\": \"PASS\", \"P2_SIMULATION_BASELINE\": \"PASS\", \"P3_PRE_HW_ACCEPTANCE_PACKAGE\": \"PASS\", \"COMBINED_OFFLINE_STATUS\": \"PASS\", \"NO_HARDWARE_ACTIONS_EXECUTED\": true, \"HARDWARE_ACCEPTANCE\": \"PENDING_HW\", \"failed\": [], \"skipped\": []}\n",
    "stderr_tail": ""
  },
  {
    "cmd": "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python314\\python.exe tools/run_simulation_gate.py --json-summary --allow-skips",
    "returncode": 0,
    "stdout_tail": "{\"P2_SIMULATION_BASELINE\": \"PASS\", \"NO_HARDWARE_ACTIONS_EXECUTED\": true, \"HARDWARE_ACCEPTANCE\": \"PENDING_HW\", \"failed\": [], \"skipped\": []}\n",
    "stderr_tail": ""
  },
  {
    "cmd": "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python314\\python.exe tools/run_pre_hw_acceptance_package_gate.py --json-summary --allow-skips",
    "returncode": 0,
    "stdout_tail": "{\"P3_PRE_HW_ACCEPTANCE_PACKAGE\": \"PASS\", \"P0_RECHECK\": \"PASS\", \"P1_RECHECK\": \"PASS\", \"P2_RECHECK\": \"PASS\", \"NO_HARDWARE_ACTIONS_EXECUTED\": true, \"HARDWARE_ACCEPTANCE\": \"PENDING_HW\", \"generated_summaries\": [\"evidence/generated/p3_repo_intake.md\", \"evidence/generated/p3_pre_hw_acceptance_package_summary.md\", \"evidence/generated/p3_no_hardware_static_scan.md\", \"evidence/generated/p3_authorization_gate_summary.md\", \"evidence/generated/p3_hardware_script_dry_run_summary.md\", \"evidence/generated/p3_constraint_freeze_summary.md\", \"evidence/generated/p3_bitstream_build_audit_summary.md\", \"evidence/generated/p3_evidence_schema_summary.md\", \"evidence/generated/p3_runbook_summary.md\", \"evidence/generated/p3_recheck_p1_p2_summary.md\"], \"pass\": [\"P3_REPO_INTAKE\", \"AUTHORIZATION_GATE\", \"EVIDENCE_SCHEMA\", \"RUNBOOKS\", \"CONSTRAINT_FREEZE\", \"BITSTREAM_BUILD_AUDIT\", \"AGENTS_P3_BOUNDARY\", \"HARDWARE_SCRIPT_DRY_RUNS\", \"NO_HARDWARE_STATIC_SCAN\", \"TFDU6102_CONTRACT\", \"P3_EVIDENCE_CONSISTENCY\"], \"fail\": [], \"skip\": [], \"NEXT_RECOMMENDED_STAGE\": \"P4_HARDWARE_ACCEPTANCE_ONLY_AFTER_USER_AUTHORIZATION\"}\n",
    "stderr_tail": ""
  },
  {
    "cmd": "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python314\\python.exe tools/summarize_gate.py",
    "returncode": 0,
    "stdout_tail": "RESULT: PASS\nP1_OFFLINE_HARDENING: PASS\nP2_SIMULATION_BASELINE: PASS\nNO_HARDWARE_ACTIONS_EXECUTED: true\nHARDWARE_ACCEPTANCE: PENDING_HW\ngit_precheck: PASS\ndirectory_integrity_check: PASS\nbootstrap_manifest_check: PASS\nagents_policy_check: PASS\nrequired_docs_check: PASS\nproject_status_check: PASS\ntools_manifest_check: PASS\nno_hardware_action_static_scan: PASS\ntfdu6102_safety_contract_check: PASS\nconstraint_uniqueness_check: PASS\nactive_profile_check: PASS\nrtl_source_manifest_check: PASS\nsoftware_source_manifest_check: PASS\nps_driver_sequence_static_check: PASS\nhost_offline_stub_run_check: PASS\nprofile_check: PASS\nvivado_project_generation_dry_check: PASS\nip_packaging_dry_check: PASS\nsoftware_no_real_io_check: PASS\nmanifest_generation: PASS\nevidence_consistency_check: PASS\ngit_cleanliness_report: PASS\n",
    "stderr_tail": ""
  }
]
```
