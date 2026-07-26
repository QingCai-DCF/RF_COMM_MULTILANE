# P8D OOC resource audit

- Status: `PASS`
- Test ID: `P8D-OOC-RESOURCE-AUDIT`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `0e3aca774213327dcc668a93b2fe663f048c7e11`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "generated_utc": "2026-07-26T12:11:33.620619Z",
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
        "BRAM36": 0,
        "FF": 4116,
        "LUT": 8398
      },
      "errors": 0,
      "marker_path": "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7010_2LANE_DEV/resource_markers.txt",
      "p8c_baseline_resources": {
        "BRAM36": 4,
        "FF": 307,
        "LUT": 364
      },
      "part": "xc7z010clg400-1",
      "profile": "Z7010_2LANE_DEV",
      "report_paths": [
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7010_2LANE_DEV/check_timing.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7010_2LANE_DEV/data_plane_utilization.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7010_2LANE_DEV/descriptor_ring_utilization.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7010_2LANE_DEV/drc.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7010_2LANE_DEV/payload_store_utilization.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7010_2LANE_DEV/scheduler_utilization.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7010_2LANE_DEV/timing_summary.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7010_2LANE_DEV/utilization.rpt"
      ],
      "resources": {
        "BRAM36": 4,
        "DSP": 0,
        "FF": 4423,
        "LUT": 8762
      },
      "status": "PASS",
      "timing_constraints": "MET",
      "timing_scope": "P8D_OOC_ARCHITECTURE_AUDIT_NOT_P8E_SIGNOFF",
      "timing_wns_ns": 2.996,
      "utilization_fraction": {
        "BRAM36": 0.06666666666666667,
        "DSP": 0.0,
        "FF": 0.12565340909090908,
        "LUT": 0.4978409090909091
      },
      "vivado_log": "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7010_2LANE_DEV/vivado.log",
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
        "BRAM36": 0,
        "FF": 7316,
        "LUT": 14059
      },
      "errors": 0,
      "marker_path": "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/resource_markers.txt",
      "p8c_baseline_resources": {
        "BRAM36": 64,
        "FF": 4777,
        "LUT": 5519
      },
      "part": "xc7z020clg400-1",
      "profile": "Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE",
      "report_paths": [
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/check_timing.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/data_plane_utilization.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/descriptor_ring_utilization.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/drc.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/payload_store_utilization.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/scheduler_utilization.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/timing_summary.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/utilization.rpt"
      ],
      "resources": {
        "BRAM36": 64,
        "DSP": 0,
        "FF": 12093,
        "LUT": 19578
      },
      "status": "PASS",
      "timing_constraints": "MET",
      "timing_scope": "P8D_OOC_ARCHITECTURE_AUDIT_NOT_P8E_SIGNOFF",
      "timing_wns_ns": 2.477,
      "utilization_fraction": {
        "BRAM36": 0.45714285714285713,
        "DSP": 0.0,
        "FF": 0.11365601503759398,
        "LUT": 0.3680075187969925
      },
      "vivado_log": "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/vivado.log",
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
        "BRAM36": 0,
        "FF": 7387,
        "LUT": 14604
      },
      "errors": 0,
      "marker_path": "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_ROTATING_8LANE_MODEL/resource_markers.txt",
      "p8c_baseline_resources": {
        "BRAM36": 16,
        "FF": 1201,
        "LUT": 1402
      },
      "part": "xc7z020clg400-1",
      "profile": "Z7020_ROTATING_8LANE_MODEL",
      "report_paths": [
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_ROTATING_8LANE_MODEL/check_timing.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_ROTATING_8LANE_MODEL/data_plane_utilization.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_ROTATING_8LANE_MODEL/descriptor_ring_utilization.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_ROTATING_8LANE_MODEL/drc.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_ROTATING_8LANE_MODEL/payload_store_utilization.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_ROTATING_8LANE_MODEL/scheduler_utilization.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_ROTATING_8LANE_MODEL/timing_summary.rpt",
        "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_ROTATING_8LANE_MODEL/utilization.rpt"
      ],
      "resources": {
        "BRAM36": 16,
        "DSP": 0,
        "FF": 8588,
        "LUT": 16006
      },
      "status": "PASS",
      "timing_constraints": "MET",
      "timing_scope": "P8D_OOC_ARCHITECTURE_AUDIT_NOT_P8E_SIGNOFF",
      "timing_wns_ns": 2.476,
      "utilization_fraction": {
        "BRAM36": 0.11428571428571428,
        "DSP": 0.0,
        "FF": 0.08071428571428571,
        "LUT": 0.30086466165413533
      },
      "vivado_log": "evidence/generated/p8d_raw/formal_0e3aca774213/resource_audit/Z7020_ROTATING_8LANE_MODEL/vivado.log",
      "within_device_capacity": true,
      "z7020_projected_limits_met": true
    }
  },
  "schema_version": 1,
  "scope": "ARCHITECTURE_FEASIBILITY_ONLY_P8E_TIMING_CDC_SIGNOFF_PENDING",
  "source_commit": "0e3aca774213327dcc668a93b2fe663f048c7e11",
  "status": "PASS",
  "test_id": "P8D-OOC-RESOURCE-AUDIT"
}
```
