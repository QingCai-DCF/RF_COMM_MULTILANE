`timescale 1ns/1ps
module ir_retry_migration #(
  parameter int LANE_COUNT = 8
) (
  input  logic                      entry_valid_i,
  input  logic                      entry_acked_i,
  input  logic                      retry_pending_i,
  input  logic [$clog2(LANE_COUNT)-1:0] last_lane_i,
  input  logic [LANE_COUNT-1:0]     eligible_lane_mask_i,
  input  logic [$clog2(LANE_COUNT)-1:0] scheduler_lane_i,
  input  logic                      scheduler_admit_i,
  output logic                      migration_allowed_o,
  output logic                      migration_required_o,
  output logic [$clog2(LANE_COUNT)-1:0] migrated_lane_o,
  output logic [3:0]                migration_reason_o
);
  always_comb begin
    migration_allowed_o = entry_valid_i && !entry_acked_i && retry_pending_i;
    migration_required_o = 1'b0;
    migrated_lane_o = scheduler_lane_i;
    migration_reason_o = 4'd0;
    if (migration_allowed_o && scheduler_admit_i &&
        eligible_lane_mask_i[scheduler_lane_i]) begin
      if (scheduler_lane_i != last_lane_i) begin
        migration_required_o = 1'b1;
        migration_reason_o = 4'd1; // health/safety/path retry migration
      end
    end else if (entry_acked_i) begin
      migration_reason_o = 4'd2; // explicitly blocked: already ACKed
    end else if (migration_allowed_o && eligible_lane_mask_i == '0) begin
      migration_reason_o = 4'd3; // all lanes unavailable
    end
  end
endmodule
