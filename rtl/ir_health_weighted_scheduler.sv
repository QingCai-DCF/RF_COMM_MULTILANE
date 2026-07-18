`timescale 1ns/1ps
// Two-stage health-aware weighted deficit scheduler.  Eligibility and safety
// inputs are captured at the request boundary; the final physical TX boundary
// still performs the live P8C permit/kill recheck in ir_data_plane_top.
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
  logic [DEFICIT_WIDTH-1:0] deficit [0:LANE_COUNT-1];
  logic [31:0] scheduled_frames [0:LANE_COUNT-1];
  logic [31:0] scheduled_bytes [0:LANE_COUNT-1];
  logic [31:0] retries [0:LANE_COUNT-1];
  logic [31:0] migrations [0:LANE_COUNT-1];
  logic [31:0] starvation [0:LANE_COUNT-1];
  logic [LANE_WIDTH-1:0] round_robin_pointer;

  logic request_pending;
  logic [LANE_COUNT-1:0] eligible_snapshot;
  logic [LANE_COUNT*WEIGHT_WIDTH-1:0] weight_snapshot;
  logic permit_snapshot, armed_snapshot, kill_snapshot, epoch_valid_snapshot;
  logic credit_valid_snapshot;
  logic [ENTRY_WIDTH-1:0] entry_snapshot;
  logic [COST_WIDTH-1:0] cost_snapshot;
  logic [2:0] priority_snapshot;
  logic retry_snapshot;
  logic [LANE_WIDTH-1:0] last_lane_snapshot;
  logic [15:0] path_epoch_snapshot;
  logic [LANE_COUNT-1:0] affordable_mask;
  logic [LANE_COUNT-1:0] rotated_affordable;
  logic [LANE_COUNT-1:0] first_one_rotated;
  logic [LANE_WIDTH-1:0] rotated_index;
  logic [LANE_WIDTH-1:0] selected_lane;

  assign request_ready_o = !request_pending && (!decision_valid_o || decision_ready_i);

  generate
    for (genvar lane = 0; lane < LANE_COUNT; lane++) begin : g_flatten
      assign scheduled_frames_o[lane*32 +: 32] = scheduled_frames[lane];
      assign scheduled_bytes_o[lane*32 +: 32] = scheduled_bytes[lane];
      assign retry_count_o[lane*32 +: 32] = retries[lane];
      assign migration_count_o[lane*32 +: 32] = migrations[lane];
      assign affordable_mask[lane] = eligible_snapshot[lane] &&
          deficit[lane] >= cost_snapshot;
    end
  endgenerate

  // Rotate, isolate the least-significant set bit, then decode.  This maps to
  // a short barrel/one-hot tree rather than an eight-lane serial if/else chain.
  assign rotated_affordable = (affordable_mask >> round_robin_pointer) |
                              (affordable_mask << (LANE_COUNT-round_robin_pointer));
  assign first_one_rotated = rotated_affordable & (~rotated_affordable + 1'b1);
  always_comb begin
    rotated_index = '0;
    for (int lane = 0; lane < LANE_COUNT; lane++)
      if (first_one_rotated[lane]) rotated_index = lane[LANE_WIDTH-1:0];
    selected_lane = round_robin_pointer + rotated_index;
  end

  always_ff @(posedge clk or negedge rst_n) begin : scheduler_state
    integer lane;
    integer weight_value;
    if (!rst_n) begin
      request_pending <= 1'b0;
      decision_valid_o <= 1'b0;
      decision_admit_o <= 1'b0;
      decision_entry_o <= '0;
      decision_lane_o <= '0;
      decision_path_epoch_o <= 16'd0;
      decision_defer_reason_o <= 4'd0;
      decision_migration_reason_o <= 4'd0;
      round_robin_pointer <= '0;
      maximum_starvation_o <= 32'd0;
      eligible_snapshot <= '0;
      weight_snapshot <= '0;
      permit_snapshot <= 1'b0;
      armed_snapshot <= 1'b0;
      kill_snapshot <= 1'b1;
      epoch_valid_snapshot <= 1'b0;
      credit_valid_snapshot <= 1'b0;
      entry_snapshot <= '0;
      cost_snapshot <= '0;
      priority_snapshot <= '0;
      retry_snapshot <= 1'b0;
      last_lane_snapshot <= '0;
      path_epoch_snapshot <= 16'd0;
      for (lane = 0; lane < LANE_COUNT; lane = lane + 1) begin
        deficit[lane] <= '0;
        scheduled_frames[lane] <= 32'd0;
        scheduled_bytes[lane] <= 32'd0;
        retries[lane] <= 32'd0;
        migrations[lane] <= 32'd0;
        starvation[lane] <= 32'd0;
      end
    end else begin
      if (decision_valid_o && decision_ready_i)
        decision_valid_o <= 1'b0;

      if (clear_counters_i) begin
        maximum_starvation_o <= 32'd0;
        for (lane = 0; lane < LANE_COUNT; lane = lane + 1) begin
          scheduled_frames[lane] <= 32'd0;
          scheduled_bytes[lane] <= 32'd0;
          retries[lane] <= 32'd0;
          migrations[lane] <= 32'd0;
          starvation[lane] <= 32'd0;
        end
      end

      if (request_valid_i && request_ready_o) begin
        request_pending <= 1'b1;
        eligible_snapshot <= active_lane_mask_i & lane_ready_i & lane_health_i &
            mapping_valid_i & frame_admission_i & lane_tx_permit_i &
            duty_headroom_i & fault_free_i;
        weight_snapshot <= lane_weights_i;
        permit_snapshot <= global_permit_effective_i;
        armed_snapshot <= endpoint_armed_i;
        kill_snapshot <= tx_kill_active_i;
        epoch_valid_snapshot <= path_epoch_valid_i;
        credit_valid_snapshot <= receiver_credit_i != 0;
        entry_snapshot <= request_entry_i;
        cost_snapshot <= request_cost_bytes_i;
        priority_snapshot <= request_priority_i;
        retry_snapshot <= request_retry_i;
        last_lane_snapshot <= request_last_lane_i;
        path_epoch_snapshot <= path_epoch_i;
      end

      if (request_pending && (!decision_valid_o || decision_ready_i)) begin
        request_pending <= 1'b0;
        decision_valid_o <= 1'b1;
        decision_admit_o <= 1'b0;
        decision_entry_o <= entry_snapshot;
        decision_lane_o <= '0;
        decision_path_epoch_o <= path_epoch_snapshot;
        decision_defer_reason_o <= 4'd0;
        decision_migration_reason_o <= 4'd0;
        if (!permit_snapshot || !armed_snapshot || kill_snapshot) begin
          decision_defer_reason_o <= 4'd1;
        end else if (!epoch_valid_snapshot) begin
          decision_defer_reason_o <= 4'd2;
        end else if (!credit_valid_snapshot) begin
          decision_defer_reason_o <= 4'd3;
        end else if (eligible_snapshot == '0) begin
          decision_defer_reason_o <= 4'd4;
        end else if (affordable_mask == '0) begin
          decision_defer_reason_o <= 4'd5;
          for (lane = 0; lane < LANE_COUNT; lane = lane + 1) begin
            if (eligible_snapshot[lane]) begin
              weight_value = weight_snapshot[lane*WEIGHT_WIDTH +: WEIGHT_WIDTH];
              if (weight_value == 0) weight_value = 1;
              deficit[lane] <= deficit[lane] + QUANTUM_BYTES * weight_value;
            end
          end
        end else begin
          decision_admit_o <= 1'b1;
          decision_lane_o <= selected_lane;
          decision_migration_reason_o <=
              (retry_snapshot && selected_lane != last_lane_snapshot) ? 4'd1 : 4'd0;
          deficit[selected_lane] <= deficit[selected_lane] - cost_snapshot;
          round_robin_pointer <= (selected_lane == LANE_COUNT-1) ? '0 : selected_lane + 1'b1;
          scheduled_frames[selected_lane] <= scheduled_frames[selected_lane] + 1'b1;
          scheduled_bytes[selected_lane] <= scheduled_bytes[selected_lane] + cost_snapshot;
          if (retry_snapshot) retries[selected_lane] <= retries[selected_lane] + 1'b1;
          if (retry_snapshot && selected_lane != last_lane_snapshot)
            migrations[selected_lane] <= migrations[selected_lane] + 1'b1;
          for (lane = 0; lane < LANE_COUNT; lane = lane + 1) begin
            if (eligible_snapshot[lane]) begin
              if (lane == selected_lane) begin
                starvation[lane] <= 32'd0;
              end else begin
                starvation[lane] <= starvation[lane] + 1'b1;
                if (starvation[lane] + 1'b1 > maximum_starvation_o)
                  maximum_starvation_o <= starvation[lane] + 1'b1;
              end
            end
          end
        end
      end
    end
  end
endmodule
