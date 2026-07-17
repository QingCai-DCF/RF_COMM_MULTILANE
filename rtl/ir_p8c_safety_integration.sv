`timescale 1ns/1ps
`default_nettype none
`include "generated/tfdu_safety_config.svh"

// Integration boundary used by the Z7010 2-module development model, the
// rotating 8-module model, and the fixed 32-module accounting model.
module ir_p8c_safety_integration #(
  parameter integer PHYSICAL_MODULE_COUNT = 32,
  parameter integer FIXED_ENDPOINT = 1,
  parameter integer CLOCK_HZ = `TFDU_SAFETY_CANONICAL_CLOCK_HZ,
  parameter integer STARTUP_US = `TFDU_SAFETY_RECEIVER_STARTUP_US,
  parameter integer WINDOW_US = `TFDU_SAFETY_ROLLING_WINDOW_US,
  parameter integer MAX_CONTINUOUS_HIGH_US = `TFDU_SAFETY_MAX_CONTINUOUS_HIGH_US
) (
  input  wire                                   clk,
  input  wire                                   rst_n,
  input  wire                                   global_permit_i,
  input  wire                                   endpoint_arm_request_i,
  input  wire                                   endpoint_disarm_request_i,
  input  wire                                   full_shutdown_request_i,
  input  wire                                   safety_fault_clear_request_i,
  input  wire                                   history_invalidate_i,
  input  wire                                   active_mapping_valid_i,
  input  wire [39:0]                            active_current_fixed_i,
  input  wire [23:0]                            active_current_bank_i,
  input  wire [31:0]                            active_path_epoch_i,
  input  wire [31:0]                            logical_path_epoch_i,
  input  wire [7:0]                             logical_selected_i,
  input  wire [7:0]                             logical_lane_tx_permit_i,
  input  wire [7:0]                             logical_frame_admitted_i,
  input  wire [7:0]                             logical_txd_waveform_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        receive_enable_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        bank_fault_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        rxd_i,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        physical_txd_out_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        physical_sd_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        rx_active_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        physical_module_selected_o,
  output wire                                   global_permit_raw_safe_o,
  output wire                                   global_permit_sync_valid_o,
  output wire                                   endpoint_armed_o,
  output wire                                   mapping_collision_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        duty_history_valid_mask_o,
  output wire [PHYSICAL_MODULE_COUNT*32-1:0]     rolling_high_cycles_flat_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        duty_hard_fault_mask_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        stuck_high_fault_mask_o
);
  wire [PHYSICAL_MODULE_COUNT-1:0] bank_one_hot_valid;
  wire [PHYSICAL_MODULE_COUNT-1:0] lane_tx_permit;
  wire [PHYSICAL_MODULE_COUNT-1:0] path_epoch_valid;
  wire [PHYSICAL_MODULE_COUNT-1:0] frame_admitted;
  wire [PHYSICAL_MODULE_COUNT-1:0] txd_waveform;
  wire adapter_mapping_valid;

  ir_p8c_mapping_safety_adapter #(
    .PHYSICAL_MODULE_COUNT(PHYSICAL_MODULE_COUNT),
    .FIXED_ENDPOINT(FIXED_ENDPOINT)
  ) u_p8b_mapping_adapter (
    .active_mapping_valid_i(active_mapping_valid_i),
    .active_current_fixed_i(active_current_fixed_i),
    .active_current_bank_i(active_current_bank_i),
    .active_path_epoch_i(active_path_epoch_i),
    .logical_path_epoch_i(logical_path_epoch_i),
    .logical_selected_i(logical_selected_i),
    .logical_lane_tx_permit_i(logical_lane_tx_permit_i),
    .logical_frame_admitted_i(logical_frame_admitted_i),
    .logical_txd_waveform_i(logical_txd_waveform_i),
    .physical_module_selected_o(physical_module_selected_o),
    .bank_one_hot_valid_o(bank_one_hot_valid),
    .lane_tx_permit_o(lane_tx_permit),
    .path_epoch_valid_o(path_epoch_valid),
    .frame_admitted_o(frame_admitted),
    .txd_waveform_o(txd_waveform),
    .mapping_collision_o(mapping_collision_o),
    .adapter_mapping_valid_o(adapter_mapping_valid)
  );

  ir_tfdu_safety_endpoint #(
    .PHYSICAL_MODULE_COUNT(PHYSICAL_MODULE_COUNT),
    .CLOCK_HZ(CLOCK_HZ),
    .STARTUP_US(STARTUP_US),
    .WINDOW_US(WINDOW_US),
    .MAX_CONTINUOUS_HIGH_US(MAX_CONTINUOUS_HIGH_US)
  ) u_endpoint_safety (
    .clk(clk),
    .rst_n(rst_n),
    .global_permit_i(global_permit_i),
    .endpoint_arm_request_i(endpoint_arm_request_i),
    .endpoint_disarm_request_i(endpoint_disarm_request_i),
    .full_shutdown_request_i(full_shutdown_request_i),
    .safety_fault_clear_request_i(safety_fault_clear_request_i),
    .telemetry_clear_i(1'b0),
    .history_invalidate_i(history_invalidate_i),
    .endpoint_fatal_fault_i(mapping_collision_o),
    .mapping_valid_i(adapter_mapping_valid),
    .receive_enable_i(receive_enable_i),
    .physical_module_selected_i(physical_module_selected_o),
    .bank_one_hot_valid_i(bank_one_hot_valid),
    .bank_fault_i(bank_fault_i),
    .lane_tx_permit_i(lane_tx_permit),
    .path_epoch_valid_i(path_epoch_valid),
    .frame_admitted_i(frame_admitted),
    .txd_waveform_i(txd_waveform),
    .rxd_i(rxd_i),
    .physical_txd_out_o(physical_txd_out_o),
    .physical_sd_o(physical_sd_o),
    .physical_mode_o(),
    .rx_active_o(rx_active_o),
    .startup_done_o(),
    .global_permit_raw_safe_o(global_permit_raw_safe_o),
    .global_permit_sync_o(),
    .global_permit_sync_valid_o(global_permit_sync_valid_o),
    .global_permit_effective_o(),
    .endpoint_armed_o(endpoint_armed_o),
    .arm_accept_pulse_o(),
    .arm_reject_pulse_o(),
    .arm_reject_reason_o(),
    .tx_kill_active_o(),
    .effective_tx_enable_mask_o(),
    .duty_hard_fault_mask_o(duty_hard_fault_mask_o),
    .stuck_high_fault_mask_o(stuck_high_fault_mask_o),
    .endpoint_fatal_fault_o(),
    .partial_frame_abort_block_o(),
    .global_permit_rise_count_o(),
    .global_permit_fall_count_o(),
    .global_permit_drop_during_frame_count_o(),
    .global_permit_rearm_count_o(),
    .last_global_permit_drop_reason_o(),
    .last_tx_kill_reason_o(),
    .safety_fault_clear_accept_pulse_o(),
    .rx_pulse_count_flat_o(),
    .rolling_high_cycles_flat_o(rolling_high_cycles_flat_o),
    .rolling_high_cycles_max_seen_flat_o(),
    .duty_headroom_cycles_flat_o(),
    .duty_target_throttle_count_flat_o(),
    .duty_hard_fault_count_flat_o(),
    .continuous_high_cycles_flat_o(),
    .longest_high_cycles_seen_flat_o(),
    .stuck_high_fault_count_flat_o(),
    .stuck_high_kill_count_flat_o(),
    .cooldown_remaining_flat_o(),
    .charge_count_flat_o(),
    .duty_history_valid_mask_o(duty_history_valid_mask_o),
    .cooldown_active_mask_o(),
    .duty_target_throttle_mask_o()
  );
endmodule

`default_nettype wire
