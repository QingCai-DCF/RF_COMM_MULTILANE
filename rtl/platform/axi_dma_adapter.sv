`timescale 1ns/1ps
// Vendor-isolation boundary for an AXI DMA SG implementation.  The portable
// core sees only AXI-Stream plus explicit descriptor/completion handshakes.
module axi_dma_adapter #(
  parameter int DATA_WIDTH = 64,
  parameter int TAG_WIDTH = 32,
  parameter int GENERATION_WIDTH = 16
) (
  input  logic clk_i,
  input  logic reset_n_i,
  input  logic abort_i,

  // Vendor MM2S stream -> portable TX stream.
  input  logic dma_mm2s_tvalid_i,
  output logic dma_mm2s_tready_o,
  input  logic [DATA_WIDTH-1:0] dma_mm2s_tdata_i,
  input  logic [DATA_WIDTH/8-1:0] dma_mm2s_tkeep_i,
  input  logic dma_mm2s_tlast_i,
  output logic core_tx_tvalid_o,
  input  logic core_tx_tready_i,
  output logic [DATA_WIDTH-1:0] core_tx_tdata_o,
  output logic [DATA_WIDTH/8-1:0] core_tx_tkeep_o,
  output logic core_tx_tlast_o,

  // Portable RX stream -> vendor S2MM stream.
  input  logic core_rx_tvalid_i,
  output logic core_rx_tready_o,
  input  logic [DATA_WIDTH-1:0] core_rx_tdata_i,
  input  logic [DATA_WIDTH/8-1:0] core_rx_tkeep_i,
  input  logic core_rx_tlast_i,
  output logic dma_s2mm_tvalid_o,
  input  logic dma_s2mm_tready_i,
  output logic [DATA_WIDTH-1:0] dma_s2mm_tdata_o,
  output logic [DATA_WIDTH/8-1:0] dma_s2mm_tkeep_o,
  output logic dma_s2mm_tlast_o,

  // Portable descriptor request -> platform/vendor SG command.
  input  logic descriptor_valid_i,
  output logic descriptor_ready_o,
  input  logic [63:0] descriptor_address_i,
  input  logic [31:0] descriptor_length_i,
  input  logic [TAG_WIDTH-1:0] descriptor_tag_i,
  input  logic [GENERATION_WIDTH-1:0] descriptor_generation_i,
  output logic dma_descriptor_valid_o,
  input  logic dma_descriptor_ready_i,
  output logic [63:0] dma_descriptor_address_o,
  output logic [31:0] dma_descriptor_length_o,
  output logic [TAG_WIDTH-1:0] dma_descriptor_tag_o,
  output logic [GENERATION_WIDTH-1:0] dma_descriptor_generation_o,

  // Platform/vendor completion -> portable completion queue.
  input  logic dma_completion_valid_i,
  output logic dma_completion_ready_o,
  input  logic [31:0] dma_completion_length_i,
  input  logic [15:0] dma_completion_error_i,
  input  logic [TAG_WIDTH-1:0] dma_completion_tag_i,
  input  logic [GENERATION_WIDTH-1:0] dma_completion_generation_i,
  output logic completion_valid_o,
  input  logic completion_ready_i,
  output logic [31:0] completion_length_o,
  output logic [15:0] completion_error_o,
  output logic [TAG_WIDTH-1:0] completion_tag_o,
  output logic [GENERATION_WIDTH-1:0] completion_generation_o,
  output logic [31:0] abort_count_o,
  output logic [31:0] stale_completion_count_o
);
  logic tx_valid, rx_valid, descriptor_pending, completion_pending;
  logic [GENERATION_WIDTH-1:0] active_generation;

  assign dma_mm2s_tready_o = !tx_valid || core_tx_tready_i;
  assign core_tx_tvalid_o = tx_valid;
  assign core_rx_tready_o = !rx_valid || dma_s2mm_tready_i;
  assign dma_s2mm_tvalid_o = rx_valid;
  assign descriptor_ready_o = !descriptor_pending || dma_descriptor_ready_i;
  assign dma_descriptor_valid_o = descriptor_pending;
  // A stale completion is consumed and discarded immediately.  Holding
  // READY low for a stale generation would deadlock a level-valid vendor
  // completion source and count the same record repeatedly.
  assign dma_completion_ready_o =
      (dma_completion_generation_i != active_generation) ||
      (!completion_pending || completion_ready_i);
  assign completion_valid_o = completion_pending;

  always_ff @(posedge clk_i) begin
    if (!reset_n_i) begin
      tx_valid <= 1'b0;
      rx_valid <= 1'b0;
      descriptor_pending <= 1'b0;
      completion_pending <= 1'b0;
      core_tx_tdata_o <= '0;
      core_tx_tkeep_o <= '0;
      core_tx_tlast_o <= 1'b0;
      dma_s2mm_tdata_o <= '0;
      dma_s2mm_tkeep_o <= '0;
      dma_s2mm_tlast_o <= 1'b0;
      dma_descriptor_address_o <= 64'd0;
      dma_descriptor_length_o <= 32'd0;
      dma_descriptor_tag_o <= '0;
      dma_descriptor_generation_o <= '0;
      completion_length_o <= 32'd0;
      completion_error_o <= 16'd0;
      completion_tag_o <= '0;
      completion_generation_o <= '0;
      active_generation <= {{(GENERATION_WIDTH-1){1'b0}},1'b1};
      abort_count_o <= 32'd0;
      stale_completion_count_o <= 32'd0;
    end else if (abort_i) begin
      tx_valid <= 1'b0;
      rx_valid <= 1'b0;
      descriptor_pending <= 1'b0;
      completion_pending <= 1'b0;
      active_generation <= active_generation + 1'b1;
      abort_count_o <= abort_count_o + 1'b1;
    end else begin
      if (dma_mm2s_tready_o) begin
        tx_valid <= dma_mm2s_tvalid_i;
        if (dma_mm2s_tvalid_i) begin
          core_tx_tdata_o <= dma_mm2s_tdata_i;
          core_tx_tkeep_o <= dma_mm2s_tkeep_i;
          core_tx_tlast_o <= dma_mm2s_tlast_i;
        end
      end
      if (core_rx_tready_o) begin
        rx_valid <= core_rx_tvalid_i;
        if (core_rx_tvalid_i) begin
          dma_s2mm_tdata_o <= core_rx_tdata_i;
          dma_s2mm_tkeep_o <= core_rx_tkeep_i;
          dma_s2mm_tlast_o <= core_rx_tlast_i;
        end
      end
      if (descriptor_ready_o) begin
        descriptor_pending <= descriptor_valid_i;
        if (descriptor_valid_i) begin
          dma_descriptor_address_o <= descriptor_address_i;
          dma_descriptor_length_o <= descriptor_length_i;
          dma_descriptor_tag_o <= descriptor_tag_i;
          dma_descriptor_generation_o <= descriptor_generation_i;
          active_generation <= descriptor_generation_i;
        end
      end
      if (completion_pending && completion_ready_i)
        completion_pending <= 1'b0;
      if (dma_completion_valid_i && dma_completion_ready_o) begin
        if (dma_completion_generation_i != active_generation) begin
          stale_completion_count_o <= stale_completion_count_o + 1'b1;
        end else if (!completion_pending || completion_ready_i) begin
          completion_pending <= 1'b1;
          completion_length_o <= dma_completion_length_i;
          completion_error_o <= dma_completion_error_i;
          completion_tag_o <= dma_completion_tag_i;
          completion_generation_o <= dma_completion_generation_i;
        end
      end
    end
  end
endmodule
