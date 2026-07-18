`timescale 1ns/1ps
// Bundled-data handshake.  src_data_hold is stable from request until the
// returned acknowledgement; the destination samples only after two clocks.
module toggle_handshake #(
  parameter int WIDTH = 64
) (
  input  logic src_clk_i,
  input  logic src_reset_n_i,
  input  logic src_valid_i,
  output logic src_ready_o,
  input  logic [WIDTH-1:0] src_data_i,
  input  logic dst_clk_i,
  input  logic dst_reset_n_i,
  output logic dst_valid_o,
  input  logic dst_ready_i,
  output logic [WIDTH-1:0] dst_data_o
);
  (* DONT_TOUCH="TRUE" *) logic [WIDTH-1:0] src_data_hold;
  logic request_toggle, acknowledge_toggle;
  (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) logic [1:0] ack_sync;
  (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) logic [1:0] request_sync;
  logic request_seen;
  assign src_ready_o = request_toggle == ack_sync[1];
  always_ff @(posedge src_clk_i or negedge src_reset_n_i) begin
    if (!src_reset_n_i) begin
      request_toggle <= 1'b0;
      ack_sync <= '0;
      src_data_hold <= '0;
    end else begin
      ack_sync <= {ack_sync[0], acknowledge_toggle};
      if (src_valid_i && src_ready_o) begin
        src_data_hold <= src_data_i;
        request_toggle <= ~request_toggle;
      end
    end
  end
  always_ff @(posedge dst_clk_i or negedge dst_reset_n_i) begin
    if (!dst_reset_n_i) begin
      request_sync <= '0;
      request_seen <= 1'b0;
      acknowledge_toggle <= 1'b0;
      dst_valid_o <= 1'b0;
      dst_data_o <= '0;
    end else begin
      request_sync <= {request_sync[0], request_toggle};
      if (!dst_valid_o && request_sync[1] != request_seen) begin
        dst_data_o <= src_data_hold;
        dst_valid_o <= 1'b1;
        request_seen <= request_sync[1];
      end
      if (dst_valid_o && dst_ready_i) begin
        dst_valid_o <= 1'b0;
        acknowledge_toggle <= request_seen;
      end
    end
  end
endmodule
