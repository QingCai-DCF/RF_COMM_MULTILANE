# P10.1R repository intake

- Status: `PASS`
- Source commit: `493955d5788942ac448a9cfd99c97f0c526281fe`
- Hardware actions executed: `false`

```json
{
  "board_binding": {
    "fixed": "AX7020-F/JTAG:210249855178",
    "rotating_role": "AX7020-R/JTAG:210512180081"
  },
  "branch": "p10.1r/2lane-speed-stability-remediation",
  "current_run_hardware_authorization": false,
  "expected_goal_sha256": "299e9b04b824f6bcf77b51398e87a2b7dc19272bcc245ef968fc7cdf0e57b35f",
  "failure_tag": "p10.1-hardware-performance-fail-20260801",
  "failure_tag_target": "991cc8a6cc5fd656178f9a3ddd9bb7c2f9c84151",
  "failure_tag_type": "tag",
  "generated_at_utc": "2026-08-01T16:12:09+00:00",
  "goal": {
    "bytes": 30007,
    "path": "goals/P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION_GOAL.md",
    "sha256": "299e9b04b824f6bcf77b51398e87a2b7dc19272bcc245ef968fc7cdf0e57b35f"
  },
  "goal_hash_match": true,
  "hardware_actions_executed": false,
  "inputs": [
    {
      "bytes": 30007,
      "path": "goals/P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION_GOAL.md",
      "sha256": "299e9b04b824f6bcf77b51398e87a2b7dc19272bcc245ef968fc7cdf0e57b35f"
    },
    {
      "bytes": 16193,
      "path": "evidence/generated/p10_1_hw_campaign_terminal_summary.json",
      "sha256": "5d5cacd78417986d9457676826fce42efe14f38d2866713ff4c98668c44bfc68"
    },
    {
      "bytes": 31834,
      "path": "config/project_state.json",
      "sha256": "705eec249789796609e30b6151f27062415735463b2350ef5a883524ec7f3ec3"
    },
    {
      "bytes": 224512,
      "path": "config/project_requirements.yaml",
      "sha256": "e063cbf55345e9addb0e7d28cbd27ee817bb864ed8365ebbdab3795a19184c75"
    },
    {
      "bytes": 2565,
      "path": "config/tfdu_rx_admission.yaml",
      "sha256": "95b43f449b85eef06757d6cbb7b682dfc6d5f8eef9c29680127a6fcb2081f485"
    },
    {
      "bytes": 1376,
      "path": "config/performance/p10_1r_hardware_runtime.yaml",
      "sha256": "bb0da402fe2d0fad60aa2364b48c736e38cbf9ee7f76a2cd0d7907458b564a04"
    },
    {
      "bytes": 60070,
      "path": "config/register_map/ir_axi_regs.yaml",
      "sha256": "2a82d64c377d71a4e95d80d0d23b938d42e91b782444c572fe82466153d711a6"
    },
    {
      "bytes": 8497,
      "path": "rtl/p10_1r_rx_admission.sv",
      "sha256": "7d74307a068183410409ddafbd52c7af98396c3bdc7ecc090cd788852ba17c11"
    },
    {
      "bytes": 98586,
      "path": "rtl/p9_optical_transport_core.sv",
      "sha256": "c296dee8880136c764c108980018e54b9eddfbe5fc9d01c524c4700159cd0cf5"
    },
    {
      "bytes": 15725,
      "path": "sim/tb/tb_p10_1r_focused.sv",
      "sha256": "0ff2510f3e0316817aef62f055a1fb6f590e5e83fdf56af4cd52596333de0fc6"
    }
  ],
  "lane_mapping": {
    "lane0": "F0-R0",
    "lane1": "F1-R1"
  },
  "network_used": false,
  "no_hardware": true,
  "offline_tag_is_ancestor": true,
  "p10_pass_tag_is_ancestor": true,
  "schema_version": 1,
  "source_commit": "493955d5788942ac448a9cfd99c97f0c526281fe",
  "source_worktree_dirty_before_generation": true,
  "status": "PASS",
  "test_id": "P10_1R-REPOSITORY-INTAKE",
  "worktree": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_1R"
}
```
