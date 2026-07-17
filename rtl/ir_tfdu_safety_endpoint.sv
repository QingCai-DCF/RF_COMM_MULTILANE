`timescale 1ns/1ps
`default_nettype none
`include "generated/tfdu_safety_config.svh"

// One electrically independent endpoint. This module intentionally consumes
// exactly one local active-high global_permit_i. Other masks are necessary
// safety conditions, never additional global-permit channels.
module ir_tfdu_safety_endpoint #(
  parameter integer PHYSICAL_MODULE_COUNT = 8,
  parameter integer CLOCK_HZ = `TFDU_SAFETY_CANONICAL_CLOCK_HZ,
  parameter integer STARTUP_US = `TFDU_SAFETY_RECEIVER_STARTUP_US,
  parameter integer WINDOW_US = `TFDU_SAFETY_ROLLING_WINDOW_US,
  parameter integer HARD_PERCENT_STRICT_LT = `TFDU_SAFETY_HARD_PERCENT_STRICT_LT,
  parameter integer TARGET_PERCENT_MAX = `TFDU_SAFETY_TARGET_PERCENT_MAX,
  parameter integer MAX_CONTINUOUS_HIGH_US = `TFDU_SAFETY_MAX_CONTINUOUS_HIGH_US,
  parameter integer ASSERT_FILTER_CYCLES = `TFDU_SAFETY_ASSERT_FILTER_CYCLES
) (
  input  wire                                   clk,
  input  wire                                   rst_n,
  input  wire                                   global_permit_i,
  input  wire                                   endpoint_arm_request_i,
  input  wire                                   endpoint_disarm_request_i,
  input  wire                                   full_shutdown_request_i,
  input  wire                                   safety_fault_clear_request_i,
  input  wire                                   telemetry_clear_i,
  input  wire                                   history_invalidate_i,
  input  wire                                   endpoint_fatal_fault_i,
  input  wire                                   mapping_valid_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        receive_enable_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        physical_module_selected_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        bank_one_hot_valid_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        bank_fault_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        lane_tx_permit_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        path_epoch_valid_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        frame_admitted_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        txd_waveform_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        rxd_i,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        physical_txd_out_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        physical_sd_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        physical_mode_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        rx_active_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        startup_done_o,
  output wire                                    global_permit_raw_safe_o,
  output wire                                    global_permit_sync_o,
  output wire                                    global_permit_sync_valid_o,
  output wire                                    global_permit_effective_o,
  output reg                                     endpoint_armed_o,
  output reg                                     arm_accept_pulse_o,
  output reg                                     arm_reject_pulse_o,
  output reg  [4:0]                              arm_reject_reason_o,
  output wire                                    tx_kill_active_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        effective_tx_enable_mask_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        duty_hard_fault_mask_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        stuck_high_fault_mask_o,
  output wire                                    endpoint_fatal_fault_o,
  output reg                                     partial_frame_abort_block_o,
  output reg  [31:0]                             global_permit_rise_count_o,
  output reg  [31:0]                             global_permit_fall_count_o,
  output reg  [31:0]                             global_permit_drop_during_frame_count_o,
  output reg  [31:0]                             global_permit_rearm_count_o,
  output reg  [4:0]                              last_global_permit_drop_reason_o,
  output reg  [4:0]                              last_tx_kill_reason_o,
  output reg                                     safety_fault_clear_accept_pulse_o,
  output reg  [PHYSICAL_MODULE_COUNT*32-1:0]     rx_pulse_count_flat_o,
  output wire [PHYSICAL_MODULE_COUNT*32-1:0]     rolling_high_cycles_flat_o,
  output wire [PHYSICAL_MODULE_COUNT*32-1:0]     rolling_high_cycles_max_seen_flat_o,
  output wire [PHYSICAL_MODULE_COUNT*32-1:0]     duty_headroom_cycles_flat_o,
  output wire [PHYSICAL_MODULE_COUNT*32-1:0]     duty_target_throttle_count_flat_o,
  output wire [PHYSICAL_MODULE_COUNT*32-1:0]     duty_hard_fault_count_flat_o,
  output wire [PHYSICAL_MODULE_COUNT*32-1:0]     continuous_high_cycles_flat_o,
  output wire [PHYSICAL_MODULE_COUNT*32-1:0]     longest_high_cycles_seen_flat_o,
  output wire [PHYSICAL_MODULE_COUNT*32-1:0]     stuck_high_fault_count_flat_o,
  output wire [PHYSICAL_MODULE_COUNT*32-1:0]     stuck_high_kill_count_flat_o,
  output wire [PHYSICAL_MODULE_COUNT*32-1:0]     cooldown_remaining_flat_o,
  output wire [PHYSICAL_MODULE_COUNT*32-1:0]     charge_count_flat_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        duty_history_valid_mask_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        cooldown_active_mask_o,
  output wire [PHYSICAL_MODULE_COUNT-1:0]        duty_target_throttle_mask_o
);
  import tfdu_safety_pkg::*;

  localparam integer FILTER_W = (ASSERT_FILTER_CYCLES <= 1) ? 1 : $clog2(ASSERT_FILTER_CYCLES + 1);

  reg permit_meta_q;
  reg permit_sync_q;
  reg [FILTER_W-1:0] permit_filter_count_q;
  reg permit_sync_valid_q;
  reg permit_raw_prev_q;
  reg [PHYSICAL_MODULE_COUNT-1:0] txd_pre_final;
  wire [PHYSICAL_MODULE_COUNT-1:0] qualified_tx_request;
  wire [PHYSICAL_MODULE_COUNT-1:0] selected_conditions_ok;
  wire all_selected_conditions_ok;
  wire any_selected;
  wire any_module_fault;
  wire arm_conditions_ok;
  wire safety_fault_clear_acceptable;
  reg [4:0] current_kill_reason;
  reg [PHYSICAL_MODULE_COUNT-1:0] rxd_meta_q;
  reg [PHYSICAL_MODULE_COUNT-1:0] rxd_sync_q;
  reg [PHYSICAL_MODULE_COUNT-1:0] rxd_sync_d_q;

  // Case equality makes X/Z fail low in simulation. In two-state hardware this
  // reduces to the single active-high input buffer.
  reg global_permit_raw_safe;
  always @* begin
    global_permit_raw_safe = 1'b0;
    if (global_permit_i === 1'b1)
      global_permit_raw_safe = 1'b1;
  end

  assign global_permit_raw_safe_o = global_permit_raw_safe;
  assign global_permit_sync_o = permit_sync_q;
  assign global_permit_sync_valid_o = permit_sync_valid_q;
  assign global_permit_effective_o =
      global_permit_raw_safe && permit_sync_valid_q && endpoint_armed_o;
  assign physical_sd_o = (~receive_enable_i) |
      {PHYSICAL_MODULE_COUNT{full_shutdown_request_i}};
  assign physical_mode_o = {PHYSICAL_MODULE_COUNT{1'b1}};
  assign rx_active_o = (~rxd_sync_q) & startup_done_o & (~physical_sd_o);
  assign any_selected = |physical_module_selected_i;
  assign selected_conditions_ok = (~physical_module_selected_i) |
      (bank_one_hot_valid_i & (~bank_fault_i) & lane_tx_permit_i &
       path_epoch_valid_i & startup_done_o & duty_history_valid_mask_o &
       (~cooldown_active_mask_o) & (~duty_hard_fault_mask_o) &
       (~stuck_high_fault_mask_o) & (~physical_sd_o));
  assign all_selected_conditions_ok = &selected_conditions_ok;
  assign any_module_fault = |duty_hard_fault_mask_o | |stuck_high_fault_mask_o;
  assign endpoint_fatal_fault_o = endpoint_fatal_fault_i || !mapping_valid_i ||
      (|(bank_fault_i & physical_module_selected_i)) || any_module_fault;
  assign arm_conditions_ok = global_permit_raw_safe && permit_sync_valid_q &&
      !endpoint_fatal_fault_o && any_selected && all_selected_conditions_ok &&
      !full_shutdown_request_i && !partial_frame_abort_block_o &&
      !(|frame_admitted_i);
  assign safety_fault_clear_acceptable = !global_permit_raw_safe &&
      !(|physical_txd_out_o) && !(|txd_pre_final);

  assign qualified_tx_request =
      physical_module_selected_i & bank_one_hot_valid_i & (~bank_fault_i) &
      lane_tx_permit_i & path_epoch_valid_i & startup_done_o &
      duty_history_valid_mask_o & (~cooldown_active_mask_o) &
      frame_admitted_i & txd_waveform_i & (~physical_sd_o) &
      {PHYSICAL_MODULE_COUNT{global_permit_sync_valid_o && endpoint_armed_o &&
        !endpoint_fatal_fault_o && !partial_frame_abort_block_o}};

  assign effective_tx_enable_mask_o = physical_txd_out_o;
  assign tx_kill_active_o = (|txd_waveform_i) && !(|physical_txd_out_o);

  always @* begin
    current_kill_reason = TX_KILL_NONE;
    if (!rst_n || full_shutdown_request_i)
      current_kill_reason = TX_KILL_RESET_OR_FULL_SHUTDOWN;
    else if (!global_permit_raw_safe)
      current_kill_reason = TX_KILL_GLOBAL_PERMIT_LOW;
    else if (!permit_sync_valid_q)
      current_kill_reason = TX_KILL_GLOBAL_PERMIT_LOW;
    else if (endpoint_fatal_fault_i || !mapping_valid_i || (|(bank_fault_i & physical_module_selected_i)))
      current_kill_reason = TX_KILL_FATAL_FAULT;
    else if (!any_selected)
      current_kill_reason = TX_KILL_INVALID_SELECTED_MODULE;
    else if (!(&((~physical_module_selected_i) | bank_one_hot_valid_i)))
      current_kill_reason = TX_KILL_ILLEGAL_ONE_HOT;
    else if (!(&((~physical_module_selected_i) | path_epoch_valid_i)))
      current_kill_reason = TX_KILL_STALE_OR_INVALID_PATH_EPOCH;
    else if (!(&((~physical_module_selected_i) | startup_done_o)))
      current_kill_reason = TX_KILL_STARTUP_NOT_COMPLETE;
    else if (|(cooldown_active_mask_o & physical_module_selected_i))
      current_kill_reason = TX_KILL_HISTORY_COOLDOWN;
    else if (|(duty_hard_fault_mask_o & physical_module_selected_i))
      current_kill_reason = TX_KILL_DUTY_HARD_FAULT;
    else if (|(stuck_high_fault_mask_o & physical_module_selected_i))
      current_kill_reason = TX_KILL_STUCK_HIGH_FAULT;
    else if (partial_frame_abort_block_o)
      current_kill_reason = TX_KILL_PARTIAL_FRAME_ABORTED;
    else if (!endpoint_armed_o)
      current_kill_reason = TX_KILL_NOT_ARMED;
    else if (|(physical_sd_o & physical_module_selected_i))
      current_kill_reason = TX_KILL_SD_ACTIVE;
    else if (!(|frame_admitted_i))
      current_kill_reason = TX_KILL_FRAME_NOT_ADMITTED;
    else if (|(duty_target_throttle_mask_o & physical_module_selected_i))
      current_kill_reason = TX_KILL_DUTY_TARGET_THROTTLE;
  end

  initial begin
    if (PHYSICAL_MODULE_COUNT < 1 || PHYSICAL_MODULE_COUNT > 32)
      $fatal(1, "P8C physical module count must be in 1..32");
    if (ASSERT_FILTER_CYCLES < 2)
      $fatal(1, "P8C permit high filter must be at least two cycles");
  end

  // Raw-low asynchronously clears both synchronizer state and arm. Raw high
  // can only progress through synchronization, filtering, and explicit arm.
  always @(posedge clk or negedge rst_n or negedge global_permit_raw_safe) begin
    if (!rst_n || !global_permit_raw_safe) begin
      permit_meta_q <= 1'b0;
      permit_sync_q <= 1'b0;
      permit_filter_count_q <= {FILTER_W{1'b0}};
      permit_sync_valid_q <= 1'b0;
    end else begin
      permit_meta_q <= 1'b1;
      permit_sync_q <= permit_meta_q;
      if (!permit_sync_q) begin
        permit_filter_count_q <= {FILTER_W{1'b0}};
        permit_sync_valid_q <= 1'b0;
      end else if (!permit_sync_valid_q) begin
        if (permit_filter_count_q == ASSERT_FILTER_CYCLES-1) begin
          permit_sync_valid_q <= 1'b1;
        end else begin
          permit_filter_count_q <= permit_filter_count_q + 1'b1;
        end
      end
    end
  end

  always @(posedge clk or negedge rst_n or negedge global_permit_raw_safe) begin
    if (!rst_n || !global_permit_raw_safe) begin
      endpoint_armed_o <= 1'b0;
      arm_accept_pulse_o <= 1'b0;
      arm_reject_pulse_o <= 1'b0;
      arm_reject_reason_o <= TX_KILL_NONE;
    end else begin
      arm_accept_pulse_o <= 1'b0;
      arm_reject_pulse_o <= 1'b0;
      arm_reject_reason_o <= TX_KILL_NONE;
      if (endpoint_disarm_request_i || full_shutdown_request_i ||
          endpoint_fatal_fault_o || !all_selected_conditions_ok) begin
        endpoint_armed_o <= 1'b0;
      end
      if (endpoint_arm_request_i) begin
        if (arm_conditions_ok) begin
          endpoint_armed_o <= 1'b1;
          arm_accept_pulse_o <= 1'b1;
        end else begin
          endpoint_armed_o <= 1'b0;
          arm_reject_pulse_o <= 1'b1;
          arm_reject_reason_o <= current_kill_reason;
        end
      end
    end
  end

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      permit_raw_prev_q <= 1'b0;
      partial_frame_abort_block_o <= 1'b0;
      global_permit_rise_count_o <= 32'd0;
      global_permit_fall_count_o <= 32'd0;
      global_permit_drop_during_frame_count_o <= 32'd0;
      global_permit_rearm_count_o <= 32'd0;
      last_global_permit_drop_reason_o <= TX_KILL_NONE;
      last_tx_kill_reason_o <= TX_KILL_NONE;
      safety_fault_clear_accept_pulse_o <= 1'b0;
      rxd_meta_q <= {PHYSICAL_MODULE_COUNT{1'b1}};
      rxd_sync_q <= {PHYSICAL_MODULE_COUNT{1'b1}};
      rxd_sync_d_q <= {PHYSICAL_MODULE_COUNT{1'b1}};
      rx_pulse_count_flat_o <= {(PHYSICAL_MODULE_COUNT*32){1'b0}};
    end else begin
      permit_raw_prev_q <= global_permit_raw_safe;
      safety_fault_clear_accept_pulse_o <= 1'b0;
      rxd_meta_q <= rxd_i;
      rxd_sync_q <= rxd_meta_q;
      rxd_sync_d_q <= rxd_sync_q;

      if (global_permit_raw_safe && !permit_raw_prev_q)
        global_permit_rise_count_o <= global_permit_rise_count_o + 1'b1;
      if (arm_accept_pulse_o)
        global_permit_rearm_count_o <= global_permit_rearm_count_o + 1'b1;
      if (!global_permit_raw_safe && permit_raw_prev_q) begin
        global_permit_fall_count_o <= global_permit_fall_count_o + 1'b1;
        last_global_permit_drop_reason_o <= TX_KILL_GLOBAL_PERMIT_LOW;
        if (|frame_admitted_i) begin
          global_permit_drop_during_frame_count_o <=
              global_permit_drop_during_frame_count_o + 1'b1;
          partial_frame_abort_block_o <= 1'b1;
        end
      end
      if ((endpoint_disarm_request_i || endpoint_fatal_fault_o ||
           full_shutdown_request_i) && (|frame_admitted_i))
        partial_frame_abort_block_o <= 1'b1;
      if (partial_frame_abort_block_o && !(|frame_admitted_i))
        partial_frame_abort_block_o <= 1'b0;

      if (safety_fault_clear_request_i && safety_fault_clear_acceptable)
        safety_fault_clear_accept_pulse_o <= 1'b1;
      if (tx_kill_active_o)
        last_tx_kill_reason_o <= current_kill_reason;

      for (integer rx_index = 0; rx_index < PHYSICAL_MODULE_COUNT; rx_index = rx_index + 1) begin
        if (telemetry_clear_i) begin
          rx_pulse_count_flat_o[rx_index*32 +: 32] <= 32'd0;
        end else if (startup_done_o[rx_index] && !physical_sd_o[rx_index] &&
                     !rxd_sync_q[rx_index] && rxd_sync_d_q[rx_index]) begin
          rx_pulse_count_flat_o[rx_index*32 +: 32] <=
              rx_pulse_count_flat_o[rx_index*32 +: 32] + 1'b1;
        end
      end
    end
  end

  genvar module_index;
  generate
    for (module_index = 0; module_index < PHYSICAL_MODULE_COUNT; module_index = module_index + 1) begin : g_physical_safety
      ir_tfdu_physical_module_safety #(
        .CLOCK_HZ(CLOCK_HZ),
        .STARTUP_US(STARTUP_US),
        .WINDOW_US(WINDOW_US),
        .HARD_PERCENT_STRICT_LT(HARD_PERCENT_STRICT_LT),
        .TARGET_PERCENT_MAX(TARGET_PERCENT_MAX),
        .MAX_CONTINUOUS_HIGH_US(MAX_CONTINUOUS_HIGH_US)
      ) u_physical_module_safety (
        .clk(clk),
        .rst_n(rst_n),
        .history_invalidate_i(history_invalidate_i),
        .safety_fault_clear_i(safety_fault_clear_accept_pulse_o),
        .telemetry_clear_i(telemetry_clear_i),
        .sd_active_i(physical_sd_o[module_index]),
        .tx_request_i(qualified_tx_request[module_index]),
        .txd_pre_final_o(txd_pre_final[module_index]),
        .startup_done_o(startup_done_o[module_index]),
        .continuous_high_cycles_o(continuous_high_cycles_flat_o[module_index*32 +: 32]),
        .longest_high_cycles_seen_o(longest_high_cycles_seen_flat_o[module_index*32 +: 32]),
        .stuck_high_fault_o(stuck_high_fault_mask_o[module_index]),
        .stuck_high_fault_count_o(stuck_high_fault_count_flat_o[module_index*32 +: 32]),
        .stuck_high_kill_count_o(stuck_high_kill_count_flat_o[module_index*32 +: 32]),
        .rolling_high_cycles_o(rolling_high_cycles_flat_o[module_index*32 +: 32]),
        .rolling_high_cycles_max_seen_o(rolling_high_cycles_max_seen_flat_o[module_index*32 +: 32]),
        .rolling_window_cycles_o(),
        .hard_limit_cycles_o(),
        .target_limit_cycles_o(),
        .duty_headroom_cycles_o(duty_headroom_cycles_flat_o[module_index*32 +: 32]),
        .duty_target_throttle_o(duty_target_throttle_mask_o[module_index]),
        .duty_target_throttle_count_o(duty_target_throttle_count_flat_o[module_index*32 +: 32]),
        .duty_hard_fault_o(duty_hard_fault_mask_o[module_index]),
        .duty_hard_fault_count_o(duty_hard_fault_count_flat_o[module_index*32 +: 32]),
        .duty_history_valid_o(duty_history_valid_mask_o[module_index]),
        .duty_recovery_cooldown_active_o(cooldown_active_mask_o[module_index]),
        .duty_recovery_cooldown_remaining_o(cooldown_remaining_flat_o[module_index*32 +: 32]),
        .actual_or_conservative_charge_count_o(charge_count_flat_o[module_index*32 +: 32])
      );
    end
  endgenerate

  // P17 final-kill invariant: no logic exists after this raw-safe AND that can
  // reassert a physical Txd output. Raw low therefore kills in the same delta
  // cycle, independent of PS, frame state, or clock progress.
  assign physical_txd_out_o =
      txd_pre_final & {PHYSICAL_MODULE_COUNT{global_permit_raw_safe}};
endmodule

`default_nettype wire
