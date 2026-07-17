`timescale 1ns/1ps
module ir_path_epoch_commit #(
  parameter integer EPOCH_WIDTH = 32
) (
  input  logic                   clk,
  input  logic                   rst_n,
  input  logic                   commit_request,
  input  logic                   phase_valid,
  input  logic                   shadow_valid,
  input  logic                   mapping_checks_pass,
  input  logic                   quiet_or_frame_boundary,
  input  logic                   no_fatal_mapping_fault,
  input  logic [EPOCH_WIDTH-1:0] readback_epoch,
  input  logic [EPOCH_WIDTH-1:0] frame_epoch,
  input  logic [EPOCH_WIDTH-1:0] ack_epoch,
  input  logic [EPOCH_WIDTH-1:0] status_epoch,
  output logic                   commit_event,
  output logic                   commit_accept,
  output logic                   commit_reject,
  output logic [2:0]             commit_reject_reason,
  output logic [EPOCH_WIDTH-1:0] path_epoch,
  output logic                   readback_epoch_current,
  output logic                   frame_epoch_current,
  output logic                   ack_epoch_current,
  output logic                   status_epoch_current
);
  logic request_seen;
  logic conditions_ok;

  always_comb begin
    conditions_ok = phase_valid && shadow_valid && mapping_checks_pass &&
      quiet_or_frame_boundary && no_fatal_mapping_fault;
    commit_event = commit_request && !request_seen && conditions_ok;
    readback_epoch_current = (readback_epoch == path_epoch);
    frame_epoch_current = (frame_epoch == path_epoch);
    ack_epoch_current = (ack_epoch == path_epoch);
    status_epoch_current = (status_epoch == path_epoch);
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      request_seen <= 1'b0;
      commit_accept <= 1'b0;
      commit_reject <= 1'b0;
      commit_reject_reason <= 3'd0;
      path_epoch <= '0;
    end else begin
      commit_accept <= 1'b0;
      commit_reject <= 1'b0;
      commit_reject_reason <= 3'd0;
      if (!commit_request) begin
        request_seen <= 1'b0;
      end else if (!request_seen) begin
        request_seen <= 1'b1;
        if (conditions_ok) begin
          path_epoch <= path_epoch + {{(EPOCH_WIDTH-1){1'b0}}, 1'b1};
          commit_accept <= 1'b1;
        end else begin
          commit_reject <= 1'b1;
          if (!phase_valid) commit_reject_reason <= 3'd1;
          else if (!shadow_valid) commit_reject_reason <= 3'd2;
          else if (!mapping_checks_pass) commit_reject_reason <= 3'd3;
          else if (!quiet_or_frame_boundary) commit_reject_reason <= 3'd4;
          else commit_reject_reason <= 3'd5;
        end
      end
    end
  end
endmodule
