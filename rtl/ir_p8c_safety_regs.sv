`timescale 1ns/1ps
`default_nettype none
`include "generated/ir_register_map_defs.svh"

// Additive P8C register front-end. Permit state is status-only; the only
// software action is a conditional arm request evaluated by the endpoint.
module ir_p8c_safety_regs #(
  parameter integer PHYSICAL_MODULE_COUNT = 32
) (
  input  wire                                   clk,
  input  wire                                   rst_n,
  input  wire                                   wr_en,
  input  wire [11:0]                            wr_addr,
  input  wire [31:0]                            wr_data,
  input  wire                                   rd_en,
  input  wire [11:0]                            rd_addr,
  output reg  [31:0]                            rd_data,
  output reg                                    rd_valid,
  output reg                                    endpoint_arm_request_o,
  output reg                                    endpoint_disarm_request_o,
  output reg                                    full_shutdown_request_o,
  output reg                                    safety_fault_clear_request_o,
  output reg                                    snapshot_request_o,
  output reg                                    telemetry_clear_request_o,
  input  wire                                   global_permit_raw_i,
  input  wire                                   global_permit_sync_i,
  input  wire                                   global_permit_effective_i,
  input  wire                                   endpoint_armed_i,
  input  wire                                   tx_kill_active_i,
  input  wire                                   partial_frame_abort_block_i,
  input  wire                                   endpoint_fatal_fault_i,
  input  wire                                   arm_accept_pulse_i,
  input  wire                                   arm_reject_pulse_i,
  input  wire [4:0]                             arm_reject_reason_i,
  input  wire                                   fault_clear_accept_pulse_i,
  input  wire [31:0]                            global_permit_rise_count_i,
  input  wire [31:0]                            global_permit_fall_count_i,
  input  wire [31:0]                            global_permit_drop_during_frame_count_i,
  input  wire [31:0]                            global_permit_rearm_count_i,
  input  wire [4:0]                             last_global_permit_drop_reason_i,
  input  wire [4:0]                             last_tx_kill_reason_i,
  input  wire [31:0]                            bank_fault_mask_i,
  input  wire [31:0]                            lane_tx_permit_mask_i,
  input  wire [31:0]                            effective_tx_enable_mask_i,
  input  wire [31:0]                            physical_module_selected_mask_i,
  input  wire [31:0]                            rolling_window_cycles_i,
  input  wire [31:0]                            hard_limit_cycles_i,
  input  wire [31:0]                            target_limit_cycles_i,
  input  wire [PHYSICAL_MODULE_COUNT*32-1:0]     rolling_high_cycles_flat_i,
  input  wire [PHYSICAL_MODULE_COUNT*32-1:0]     rolling_high_cycles_max_seen_flat_i,
  input  wire [PHYSICAL_MODULE_COUNT*32-1:0]     duty_headroom_cycles_flat_i,
  input  wire [PHYSICAL_MODULE_COUNT*32-1:0]     duty_target_throttle_count_flat_i,
  input  wire [PHYSICAL_MODULE_COUNT*32-1:0]     duty_hard_fault_count_flat_i,
  input  wire [PHYSICAL_MODULE_COUNT*32-1:0]     continuous_high_cycles_flat_i,
  input  wire [PHYSICAL_MODULE_COUNT*32-1:0]     longest_high_cycles_seen_flat_i,
  input  wire [PHYSICAL_MODULE_COUNT*32-1:0]     stuck_high_fault_count_flat_i,
  input  wire [PHYSICAL_MODULE_COUNT*32-1:0]     stuck_high_kill_count_flat_i,
  input  wire [PHYSICAL_MODULE_COUNT*32-1:0]     cooldown_remaining_flat_i,
  input  wire [PHYSICAL_MODULE_COUNT*32-1:0]     charge_count_flat_i,
  input  wire [PHYSICAL_MODULE_COUNT*32-1:0]     rx_pulse_count_flat_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        duty_target_throttle_mask_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        duty_hard_fault_mask_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        stuck_high_fault_mask_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        duty_history_valid_mask_i,
  input  wire [PHYSICAL_MODULE_COUNT-1:0]        cooldown_active_mask_i
);
  reg [4:0] snapshot_index_q;
  reg snapshot_valid_q;
  reg [31:0] snapshot_rolling_high_q;
  reg [31:0] snapshot_rolling_max_q;
  reg [31:0] snapshot_window_q;
  reg [31:0] snapshot_hard_limit_q;
  reg [31:0] snapshot_target_limit_q;
  reg [31:0] snapshot_headroom_q;
  reg [31:0] snapshot_throttle_count_q;
  reg [31:0] snapshot_hard_fault_count_q;
  reg [31:0] snapshot_continuous_high_q;
  reg [31:0] snapshot_longest_high_q;
  reg [31:0] snapshot_stuck_fault_count_q;
  reg [31:0] snapshot_stuck_kill_count_q;
  reg [31:0] snapshot_cooldown_remaining_q;
  reg [31:0] snapshot_charge_count_q;
  reg [31:0] snapshot_rx_pulse_count_q;
  reg [31:0] snapshot_flags_q;

  wire snapshot_index_valid = snapshot_index_q < PHYSICAL_MODULE_COUNT;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      endpoint_arm_request_o <= 1'b0;
      endpoint_disarm_request_o <= 1'b0;
      full_shutdown_request_o <= 1'b0;
      safety_fault_clear_request_o <= 1'b0;
      snapshot_request_o <= 1'b0;
      telemetry_clear_request_o <= 1'b0;
      snapshot_index_q <= 5'd0;
      snapshot_valid_q <= 1'b0;
      snapshot_rolling_high_q <= 32'd0;
      snapshot_rolling_max_q <= 32'd0;
      snapshot_window_q <= 32'd0;
      snapshot_hard_limit_q <= 32'd0;
      snapshot_target_limit_q <= 32'd0;
      snapshot_headroom_q <= 32'd0;
      snapshot_throttle_count_q <= 32'd0;
      snapshot_hard_fault_count_q <= 32'd0;
      snapshot_continuous_high_q <= 32'd0;
      snapshot_longest_high_q <= 32'd0;
      snapshot_stuck_fault_count_q <= 32'd0;
      snapshot_stuck_kill_count_q <= 32'd0;
      snapshot_cooldown_remaining_q <= 32'd0;
      snapshot_charge_count_q <= 32'd0;
      snapshot_rx_pulse_count_q <= 32'd0;
      snapshot_flags_q <= 32'd0;
    end else begin
      endpoint_arm_request_o <= 1'b0;
      endpoint_disarm_request_o <= 1'b0;
      full_shutdown_request_o <= 1'b0;
      safety_fault_clear_request_o <= 1'b0;
      snapshot_request_o <= 1'b0;
      telemetry_clear_request_o <= 1'b0;

      if (wr_en && wr_addr == `IR_REG_P8C_SNAPSHOT_INDEX)
        snapshot_index_q <= wr_data[4:0];

      if (wr_en && wr_addr == `IR_REG_P8C_CONTROL) begin
        endpoint_arm_request_o <= wr_data[`IR_P8C_CONTROL_ENDPOINT_ARM_REQUEST_SHIFT];
        endpoint_disarm_request_o <= wr_data[`IR_P8C_CONTROL_ENDPOINT_DISARM_REQUEST_SHIFT];
        full_shutdown_request_o <= wr_data[`IR_P8C_CONTROL_FULL_SHUTDOWN_REQUEST_SHIFT];
        safety_fault_clear_request_o <= wr_data[`IR_P8C_CONTROL_SAFETY_FAULT_CLEAR_REQUEST_SHIFT];
        snapshot_request_o <= wr_data[`IR_P8C_CONTROL_SNAPSHOT_REQUEST_SHIFT];
        telemetry_clear_request_o <= wr_data[`IR_P8C_CONTROL_TELEMETRY_CLEAR_REQUEST_SHIFT];
        if (wr_data[`IR_P8C_CONTROL_SNAPSHOT_REQUEST_SHIFT]) begin
          snapshot_valid_q <= snapshot_index_valid;
          if (snapshot_index_valid) begin
            snapshot_rolling_high_q <= rolling_high_cycles_flat_i[snapshot_index_q*32 +: 32];
            snapshot_rolling_max_q <= rolling_high_cycles_max_seen_flat_i[snapshot_index_q*32 +: 32];
            snapshot_window_q <= rolling_window_cycles_i;
            snapshot_hard_limit_q <= hard_limit_cycles_i;
            snapshot_target_limit_q <= target_limit_cycles_i;
            snapshot_headroom_q <= duty_headroom_cycles_flat_i[snapshot_index_q*32 +: 32];
            snapshot_throttle_count_q <= duty_target_throttle_count_flat_i[snapshot_index_q*32 +: 32];
            snapshot_hard_fault_count_q <= duty_hard_fault_count_flat_i[snapshot_index_q*32 +: 32];
            snapshot_continuous_high_q <= continuous_high_cycles_flat_i[snapshot_index_q*32 +: 32];
            snapshot_longest_high_q <= longest_high_cycles_seen_flat_i[snapshot_index_q*32 +: 32];
            snapshot_stuck_fault_count_q <= stuck_high_fault_count_flat_i[snapshot_index_q*32 +: 32];
            snapshot_stuck_kill_count_q <= stuck_high_kill_count_flat_i[snapshot_index_q*32 +: 32];
            snapshot_cooldown_remaining_q <= cooldown_remaining_flat_i[snapshot_index_q*32 +: 32];
            snapshot_charge_count_q <= charge_count_flat_i[snapshot_index_q*32 +: 32];
            snapshot_rx_pulse_count_q <= rx_pulse_count_flat_i[snapshot_index_q*32 +: 32];
            snapshot_flags_q <= {
              27'd0,
              cooldown_active_mask_i[snapshot_index_q],
              duty_history_valid_mask_i[snapshot_index_q],
              stuck_high_fault_mask_i[snapshot_index_q],
              duty_hard_fault_mask_i[snapshot_index_q],
              duty_target_throttle_mask_i[snapshot_index_q]
            };
          end
        end
      end
      // Writes to all RO permit/status/counter addresses are intentionally ignored.
    end
  end

  always @* begin
    rd_data = 32'd0;
    rd_valid = rd_en;
    if (rd_en) begin
      case (rd_addr)
        `IR_REG_P8C_CONTROL: rd_data = 32'd0;
        `IR_REG_P8C_PERMIT_STATUS: rd_data = {
          24'd0,
          endpoint_fatal_fault_i,
          snapshot_valid_q,
          partial_frame_abort_block_i,
          tx_kill_active_i,
          endpoint_armed_i,
          global_permit_effective_i,
          global_permit_sync_i,
          global_permit_raw_i
        };
        `IR_REG_P8C_PERMIT_RISE_COUNT: rd_data = global_permit_rise_count_i;
        `IR_REG_P8C_PERMIT_FALL_COUNT: rd_data = global_permit_fall_count_i;
        `IR_REG_P8C_PERMIT_DROP_DURING_FRAME_COUNT: rd_data = global_permit_drop_during_frame_count_i;
        `IR_REG_P8C_PERMIT_REARM_COUNT: rd_data = global_permit_rearm_count_i;
        `IR_REG_P8C_LAST_REASONS: rd_data = {19'd0, last_tx_kill_reason_i, 3'd0, last_global_permit_drop_reason_i};
        `IR_REG_P8C_BANK_FAULT_MASK: rd_data = bank_fault_mask_i;
        `IR_REG_P8C_LANE_TX_PERMIT_MASK: rd_data = lane_tx_permit_mask_i;
        `IR_REG_P8C_EFFECTIVE_TX_ENABLE_MASK: rd_data = effective_tx_enable_mask_i;
        `IR_REG_P8C_PHYSICAL_MODULE_SELECTED_MASK: rd_data = physical_module_selected_mask_i;
        `IR_REG_P8C_ARM_STATUS: rd_data = {19'd0, arm_reject_reason_i, 5'd0,
          fault_clear_accept_pulse_i, arm_reject_pulse_i, arm_accept_pulse_i};
        `IR_REG_P8C_SNAPSHOT_INDEX: rd_data = {27'd0, snapshot_index_q};
        `IR_REG_P8C_SNAPSHOT_ROLLING_HIGH: rd_data = snapshot_rolling_high_q;
        `IR_REG_P8C_SNAPSHOT_ROLLING_MAX: rd_data = snapshot_rolling_max_q;
        `IR_REG_P8C_SNAPSHOT_WINDOW_CYCLES: rd_data = snapshot_window_q;
        `IR_REG_P8C_SNAPSHOT_HARD_LIMIT: rd_data = snapshot_hard_limit_q;
        `IR_REG_P8C_SNAPSHOT_TARGET_LIMIT: rd_data = snapshot_target_limit_q;
        `IR_REG_P8C_SNAPSHOT_DUTY_HEADROOM: rd_data = snapshot_headroom_q;
        `IR_REG_P8C_SNAPSHOT_TARGET_THROTTLE_COUNT: rd_data = snapshot_throttle_count_q;
        `IR_REG_P8C_SNAPSHOT_HARD_FAULT_COUNT: rd_data = snapshot_hard_fault_count_q;
        `IR_REG_P8C_SNAPSHOT_CONTINUOUS_HIGH: rd_data = snapshot_continuous_high_q;
        `IR_REG_P8C_SNAPSHOT_LONGEST_HIGH: rd_data = snapshot_longest_high_q;
        `IR_REG_P8C_SNAPSHOT_STUCK_FAULT_COUNT: rd_data = snapshot_stuck_fault_count_q;
        `IR_REG_P8C_SNAPSHOT_STUCK_KILL_COUNT: rd_data = snapshot_stuck_kill_count_q;
        `IR_REG_P8C_SNAPSHOT_COOLDOWN_REMAINING: rd_data = snapshot_cooldown_remaining_q;
        `IR_REG_P8C_SNAPSHOT_CHARGE_COUNT: rd_data = snapshot_charge_count_q;
        `IR_REG_P8C_SNAPSHOT_FLAGS: rd_data = snapshot_flags_q;
        `IR_REG_P8C_SNAPSHOT_RX_PULSE_COUNT: rd_data = snapshot_rx_pulse_count_q;
        `IR_REG_P8C_REGISTER_MAP_VERSION: rd_data = `IR_REGISTER_MAP_VERSION;
        `IR_REG_P8C_REGISTER_MAP_HASH_LOW: rd_data = `IR_REGISTER_MAP_HASH_LOW;
        default: rd_data = 32'd0;
      endcase
    end
  end
endmodule

`default_nettype wire
