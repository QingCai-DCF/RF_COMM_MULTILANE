`timescale 1ns/1ps
// Toggle-based pulse crossing.  Source pulses must be separated by a returned
// acknowledgement; src_ready_o makes that requirement explicit.
module pulse_sync (
  input  logic src_clk_i,
  input  logic src_reset_n_i,
  input  logic src_pulse_i,
  output logic src_ready_o,
  input  logic dst_clk_i,
  input  logic dst_reset_n_i,
  output logic dst_pulse_o
);
  logic request_toggle;
  logic acknowledge_toggle;
  (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) logic [1:0] ack_sync;
  (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) logic [1:0] request_sync;
  logic request_seen;
  assign src_ready_o = request_toggle == ack_sync[1];
  always_ff @(posedge src_clk_i or negedge src_reset_n_i) begin
    if (!src_reset_n_i) begin
      request_toggle <= 1'b0;
      ack_sync <= '0;
    end else begin
      ack_sync <= {ack_sync[0], acknowledge_toggle};
      if (src_pulse_i && src_ready_o) request_toggle <= ~request_toggle;
    end
  end
  always_ff @(posedge dst_clk_i or negedge dst_reset_n_i) begin
    if (!dst_reset_n_i) begin
      request_sync <= '0;
      request_seen <= 1'b0;
      acknowledge_toggle <= 1'b0;
      dst_pulse_o <= 1'b0;
    end else begin
      request_sync <= {request_sync[0], request_toggle};
      dst_pulse_o <= request_sync[1] != request_seen;
      if (request_sync[1] != request_seen) begin
        request_seen <= request_sync[1];
        acknowledge_toggle <= request_sync[1];
      end
    end
  end
endmodule
