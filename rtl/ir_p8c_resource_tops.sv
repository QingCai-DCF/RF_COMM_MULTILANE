`timescale 1ns/1ps
`default_nettype none

// Out-of-context-only wrappers used to audit the implementation cost of the
// complete endpoint safety path. They contain no board pins or hardware I/O.
module ir_p8c_resource_top #(
  parameter integer PHYSICAL_MODULE_COUNT = 8
) (
  input  wire                              clk,
  input  wire                              rst_n,
  input  wire                              global_permit_i,
  input  wire                              arm_request_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]  frame_admitted_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]  waveform_i,
  output wire [PHYSICAL_MODULE_COUNT-1:0]  txd_o,
  output wire                              safety_status_o
);
  wire [PHYSICAL_MODULE_COUNT-1:0] duty_fault;
  wire [PHYSICAL_MODULE_COUNT-1:0] stuck_fault;
  wire [PHYSICAL_MODULE_COUNT-1:0] history_valid;
  wire [PHYSICAL_MODULE_COUNT*32-1:0] rolling;

  ir_tfdu_safety_endpoint #(.PHYSICAL_MODULE_COUNT(PHYSICAL_MODULE_COUNT)) endpoint (
    .clk, .rst_n, .global_permit_i, .endpoint_arm_request_i(arm_request_i),
    .endpoint_disarm_request_i(1'b0), .full_shutdown_request_i(1'b0),
    .safety_fault_clear_request_i(1'b0), .telemetry_clear_i(1'b0),
    .history_invalidate_i(1'b0), .endpoint_fatal_fault_i(1'b0),
    .mapping_valid_i(1'b1), .receive_enable_i({PHYSICAL_MODULE_COUNT{1'b1}}),
    .physical_module_selected_i({PHYSICAL_MODULE_COUNT{1'b1}}),
    .bank_one_hot_valid_i({PHYSICAL_MODULE_COUNT{1'b1}}),
    .bank_fault_i({PHYSICAL_MODULE_COUNT{1'b0}}),
    .lane_tx_permit_i({PHYSICAL_MODULE_COUNT{1'b1}}),
    .path_epoch_valid_i({PHYSICAL_MODULE_COUNT{1'b1}}),
    .frame_admitted_i, .txd_waveform_i(waveform_i),
    .rxd_i({PHYSICAL_MODULE_COUNT{1'b1}}), .physical_txd_out_o(txd_o),
    .physical_sd_o(), .physical_mode_o(), .rx_active_o(), .startup_done_o(),
    .global_permit_raw_safe_o(), .global_permit_sync_o(),
    .global_permit_sync_valid_o(), .global_permit_effective_o(),
    .endpoint_armed_o(), .arm_accept_pulse_o(), .arm_reject_pulse_o(),
    .arm_reject_reason_o(), .tx_kill_active_o(), .effective_tx_enable_mask_o(),
    .duty_hard_fault_mask_o(duty_fault), .stuck_high_fault_mask_o(stuck_fault),
    .endpoint_fatal_fault_o(), .partial_frame_abort_block_o(),
    .global_permit_rise_count_o(), .global_permit_fall_count_o(),
    .global_permit_drop_during_frame_count_o(), .global_permit_rearm_count_o(),
    .last_global_permit_drop_reason_o(), .last_tx_kill_reason_o(),
    .safety_fault_clear_accept_pulse_o(), .rx_pulse_count_flat_o(),
    .rolling_high_cycles_flat_o(rolling), .rolling_high_cycles_max_seen_flat_o(),
    .duty_headroom_cycles_flat_o(), .duty_target_throttle_count_flat_o(),
    .duty_hard_fault_count_flat_o(), .continuous_high_cycles_flat_o(),
    .longest_high_cycles_seen_flat_o(), .stuck_high_fault_count_flat_o(),
    .stuck_high_kill_count_flat_o(), .cooldown_remaining_flat_o(),
    .charge_count_flat_o(), .duty_history_valid_mask_o(history_valid),
    .cooldown_active_mask_o(), .duty_target_throttle_mask_o()
  );
  assign safety_status_o = ^{duty_fault, stuck_fault, history_valid, rolling};
endmodule

module ir_p8c_resource_top_2 (
  input wire clk, rst_n, global_permit_i, arm_request_i,
  input wire [1:0] frame_admitted_i, waveform_i,
  output wire [1:0] txd_o, output wire safety_status_o
);
  ir_p8c_resource_top #(.PHYSICAL_MODULE_COUNT(2)) impl (.*);
endmodule

module ir_p8c_resource_top_8 (
  input wire clk, rst_n, global_permit_i, arm_request_i,
  input wire [7:0] frame_admitted_i, waveform_i,
  output wire [7:0] txd_o, output wire safety_status_o
);
  ir_p8c_resource_top #(.PHYSICAL_MODULE_COUNT(8)) impl (.*);
endmodule

module ir_p8c_resource_top_32 (
  input wire clk, rst_n, global_permit_i, arm_request_i,
  input wire [31:0] frame_admitted_i, waveform_i,
  output wire [31:0] txd_o, output wire safety_status_o
);
  ir_p8c_resource_top #(.PHYSICAL_MODULE_COUNT(32)) impl (.*);
endmodule

`default_nettype wire
