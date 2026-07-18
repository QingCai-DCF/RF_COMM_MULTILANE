`timescale 1ns/1ps
module tb_axi_dma_adapter;
  logic clk=0; always #5 clk=~clk;
  logic reset_n,abort;
  logic mm_valid,mm_ready,mm_last,tx_valid,tx_ready,tx_last;
  logic [63:0] mm_data,tx_data,rx_data,s2_data;
  logic [7:0] mm_keep,tx_keep,rx_keep,s2_keep;
  logic rx_valid,rx_ready,rx_last,s2_valid,s2_ready,s2_last;
  logic desc_valid,desc_ready,dma_desc_valid,dma_desc_ready;
  logic [63:0] desc_addr,dma_desc_addr;
  logic [31:0] desc_len,dma_desc_len;
  logic [31:0] desc_tag,dma_desc_tag;
  logic [15:0] desc_gen,dma_desc_gen;
  logic dma_comp_valid,dma_comp_ready,comp_valid,comp_ready;
  logic [31:0] dma_comp_len,comp_len;
  logic [15:0] dma_comp_error,comp_error,dma_comp_gen,comp_gen;
  logic [31:0] dma_comp_tag,comp_tag,abort_count,stale_count;
  integer tx_seen,rx_seen;

  axi_dma_adapter dut(
    .clk_i(clk),.reset_n_i(reset_n),.abort_i(abort),
    .dma_mm2s_tvalid_i(mm_valid),.dma_mm2s_tready_o(mm_ready),
    .dma_mm2s_tdata_i(mm_data),.dma_mm2s_tkeep_i(mm_keep),.dma_mm2s_tlast_i(mm_last),
    .core_tx_tvalid_o(tx_valid),.core_tx_tready_i(tx_ready),
    .core_tx_tdata_o(tx_data),.core_tx_tkeep_o(tx_keep),.core_tx_tlast_o(tx_last),
    .core_rx_tvalid_i(rx_valid),.core_rx_tready_o(rx_ready),.core_rx_tdata_i(rx_data),
    .core_rx_tkeep_i(rx_keep),.core_rx_tlast_i(rx_last),
    .dma_s2mm_tvalid_o(s2_valid),.dma_s2mm_tready_i(s2_ready),
    .dma_s2mm_tdata_o(s2_data),.dma_s2mm_tkeep_o(s2_keep),.dma_s2mm_tlast_o(s2_last),
    .descriptor_valid_i(desc_valid),.descriptor_ready_o(desc_ready),
    .descriptor_address_i(desc_addr),.descriptor_length_i(desc_len),
    .descriptor_tag_i(desc_tag),.descriptor_generation_i(desc_gen),
    .dma_descriptor_valid_o(dma_desc_valid),.dma_descriptor_ready_i(dma_desc_ready),
    .dma_descriptor_address_o(dma_desc_addr),.dma_descriptor_length_o(dma_desc_len),
    .dma_descriptor_tag_o(dma_desc_tag),.dma_descriptor_generation_o(dma_desc_gen),
    .dma_completion_valid_i(dma_comp_valid),.dma_completion_ready_o(dma_comp_ready),
    .dma_completion_length_i(dma_comp_len),.dma_completion_error_i(dma_comp_error),
    .dma_completion_tag_i(dma_comp_tag),.dma_completion_generation_i(dma_comp_gen),
    .completion_valid_o(comp_valid),.completion_ready_i(comp_ready),
    .completion_length_o(comp_len),.completion_error_o(comp_error),
    .completion_tag_o(comp_tag),.completion_generation_o(comp_gen),
    .abort_count_o(abort_count),.stale_completion_count_o(stale_count));

  task automatic check_expect(input logic condition,input string message);
    if(!condition)$fatal(1,"AXIDMA_EXPECT_FAIL: %s",message);
  endtask
  always @(posedge clk)begin
    if(tx_valid&&tx_ready)begin
      check_expect(tx_data==64'h1000+tx_seen,"MM2S beat order/data preserved");tx_seen=tx_seen+1;end
    if(s2_valid&&s2_ready)begin
      check_expect(s2_data==64'h2000+rx_seen,"S2MM beat order/data preserved");rx_seen=rx_seen+1;end
  end
  initial begin
    reset_n=0;abort=0;mm_valid=0;mm_data=0;mm_keep=0;mm_last=0;tx_ready=0;
    rx_valid=0;rx_data=0;rx_keep=0;rx_last=0;s2_ready=0;desc_valid=0;
    desc_addr=0;desc_len=0;desc_tag=0;desc_gen=1;dma_desc_ready=0;
    dma_comp_valid=0;dma_comp_len=0;dma_comp_error=0;dma_comp_tag=0;dma_comp_gen=1;
    comp_ready=0;tx_seen=0;rx_seen=0;
    repeat(3)@(posedge clk);reset_n=1;@(posedge clk);#1;

    // TX backpressure retains TDATA/TKEEP/TLAST.
    @(negedge clk);mm_valid=1;mm_data=64'h1000;mm_keep=8'hff;mm_last=0;
    @(posedge clk);#1;mm_valid=0;repeat(3)@(posedge clk);#1;
    check_expect(tx_valid&&tx_data==64'h1000&&tx_keep==8'hff&&!tx_last,"TX skid holds under backpressure");
    tx_ready=1;@(posedge clk);#1;tx_ready=0;
    @(negedge clk);mm_valid=1;mm_data=64'h1001;mm_keep=8'h0f;mm_last=1;tx_ready=1;
    @(posedge clk);#1;mm_valid=0;@(posedge clk);#1;tx_ready=0;
    check_expect(tx_seen==2,"TX stream sends two beats exactly once");

    // RX backpressure and partial final keep.
    @(negedge clk);rx_valid=1;rx_data=64'h2000;rx_keep=8'hff;rx_last=0;
    @(posedge clk);#1;rx_valid=0;repeat(2)@(posedge clk);#1;
    check_expect(s2_valid&&s2_data==64'h2000,"RX skid holds under backpressure");
    s2_ready=1;@(posedge clk);#1;s2_ready=0;
    @(negedge clk);rx_valid=1;rx_data=64'h2001;rx_keep=8'h03;rx_last=1;s2_ready=1;
    @(posedge clk);#1;rx_valid=0;@(posedge clk);#1;s2_ready=0;
    check_expect(rx_seen==2&&s2_keep==8'h03&&s2_last,"RX TLAST/TKEEP preserved");

    // Descriptor/completion and stale-generation rejection.
    @(negedge clk);desc_valid=1;desc_addr=64'h1234_0000;desc_len=288;desc_tag=32'h55;desc_gen=16'd7;
    @(posedge clk);#1;desc_valid=0;check_expect(dma_desc_valid,"descriptor is held for vendor ready");
    dma_desc_ready=1;@(posedge clk);#1;dma_desc_ready=0;
    @(negedge clk);dma_comp_valid=1;dma_comp_len=288;dma_comp_tag=32'h55;dma_comp_gen=7;
    @(posedge clk);#1;dma_comp_valid=0;
    check_expect(comp_valid&&comp_len==288&&comp_tag==32'h55,"matching completion reaches portable core");
    comp_ready=1;@(posedge clk);#1;comp_ready=0;
    abort=1;@(posedge clk);#1;abort=0;
    @(negedge clk);dma_comp_valid=1;dma_comp_gen=7;
    #1;check_expect(dma_comp_ready,"stale completion is consumed rather than deadlocking vendor valid");
    @(posedge clk);#1;dma_comp_valid=0;
    check_expect(!comp_valid&&stale_count==1&&abort_count==1,"abort rejects stale completion");
    $display("P8E_AXI_DMA_TLAST_TKEEP_BACKPRESSURE_PASS=1");
    $display("P8E_AXI_DMA_DESCRIPTOR_COMPLETION_PASS=1");
    $display("P8E_AXI_DMA_RESET_ABORT_STALE_REJECT_PASS=1");
    $display("TB_AXI_DMA_ADAPTER_PASS=1");
    $finish;
  end
endmodule
