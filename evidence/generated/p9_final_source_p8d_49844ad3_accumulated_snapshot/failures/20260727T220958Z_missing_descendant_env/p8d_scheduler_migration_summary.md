# P8D scheduler and retry migration

- Status: `PASS`
- Test ID: `P8D-SCHEDULER-MIGRATION`
- Profile: `P8D_8LANE_MODEL`
- Source commit: `5097ef02140c8eac79d49f7ff7cd9ed2f7a4a3e8`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "generated_utc": "2026-07-27T21:07:15.403749Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_8LANE_MODEL",
  "randomized_scheduler": {
    "allocated_frames": 100000,
    "descriptor_double_completion": 0,
    "descriptor_leak": 0,
    "descriptor_ring_events": 25000,
    "duplicate_application_delivery": 0,
    "fixed_seeds": [
      1,
      7,
      17,
      31,
      127,
      1024,
      20260718,
      20260719
    ],
    "protocol_lifecycle_events": 100000,
    "scheduler_balanced_fairness_error": 0.0,
    "scheduler_fault_events": 25000,
    "scheduler_fault_workload_fairness_error": 0.6236209613869188,
    "scheduler_maximum_starvation": 17,
    "status": "PASS",
    "unique_application_deliveries": 100000
  },
  "schema_version": 1,
  "simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d/p8d_raw/formal_5097ef02140c/xsim/tb_ir_scheduler_migration",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_health_weighted_scheduler.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_retry_migration.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_scheduler_migration.sv",
        "finished_utc": "2026-07-27T21:06:34.081790Z",
        "log": "evidence/generated/p9_final_source_p8d/p8d_raw/formal_5097ef02140c/xsim/tb_ir_scheduler_migration/compile.log",
        "returncode": 0,
        "started_utc": "2026-07-27T21:06:33.339506Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_scheduler_migration -debug typical -s tb_ir_scheduler_migration_snapshot",
        "finished_utc": "2026-07-27T21:06:35.381830Z",
        "log": "evidence/generated/p9_final_source_p8d/p8d_raw/formal_5097ef02140c/xsim/tb_ir_scheduler_migration/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-07-27T21:06:34.082523Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_scheduler_migration_snapshot -runall",
        "finished_utc": "2026-07-27T21:06:37.966610Z",
        "log": "evidence/generated/p9_final_source_p8d/p8d_raw/formal_5097ef02140c/xsim/tb_ir_scheduler_migration/run.log",
        "returncode": 0,
        "started_utc": "2026-07-27T21:06:35.382473Z",
        "timed_out": false
      }
    },
    "required_markers": [
      "P8D_HEALTH_AWARE_WEIGHTED_SCHEDULER_PASS=1",
      "P8D_SCHEDULER_FAIRNESS_PASS=1",
      "P8D_RETRY_MIGRATION_ACKED_BLOCK_PASS=1",
      "TB_IR_SCHEDULER_MIGRATION_PASS=1"
    ],
    "sources": [
      "rtl/ir_health_weighted_scheduler.sv",
      "rtl/ir_retry_migration.sv",
      "sim/tb/tb_ir_scheduler_migration.sv"
    ],
    "status": "PASS",
    "top": "tb_ir_scheduler_migration"
  },
  "source_commit": "5097ef02140c8eac79d49f7ff7cd9ed2f7a4a3e8",
  "status": "PASS",
  "test_id": "P8D-SCHEDULER-MIGRATION"
}
```
