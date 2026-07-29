# P8D DMA descriptor and ring model

- Status: `PASS`
- Test ID: `P8D-DMA-DESCRIPTOR-RING`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `c0d0e120ad622aac8828ee2f37d1ce87853d9573`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "generated_utc": "2026-07-27T12:31:12.979323Z",
  "hardware_scope_promoted": false,
  "long_run": {
    "deadlock": 0,
    "descriptor_double_completion": 0,
    "descriptor_leak": 0,
    "duplicate_application_delivery": 0,
    "duplicate_frames_suppressed": 487856,
    "lane_fault_recovery_events": 61,
    "ring_wraps": 11720,
    "sequence_wraps": 12,
    "state_transitions": 1000000,
    "status": "PASS",
    "unbounded_queue_growth": 0,
    "window_corruption": 0
  },
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "randomized_ring": {
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
    "log_directory": "evidence/generated/p9_final_source_p8d_c0d0/p8d_raw/formal_c0d0e120ad62/xsim/tb_ir_dma_descriptor_ring",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_dma_descriptor_model.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_dma_descriptor_ring.sv",
        "finished_utc": "2026-07-27T12:30:37.479705Z",
        "log": "evidence/generated/p9_final_source_p8d_c0d0/p8d_raw/formal_c0d0e120ad62/xsim/tb_ir_dma_descriptor_ring/compile.log",
        "returncode": 0,
        "started_utc": "2026-07-27T12:30:36.469788Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_dma_descriptor_ring -debug typical -s tb_ir_dma_descriptor_ring_snapshot",
        "finished_utc": "2026-07-27T12:30:38.940160Z",
        "log": "evidence/generated/p9_final_source_p8d_c0d0/p8d_raw/formal_c0d0e120ad62/xsim/tb_ir_dma_descriptor_ring/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-07-27T12:30:37.480349Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_dma_descriptor_ring_snapshot -runall",
        "finished_utc": "2026-07-27T12:30:41.658926Z",
        "log": "evidence/generated/p9_final_source_p8d_c0d0/p8d_raw/formal_c0d0e120ad62/xsim/tb_ir_dma_descriptor_ring/run.log",
        "returncode": 0,
        "started_utc": "2026-07-27T12:30:38.941176Z",
        "timed_out": false
      }
    },
    "required_markers": [
      "P8D_TX_RX_RING_INDEPENDENCE_PASS=1",
      "P8D_DESCRIPTOR_SINGLE_COMPLETION_PASS=1",
      "P8D_RESET_ABORT_STALE_GENERATION_PASS=1",
      "P8D_DESCRIPTOR_LEAK_ZERO_PASS=1",
      "TB_IR_DMA_DESCRIPTOR_RING_PASS=1"
    ],
    "sources": [
      "rtl/ir_dma_descriptor_model.sv",
      "sim/tb/tb_ir_dma_descriptor_ring.sv"
    ],
    "status": "PASS",
    "top": "tb_ir_dma_descriptor_ring"
  },
  "source_commit": "c0d0e120ad622aac8828ee2f37d1ce87853d9573",
  "status": "PASS",
  "test_id": "P8D-DMA-DESCRIPTOR-RING"
}
```
