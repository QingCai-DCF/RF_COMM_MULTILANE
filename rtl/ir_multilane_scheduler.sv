`timescale 1ns/1ps
module ir_multilane_scheduler #(
  parameter int LANE_COUNT = 8,
  parameter logic [LANE_COUNT-1:0] DEFAULT_LANE_ENABLE_MASK = {{(LANE_COUNT-1){1'b0}}, 1'b1},
  parameter logic [LANE_COUNT-1:0] KNOWN_BAD_RAW_DIRECTION_MASK = {{(LANE_COUNT-2){1'b0}}, 1'b1, 1'b0}
) (
  input  logic                    clk,
  input  logic                    rst_n,
  input  logic                    clear_sticky,
  input  logic                    commit_profile,

  input  logic [LANE_COUNT-1:0]   requested_lane_enable_mask,
  input  logic [LANE_COUNT-1:0]   requested_reliable_lane_mask,
  input  logic [LANE_COUNT-1:0]   lane_fault_pulse,
  input  logic [LANE_COUNT-1:0]   lane_recovered_pulse,

  output logic [LANE_COUNT-1:0]   requested_lane_enable_readback,
  output logic [LANE_COUNT-1:0]   requested_reliable_lane_readback,
  output logic [LANE_COUNT-1:0]   blocked_lane_mask,
  output logic [LANE_COUNT-1:0]   sticky_bad_lane_mask,
  output logic [LANE_COUNT-1:0]   effective_lane_enable_mask,
  output logic [LANE_COUNT-1:0]   effective_reliable_lane_mask,
  output logic [LANE_COUNT-1:0]   lane_enable_readback,
  output logic [LANE_COUNT-1:0]   reliable_lane_readback,

  output logic                    lane1_reliable_blocked,
  output logic                    fallback_to_lane0_active,
  output logic                    no_reliable_lane_sticky,
  output logic                    fault_isolated_pulse,
  output logic [$clog2(LANE_COUNT)-1:0] selected_tx_lane,
  output logic [$clog2(LANE_COUNT)-1:0] selected_ack_lane,
  output logic [31:0]             debug_status
);
  localparam logic [LANE_COUNT-1:0] LANE0_MASK = {{(LANE_COUNT-1){1'b0}}, 1'b1};
  localparam bit LANE1_DEFAULT_DISABLED = (LANE_COUNT > 1) ? !DEFAULT_LANE_ENABLE_MASK[1] : 1'b1;
  localparam string known_bad_raw_direction = "AB_L1";

  logic [LANE_COUNT-1:0] profile_lane_enable_mask;
  logic [LANE_COUNT-1:0] profile_reliable_lane_mask;
  logic [LANE_COUNT-1:0] sanitized_enable_mask;
  logic [LANE_COUNT-1:0] sanitized_reliable_mask;
  logic [LANE_COUNT-1:0] unblocked_enable_mask;
  logic [LANE_COUNT-1:0] unblocked_reliable_mask;
  logic [LANE_COUNT-1:0] healthy_enable_mask;
  logic [LANE_COUNT-1:0] healthy_reliable_mask;
  logic lane0_available_for_fallback;

  function automatic logic [$clog2(LANE_COUNT)-1:0] first_enabled_lane(
    input logic [LANE_COUNT-1:0] mask
  );
    logic [$clog2(LANE_COUNT)-1:0] result;
    logic found;
    begin
      result = '0;
      found = 1'b0;
      for (int lane = 0; lane < LANE_COUNT; lane++) begin
        if (mask[lane] && !found) begin
          result = lane[$clog2(LANE_COUNT)-1:0];
          found = 1'b1;
        end
      end
      first_enabled_lane = result;
    end
  endfunction

  assign blocked_lane_mask = KNOWN_BAD_RAW_DIRECTION_MASK;
  assign sanitized_enable_mask =
      (profile_lane_enable_mask == '0) ? DEFAULT_LANE_ENABLE_MASK : profile_lane_enable_mask;
  assign sanitized_reliable_mask =
      (profile_reliable_lane_mask == '0) ? sanitized_enable_mask : profile_reliable_lane_mask;
  assign unblocked_enable_mask = sanitized_enable_mask & ~blocked_lane_mask;
  assign unblocked_reliable_mask = sanitized_reliable_mask & unblocked_enable_mask;
  assign healthy_enable_mask = unblocked_enable_mask & ~sticky_bad_lane_mask;
  assign healthy_reliable_mask = unblocked_reliable_mask & ~sticky_bad_lane_mask;
  assign lane0_available_for_fallback = ((LANE0_MASK & ~blocked_lane_mask & ~sticky_bad_lane_mask) != '0);

  always_comb begin
    effective_lane_enable_mask = healthy_enable_mask;
    effective_reliable_lane_mask = healthy_reliable_mask;
    fallback_to_lane0_active = 1'b0;

    if (healthy_reliable_mask == '0 && lane0_available_for_fallback) begin
      effective_lane_enable_mask = LANE0_MASK;
      effective_reliable_lane_mask = LANE0_MASK;
      fallback_to_lane0_active = 1'b1;
    end
  end

  assign lane_enable_readback = effective_lane_enable_mask;
  assign reliable_lane_readback = effective_reliable_lane_mask;
  assign lane1_reliable_blocked =
      (LANE_COUNT > 1) &&
      sanitized_reliable_mask[1] &&
      blocked_lane_mask[1] &&
      !effective_reliable_lane_mask[1];
  assign selected_tx_lane = first_enabled_lane(effective_reliable_lane_mask);
  assign selected_ack_lane = first_enabled_lane(effective_reliable_lane_mask);
  assign debug_status = {
    no_reliable_lane_sticky,
    fallback_to_lane0_active,
    lane1_reliable_blocked,
    fault_isolated_pulse,
    4'd0,
    effective_reliable_lane_mask[7:0],
    sticky_bad_lane_mask[7:0],
    blocked_lane_mask[7:0]
  };

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      profile_lane_enable_mask <= DEFAULT_LANE_ENABLE_MASK;
      profile_reliable_lane_mask <= DEFAULT_LANE_ENABLE_MASK;
      requested_lane_enable_readback <= DEFAULT_LANE_ENABLE_MASK;
      requested_reliable_lane_readback <= DEFAULT_LANE_ENABLE_MASK;
      sticky_bad_lane_mask <= '0;
      no_reliable_lane_sticky <= 1'b0;
      fault_isolated_pulse <= 1'b0;
    end else begin
      fault_isolated_pulse <= 1'b0;

      if (commit_profile) begin
        profile_lane_enable_mask <=
            (requested_lane_enable_mask == '0) ? DEFAULT_LANE_ENABLE_MASK : requested_lane_enable_mask;
        profile_reliable_lane_mask <=
            (requested_reliable_lane_mask == '0) ?
                ((requested_lane_enable_mask == '0) ? DEFAULT_LANE_ENABLE_MASK : requested_lane_enable_mask) :
                requested_reliable_lane_mask;
        requested_lane_enable_readback <=
            (requested_lane_enable_mask == '0) ? DEFAULT_LANE_ENABLE_MASK : requested_lane_enable_mask;
        requested_reliable_lane_readback <=
            (requested_reliable_lane_mask == '0) ?
                ((requested_lane_enable_mask == '0) ? DEFAULT_LANE_ENABLE_MASK : requested_lane_enable_mask) :
                requested_reliable_lane_mask;
      end

      if (clear_sticky) begin
        sticky_bad_lane_mask <= '0;
        no_reliable_lane_sticky <= 1'b0;
      end else begin
        sticky_bad_lane_mask <= (sticky_bad_lane_mask | lane_fault_pulse) & ~lane_recovered_pulse;
        if ((lane_fault_pulse & effective_lane_enable_mask) != '0) begin
          fault_isolated_pulse <= 1'b1;
        end
        if (effective_reliable_lane_mask == '0) begin
          no_reliable_lane_sticky <= 1'b1;
        end
      end
    end
  end
endmodule
