# P8D OOC resource audit

- Status: `PASS`
- Test ID: `P8D-OOC-RESOURCE-AUDIT`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `d28eef6aea8f545282076dd1a19a344adb12ccd9`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "generated_utc": "2026-07-18T12:21:48.330579Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "profiles": {
    "Z7010_2LANE_DEV": {
      "capacity": {
        "BRAM36": 60,
        "DSP": 80,
        "FF": 35200,
        "LUT": 17600
      },
      "critical_warnings": 0,
      "delta_from_p8c": {
        "BRAM36": 4,
        "FF": 3740,
        "LUT": 13759
      },
      "errors": 0,
      "marker_path": "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7010_2LANE_DEV/resource_markers.txt",
      "p8c_baseline_resources": {
        "BRAM36": 4,
        "FF": 307,
        "LUT": 364
      },
      "part": "xc7z010clg400-1",
      "profile": "Z7010_2LANE_DEV",
      "report_paths": [
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7010_2LANE_DEV/check_timing.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7010_2LANE_DEV/data_plane_utilization.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7010_2LANE_DEV/descriptor_ring_utilization.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7010_2LANE_DEV/drc.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7010_2LANE_DEV/payload_store_utilization.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7010_2LANE_DEV/scheduler_utilization.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7010_2LANE_DEV/timing_summary.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7010_2LANE_DEV/utilization.rpt"
      ],
      "resources": {
        "BRAM36": 8,
        "DSP": 0,
        "FF": 4047,
        "LUT": 14123
      },
      "status": "PASS",
      "timing_constraints": "NOT_MET_PENDING_P8E",
      "timing_scope": "P8D_OOC_ARCHITECTURE_AUDIT_NOT_P8E_SIGNOFF",
      "timing_wns_ns": -12.959,
      "utilization_fraction": {
        "BRAM36": 0.13333333333333333,
        "DSP": 0.0,
        "FF": 0.11497159090909091,
        "LUT": 0.8024431818181819
      },
      "vivado_log": "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7010_2LANE_DEV/vivado.log",
      "within_device_capacity": true,
      "z7020_projected_limits_met": true
    },
    "Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE": {
      "capacity": {
        "BRAM36": 140,
        "DSP": 220,
        "FF": 106400,
        "LUT": 53200
      },
      "critical_warnings": 0,
      "delta_from_p8c": {
        "BRAM36": 8,
        "FF": 6660,
        "LUT": 29681
      },
      "errors": 0,
      "marker_path": "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/resource_markers.txt",
      "p8c_baseline_resources": {
        "BRAM36": 64,
        "FF": 4777,
        "LUT": 5519
      },
      "part": "xc7z020clg400-1",
      "profile": "Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE",
      "report_paths": [
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/check_timing.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/data_plane_utilization.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/descriptor_ring_utilization.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/drc.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/payload_store_utilization.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/scheduler_utilization.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/timing_summary.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/utilization.rpt"
      ],
      "resources": {
        "BRAM36": 72,
        "DSP": 0,
        "FF": 11437,
        "LUT": 35200
      },
      "status": "PASS",
      "timing_constraints": "NOT_MET_PENDING_P8E",
      "timing_scope": "P8D_OOC_ARCHITECTURE_AUDIT_NOT_P8E_SIGNOFF",
      "timing_wns_ns": -26.047,
      "utilization_fraction": {
        "BRAM36": 0.5142857142857142,
        "DSP": 0.0,
        "FF": 0.1074906015037594,
        "LUT": 0.6616541353383458
      },
      "vivado_log": "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/vivado.log",
      "within_device_capacity": true,
      "z7020_projected_limits_met": true
    },
    "Z7020_ROTATING_8LANE_MODEL": {
      "capacity": {
        "BRAM36": 140,
        "DSP": 220,
        "FF": 106400,
        "LUT": 53200
      },
      "critical_warnings": 0,
      "delta_from_p8c": {
        "BRAM36": 8,
        "FF": 6659,
        "LUT": 29714
      },
      "errors": 0,
      "marker_path": "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_ROTATING_8LANE_MODEL/resource_markers.txt",
      "p8c_baseline_resources": {
        "BRAM36": 16,
        "FF": 1201,
        "LUT": 1402
      },
      "part": "xc7z020clg400-1",
      "profile": "Z7020_ROTATING_8LANE_MODEL",
      "report_paths": [
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_ROTATING_8LANE_MODEL/check_timing.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_ROTATING_8LANE_MODEL/data_plane_utilization.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_ROTATING_8LANE_MODEL/descriptor_ring_utilization.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_ROTATING_8LANE_MODEL/drc.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_ROTATING_8LANE_MODEL/payload_store_utilization.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_ROTATING_8LANE_MODEL/scheduler_utilization.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_ROTATING_8LANE_MODEL/timing_summary.rpt",
        "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_ROTATING_8LANE_MODEL/utilization.rpt"
      ],
      "resources": {
        "BRAM36": 24,
        "DSP": 0,
        "FF": 7860,
        "LUT": 31116
      },
      "status": "PASS",
      "timing_constraints": "NOT_MET_PENDING_P8E",
      "timing_scope": "P8D_OOC_ARCHITECTURE_AUDIT_NOT_P8E_SIGNOFF",
      "timing_wns_ns": -26.047,
      "utilization_fraction": {
        "BRAM36": 0.17142857142857143,
        "DSP": 0.0,
        "FF": 0.07387218045112783,
        "LUT": 0.5848872180451128
      },
      "vivado_log": "evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001/resource_audit/Z7020_ROTATING_8LANE_MODEL/vivado.log",
      "within_device_capacity": true,
      "z7020_projected_limits_met": true
    }
  },
  "schema_version": 1,
  "scope": "ARCHITECTURE_FEASIBILITY_ONLY_P8E_TIMING_CDC_SIGNOFF_PENDING",
  "source_commit": "d28eef6aea8f545282076dd1a19a344adb12ccd9",
  "status": "PASS",
  "test_id": "P8D-OOC-RESOURCE-AUDIT"
}
```
