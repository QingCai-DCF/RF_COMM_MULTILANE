`timescale 1ns/1ps
`default_nettype wire

module p10_1_descriptor_batch #(
  parameter int unsigned RING_DEPTH = 64,
  parameter int unsigned BATCH = 16,
  localparam int unsigned PTR_W = $clog2(RING_DEPTH)
) (
  input  logic                 clk,
  input  logic                 rst_n,
  input  logic                 clear_i,
  input  logic                 submit_i,
  output logic                 submit_ready_o,
  input  logic                 complete_i,
  output logic                 complete_valid_o,
  output logic                 interrupt_o,
  output logic [PTR_W:0]       outstanding_o,
  output logic [31:0]          producer_generation_o,
  output logic [31:0]          consumer_generation_o,
  output logic [63:0]          submitted_o,
  output logic [63:0]          completed_o,
  output logic [63:0]          double_completion_o
);
  logic [PTR_W-1:0] producer_q;
  logic [PTR_W-1:0] consumer_q;
  logic [$clog2(BATCH+1)-1:0] batch_completed_q;

  assign submit_ready_o = outstanding_o < RING_DEPTH;
  assign complete_valid_o = outstanding_o != 0;

  always_ff @(posedge clk) begin
    if (!rst_n || clear_i) begin
      producer_q <= '0;
      consumer_q <= '0;
      outstanding_o <= '0;
      producer_generation_o <= '0;
      consumer_generation_o <= '0;
      submitted_o <= '0;
      completed_o <= '0;
      double_completion_o <= '0;
      batch_completed_q <= '0;
      interrupt_o <= 1'b0;
    end else begin
      interrupt_o <= 1'b0;
      if (submit_i && submit_ready_o) begin
        producer_q <= producer_q + 1'b1;
        submitted_o <= submitted_o + 1'b1;
        if (producer_q == RING_DEPTH-1)
          producer_generation_o <= producer_generation_o + 1'b1;
      end
      if (complete_i && complete_valid_o) begin
        consumer_q <= consumer_q + 1'b1;
        completed_o <= completed_o + 1'b1;
        if (consumer_q == RING_DEPTH-1)
          consumer_generation_o <= consumer_generation_o + 1'b1;
        if (batch_completed_q == BATCH-1) begin
          batch_completed_q <= '0;
          interrupt_o <= 1'b1;
        end else
          batch_completed_q <= batch_completed_q + 1'b1;
      end else if (complete_i && !complete_valid_o)
        double_completion_o <= double_completion_o + 1'b1;
      unique case ({submit_i && submit_ready_o,
                    complete_i && complete_valid_o})
        2'b10: outstanding_o <= outstanding_o + 1'b1;
        2'b01: outstanding_o <= outstanding_o - 1'b1;
        default: outstanding_o <= outstanding_o;
      endcase
    end
  end
endmodule

`default_nettype wire
