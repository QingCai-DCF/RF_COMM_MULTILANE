# P8D OOC resource audit

- Status: `PASS`
- Test ID: `P8D-OOC-RESOURCE-AUDIT`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `af46d3b9d09fca6d9c57e79b7e91ef634a1ecf5c`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "generated_utc": "2026-08-02T11:40:05.925425Z",
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
        "FF": 4100,
        "LUT": 8357
      },
      "errors": 0,
      "marker_path": "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7010_2LANE_DEV/resource_markers.txt",
      "p8c_baseline_resources": {
        "BRAM36": 4,
        "FF": 307,
        "LUT": 364
      },
      "part": "xc7z010clg400-1",
      "profile": "Z7010_2LANE_DEV",
      "report_paths": [
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7010_2LANE_DEV/check_timing.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7010_2LANE_DEV/data_plane_utilization.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7010_2LANE_DEV/descriptor_ring_utilization.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7010_2LANE_DEV/drc.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7010_2LANE_DEV/payload_store_utilization.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7010_2LANE_DEV/scheduler_utilization.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7010_2LANE_DEV/timing_summary.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7010_2LANE_DEV/utilization.rpt"
      ],
      "resources": {
        "BRAM36": 4,
        "DSP": 0,
        "FF": 4407,
        "LUT": 8721
      },
      "status": "PASS",
      "timing_constraints": "MET",
      "timing_scope": "P8D_OOC_ARCHITECTURE_AUDIT_NOT_P8E_SIGNOFF",
      "timing_wns_ns": 3.919,
      "utilization_fraction": {
        "BRAM36": 0.06666666666666667,
        "DSP": 0.0,
        "FF": 0.12519886363636365,
        "LUT": 0.4955113636363636
      },
      "vivado_log": "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7010_2LANE_DEV/vivado.log",
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
        "FF": 7313,
        "LUT": 13967
      },
      "errors": 0,
      "marker_path": "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/resource_markers.txt",
      "p8c_baseline_resources": {
        "BRAM36": 64,
        "FF": 4777,
        "LUT": 5519
      },
      "part": "xc7z020clg400-1",
      "profile": "Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE",
      "report_paths": [
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/check_timing.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/data_plane_utilization.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/descriptor_ring_utilization.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/drc.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/payload_store_utilization.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/scheduler_utilization.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/timing_summary.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/utilization.rpt"
      ],
      "resources": {
        "BRAM36": 64,
        "DSP": 0,
        "FF": 12090,
        "LUT": 19486
      },
      "status": "PASS",
      "timing_constraints": "MET",
      "timing_scope": "P8D_OOC_ARCHITECTURE_AUDIT_NOT_P8E_SIGNOFF",
      "timing_wns_ns": 3.279,
      "utilization_fraction": {
        "BRAM36": 0.45714285714285713,
        "DSP": 0.0,
        "FF": 0.11362781954887217,
        "LUT": 0.3662781954887218
      },
      "vivado_log": "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE/vivado.log",
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
        "FF": 7352,
        "LUT": 14294
      },
      "errors": 0,
      "marker_path": "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_ROTATING_8LANE_MODEL/resource_markers.txt",
      "p8c_baseline_resources": {
        "BRAM36": 16,
        "FF": 1201,
        "LUT": 1402
      },
      "part": "xc7z020clg400-1",
      "profile": "Z7020_ROTATING_8LANE_MODEL",
      "report_paths": [
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_ROTATING_8LANE_MODEL/check_timing.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_ROTATING_8LANE_MODEL/data_plane_utilization.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_ROTATING_8LANE_MODEL/descriptor_ring_utilization.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_ROTATING_8LANE_MODEL/drc.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_ROTATING_8LANE_MODEL/payload_store_utilization.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_ROTATING_8LANE_MODEL/scheduler_utilization.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_ROTATING_8LANE_MODEL/timing_summary.rpt",
        "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_ROTATING_8LANE_MODEL/utilization.rpt"
      ],
      "resources": {
        "BRAM36": 16,
        "DSP": 0,
        "FF": 8553,
        "LUT": 15696
      },
      "status": "PASS",
      "timing_constraints": "MET",
      "timing_scope": "P8D_OOC_ARCHITECTURE_AUDIT_NOT_P8E_SIGNOFF",
      "timing_wns_ns": 3.287,
      "utilization_fraction": {
        "BRAM36": 0.11428571428571428,
        "DSP": 0.0,
        "FF": 0.08038533834586466,
        "LUT": 0.29503759398496243
      },
      "vivado_log": "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/resource_audit/Z7020_ROTATING_8LANE_MODEL/vivado.log",
      "within_device_capacity": true,
      "z7020_projected_limits_met": true
    }
  },
  "schema_version": 1,
  "scope": "ARCHITECTURE_FEASIBILITY_ONLY_P8E_TIMING_CDC_SIGNOFF_PENDING",
  "source_commit": "af46d3b9d09fca6d9c57e79b7e91ef634a1ecf5c",
  "status": "PASS",
  "test_id": "P8D-OOC-RESOURCE-AUDIT"
}
```
