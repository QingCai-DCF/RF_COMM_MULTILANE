`timescale 1ns/1ps
// Bundled-data toggle handshake for descriptor/control metadata.  src_data_hold
// is written before the request toggle and remains stable until the synchronized
// acknowledgement returns.  Both domains must use coordinated session reset;
// reset assertion is asynchronous and deassertion is synchronized externally.
module ir_p8d_async_descriptor_bridge #(
  parameter int WIDTH=64
) (
  input logic src_clk,input logic src_rst_n,input logic src_valid_i,
  output logic src_ready_o,input logic [WIDTH-1:0] src_data_i,
  input logic dst_clk,input logic dst_rst_n,output logic dst_valid_o,
  input logic dst_ready_i,output logic [WIDTH-1:0] dst_data_o
);
  logic [WIDTH-1:0] src_data_hold;
  logic request_toggle,ack_toggle;
  (* ASYNC_REG="TRUE" *) logic ack_sync1,ack_sync2;
  (* ASYNC_REG="TRUE" *) logic request_sync1,request_sync2;
  logic request_seen;
  assign src_ready_o=(request_toggle==ack_sync2);

  always_ff @(posedge src_clk or negedge src_rst_n) begin
    if(!src_rst_n)begin
      src_data_hold<='0;request_toggle<=0;ack_sync1<=0;ack_sync2<=0;
    end else begin
      ack_sync1<=ack_toggle;ack_sync2<=ack_sync1;
      if(src_valid_i&&src_ready_o)begin
        src_data_hold<=src_data_i;request_toggle<=~request_toggle;
      end
    end
  end
  always_ff @(posedge dst_clk or negedge dst_rst_n) begin
    if(!dst_rst_n)begin
      request_sync1<=0;request_sync2<=0;request_seen<=0;ack_toggle<=0;
      dst_valid_o<=0;dst_data_o<='0;
    end else begin
      request_sync1<=request_toggle;request_sync2<=request_sync1;
      if(!dst_valid_o&&request_sync2!=request_seen)begin
        // The data bus has been stable for at least two destination clocks.
        dst_data_o<=src_data_hold;dst_valid_o<=1;request_seen<=request_sync2;
      end
      if(dst_valid_o&&dst_ready_i)begin
        dst_valid_o<=0;ack_toggle<=request_seen;
      end
    end
  end
endmodule
