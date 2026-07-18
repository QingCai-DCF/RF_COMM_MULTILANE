`timescale 1ns/1ps
module ir_health_weighted_scheduler #(
  parameter int LANE_COUNT = 8,
  parameter int ENTRY_WIDTH = 6,
  parameter int WEIGHT_WIDTH = 8,
  parameter int COST_WIDTH = 16,
  parameter int DEFICIT_WIDTH = 24,
  parameter int QUANTUM_BYTES = 288,
  parameter int STARVATION_BOUND = 4096
) (
  input  logic                          clk,
  input  logic                          rst_n,
  input  logic                          clear_counters_i,
  input  logic [LANE_COUNT*WEIGHT_WIDTH-1:0] lane_weights_i,
  input  logic [LANE_COUNT-1:0]         active_lane_mask_i,
  input  logic [LANE_COUNT-1:0]         lane_ready_i,
  input  logic [LANE_COUNT-1:0]         lane_health_i,
  input  logic [LANE_COUNT-1:0]         mapping_valid_i,
  input  logic [LANE_COUNT-1:0]         frame_admission_i,
  input  logic [LANE_COUNT-1:0]         lane_tx_permit_i,
  input  logic [LANE_COUNT-1:0]         duty_headroom_i,
  input  logic [LANE_COUNT-1:0]         fault_free_i,
  input  logic                          global_permit_effective_i,
  input  logic                          endpoint_armed_i,
  input  logic                          tx_kill_active_i,
  input  logic                          path_epoch_valid_i,
  input  logic [15:0]                   receiver_credit_i,
  input  logic [15:0]                   path_epoch_i,
  input  logic                          request_valid_i,
  output logic                          request_ready_o,
  input  logic [ENTRY_WIDTH-1:0]        request_entry_i,
  input  logic [COST_WIDTH-1:0]         request_cost_bytes_i,
  input  logic [2:0]                    request_priority_i,
  input  logic                          request_retry_i,
  input  logic [$clog2(LANE_COUNT)-1:0] request_last_lane_i,
  output logic                          decision_valid_o,
  input  logic                          decision_ready_i,
  output logic                          decision_admit_o,
  output logic [ENTRY_WIDTH-1:0]        decision_entry_o,
  output logic [$clog2(LANE_COUNT)-1:0] decision_lane_o,
  output logic [15:0]                   decision_path_epoch_o,
  output logic [3:0]                    decision_defer_reason_o,
  output logic [3:0]                    decision_migration_reason_o,
  output logic [LANE_COUNT*32-1:0]      scheduled_frames_o,
  output logic [LANE_COUNT*32-1:0]      scheduled_bytes_o,
  output logic [LANE_COUNT*32-1:0]      retry_count_o,
  output logic [LANE_COUNT*32-1:0]      migration_count_o,
  output logic [31:0]                   maximum_starvation_o
);
  localparam int LANE_WIDTH = $clog2(LANE_COUNT);
  logic [LANE_COUNT-1:0] eligible_mask;
  logic [DEFICIT_WIDTH-1:0] deficit [0:LANE_COUNT-1];
  logic [31:0] scheduled_frames [0:LANE_COUNT-1];
  logic [31:0] scheduled_bytes [0:LANE_COUNT-1];
  logic [31:0] retries [0:LANE_COUNT-1];
  logic [31:0] migrations [0:LANE_COUNT-1];
  logic [31:0] starvation [0:LANE_COUNT-1];
  logic [LANE_WIDTH-1:0] round_robin_pointer;

  assign eligible_mask = active_lane_mask_i & lane_ready_i & lane_health_i &
                         mapping_valid_i & frame_admission_i & lane_tx_permit_i &
                         duty_headroom_i & fault_free_i;
  assign request_ready_o = !decision_valid_o || decision_ready_i;

  generate
    for (genvar lane = 0; lane < LANE_COUNT; lane++) begin : g_flatten
      assign scheduled_frames_o[lane*32 +: 32] = scheduled_frames[lane];
      assign scheduled_bytes_o[lane*32 +: 32] = scheduled_bytes[lane];
      assign retry_count_o[lane*32 +: 32] = retries[lane];
      assign migration_count_o[lane*32 +: 32] = migrations[lane];
    end
  endgenerate

  always_ff @(posedge clk or negedge rst_n) begin : scheduler_state
    integer scan;
    integer lane_index;
    integer selected_lane;
    integer weight_value;
    logic found;
    if (!rst_n) begin
      decision_valid_o <= 1'b0;
      decision_admit_o <= 1'b0;
      decision_entry_o <= '0;
      decision_lane_o <= '0;
      decision_path_epoch_o <= 16'd0;
      decision_defer_reason_o <= 4'd0;
      decision_migration_reason_o <= 4'd0;
      round_robin_pointer <= '0;
      maximum_starvation_o <= 32'd0;
      for (lane_index = 0; lane_index < LANE_COUNT; lane_index = lane_index + 1) begin
        deficit[lane_index] <= '0;
        scheduled_frames[lane_index] <= 32'd0;
        scheduled_bytes[lane_index] <= 32'd0;
        retries[lane_index] <= 32'd0;
        migrations[lane_index] <= 32'd0;
        starvation[lane_index] <= 32'd0;
      end
    end else begin
      if (decision_valid_o && decision_ready_i) decision_valid_o <= 1'b0;
      if (clear_counters_i) begin
        maximum_starvation_o <= 32'd0;
        for (lane_index = 0; lane_index < LANE_COUNT; lane_index = lane_index + 1) begin
          scheduled_frames[lane_index] <= 32'd0;
          scheduled_bytes[lane_index] <= 32'd0;
          retries[lane_index] <= 32'd0;
          migrations[lane_index] <= 32'd0;
          starvation[lane_index] <= 32'd0;
        end
      end
      if (request_valid_i && request_ready_o) begin
        decision_valid_o <= 1'b1;
        decision_admit_o <= 1'b0;
        decision_entry_o <= request_entry_i;
        decision_lane_o <= '0;
        decision_path_epoch_o <= path_epoch_i;
        decision_defer_reason_o <= 4'd0;
        decision_migration_reason_o <= 4'd0;
        found = 1'b0;
        selected_lane = 0;
        if (!global_permit_effective_i || !endpoint_armed_i || tx_kill_active_i) begin
          decision_defer_reason_o <= 4'd1;
        end else if (!path_epoch_valid_i) begin
          decision_defer_reason_o <= 4'd2;
        end else if (receiver_credit_i == 0) begin
          decision_defer_reason_o <= 4'd3;
        end else if (eligible_mask == '0) begin
          decision_defer_reason_o <= 4'd4;
        end else begin
          for (scan = 0; scan < LANE_COUNT; scan = scan + 1) begin
            lane_index = (round_robin_pointer + scan) % LANE_COUNT;
            if (!found && eligible_mask[lane_index] &&
                (deficit[lane_index] >= request_cost_bytes_i)) begin
              found = 1'b1;
              selected_lane = lane_index;
            end
          end
          if (found) begin
            decision_admit_o <= 1'b1;
            decision_lane_o <= selected_lane[LANE_WIDTH-1:0];
            decision_migration_reason_o <=
                (request_retry_i && selected_lane != request_last_lane_i) ? 4'd1 : 4'd0;
            deficit[selected_lane] <= deficit[selected_lane] - request_cost_bytes_i;
            round_robin_pointer <= (selected_lane == LANE_COUNT-1) ? '0 :
                                   selected_lane[LANE_WIDTH-1:0] + 1'b1;
            scheduled_frames[selected_lane] <= scheduled_frames[selected_lane] + 1'b1;
            scheduled_bytes[selected_lane] <= scheduled_bytes[selected_lane] + request_cost_bytes_i;
            if (request_retry_i) retries[selected_lane] <= retries[selected_lane] + 1'b1;
            if (request_retry_i && selected_lane != request_last_lane_i)
              migrations[selected_lane] <= migrations[selected_lane] + 1'b1;
            for (lane_index = 0; lane_index < LANE_COUNT; lane_index = lane_index + 1) begin
              if (eligible_mask[lane_index]) begin
                if (lane_index == selected_lane) begin
                  starvation[lane_index] <= 32'd0;
                end else begin
                  starvation[lane_index] <= starvation[lane_index] + 1'b1;
                  if (starvation[lane_index] + 1'b1 > maximum_starvation_o)
                    maximum_starvation_o <= starvation[lane_index] + 1'b1;
                end
              end
            end
          end else begin
            decision_defer_reason_o <= 4'd5;
            for (lane_index = 0; lane_index < LANE_COUNT; lane_index = lane_index + 1) begin
              if (eligible_mask[lane_index]) begin
                weight_value = lane_weights_i[lane_index*WEIGHT_WIDTH +: WEIGHT_WIDTH];
                if (weight_value == 0) weight_value = 1;
                deficit[lane_index] <= deficit[lane_index] + QUANTUM_BYTES * weight_value;
              end
            end
          end
        end
      end
    end
  end
endmodule
