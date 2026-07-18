`timescale 1ns/1ps
`default_nettype none
// Common-source endpoint shell used by every P8E implementation profile.
// The single raw GLOBAL_PERMIT enters the P8C endpoint unchanged; only ordinary
// DMA/control requests cross through registered CDC primitives.
module ir_endpoint_core #(
  parameter integer LANE_COUNT = 8,
  parameter integer WINDOW_SIZE = 64,
  parameter integer SACK_BITS = 64,
  parameter integer PHYSICAL_MODULE_COUNT = 8,
  parameter integer DATA_WIDTH = 64
) (
  input  wire protocol_clk_i,
  input  wire axis_dma_clk_i,
  input  wire axi_lite_clk_i,
  input  wire reset_n_i,
  input  wire global_permit_i,
  input  wire endpoint_arm_request_i,
  input  wire dma_tx_kick_i,
  input  wire control_abort_i,
  input  wire protocol_rx_event_i,
  input  wire protocol_ack_event_i,
  input  wire [31:0] stimulus_seed_i,
  output wire [PHYSICAL_MODULE_COUNT-1:0] physical_txd_o,
  output wire physical_attempt_valid_o,
  output wire [$clog2(LANE_COUNT)-1:0] physical_attempt_lane_o,
  output wire [15:0] physical_attempt_sequence_o,
  output wire architecture_status_o,
  output wire clock_domain_status_o
);
  wire protocol_reset_n,axis_dma_reset_n,axi_lite_reset_n;
  reset_sync #(.STAGES(3)) u_protocol_reset(
    .clk_i(protocol_clk_i),.async_reset_n_i(reset_n_i),.reset_n_o(protocol_reset_n));
  reset_sync #(.STAGES(3)) u_axis_reset(
    .clk_i(axis_dma_clk_i),.async_reset_n_i(reset_n_i),.reset_n_o(axis_dma_reset_n));
  reset_sync #(.STAGES(3)) u_axil_reset(
    .clk_i(axi_lite_clk_i),.async_reset_n_i(reset_n_i),.reset_n_o(axi_lite_reset_n));

  wire dma_kick_protocol,dma_kick_ready;
  pulse_sync u_dma_kick_sync(
    .src_clk_i(axis_dma_clk_i),.src_reset_n_i(axis_dma_reset_n),
    .src_pulse_i(dma_tx_kick_i),.src_ready_o(dma_kick_ready),
    .dst_clk_i(protocol_clk_i),.dst_reset_n_i(protocol_reset_n),
    .dst_pulse_o(dma_kick_protocol));
  wire abort_protocol,abort_axis,arm_request_protocol;
  level_sync u_abort_sync(.clk_i(protocol_clk_i),.reset_n_i(protocol_reset_n),
    .async_level_i(control_abort_i),.level_o(abort_protocol));
  level_sync u_abort_axis_sync(.clk_i(axis_dma_clk_i),.reset_n_i(axis_dma_reset_n),
    .async_level_i(control_abort_i),.level_o(abort_axis));
  level_sync u_arm_sync(.clk_i(protocol_clk_i),.reset_n_i(protocol_reset_n),
    .async_level_i(endpoint_arm_request_i),.level_o(arm_request_protocol));

  reg [31:0] stimulus_lfsr;
  always @(posedge protocol_clk_i or negedge protocol_reset_n) begin
    if(!protocol_reset_n) stimulus_lfsr<=32'h1;
    else stimulus_lfsr<={stimulus_lfsr[30:0],
      stimulus_lfsr[31]^stimulus_lfsr[21]^stimulus_lfsr[1]^stimulus_lfsr[0]}^
      stimulus_seed_i;
  end

  // The DMA adapter is isolated in the axis/platform domain.  Its portable
  // interface is statically present without instantiating a board-specific IP.
  wire adapter_tx_valid,adapter_tx_last,adapter_desc_valid;
  wire [DATA_WIDTH-1:0] adapter_tx_data;
  wire [DATA_WIDTH/8-1:0] adapter_tx_keep;
  wire [63:0] adapter_desc_address;
  wire [31:0] adapter_desc_length,adapter_desc_tag;
  wire [15:0] adapter_desc_generation;
  wire [31:0] adapter_abort_count,adapter_stale_count;
  axi_dma_adapter #(.DATA_WIDTH(DATA_WIDTH)) u_dma_adapter(
    .clk_i(axis_dma_clk_i),.reset_n_i(axis_dma_reset_n),.abort_i(abort_axis),
    .dma_mm2s_tvalid_i(dma_tx_kick_i),.dma_mm2s_tready_o(),
    .dma_mm2s_tdata_i({DATA_WIDTH{stimulus_seed_i[0]}}),
    .dma_mm2s_tkeep_i({DATA_WIDTH/8{1'b1}}),.dma_mm2s_tlast_i(1'b1),
    .core_tx_tvalid_o(adapter_tx_valid),.core_tx_tready_i(1'b1),
    .core_tx_tdata_o(adapter_tx_data),.core_tx_tkeep_o(adapter_tx_keep),
    .core_tx_tlast_o(adapter_tx_last),.core_rx_tvalid_i(1'b0),
    .core_rx_tready_o(),.core_rx_tdata_i({DATA_WIDTH{1'b0}}),
    .core_rx_tkeep_i({DATA_WIDTH/8{1'b0}}),.core_rx_tlast_i(1'b0),
    .dma_s2mm_tvalid_o(),.dma_s2mm_tready_i(1'b1),.dma_s2mm_tdata_o(),
    .dma_s2mm_tkeep_o(),.dma_s2mm_tlast_o(),
    .descriptor_valid_i(dma_tx_kick_i),.descriptor_ready_o(),
    .descriptor_address_i({32'd0,stimulus_seed_i}),.descriptor_length_i(32'd288),
    .descriptor_tag_i(stimulus_seed_i),.descriptor_generation_i(16'd1),
    .dma_descriptor_valid_o(adapter_desc_valid),.dma_descriptor_ready_i(1'b1),
    .dma_descriptor_address_o(adapter_desc_address),
    .dma_descriptor_length_o(adapter_desc_length),.dma_descriptor_tag_o(adapter_desc_tag),
    .dma_descriptor_generation_o(adapter_desc_generation),
    .dma_completion_valid_i(1'b0),.dma_completion_ready_o(),
    .dma_completion_length_i(32'd0),.dma_completion_error_i(16'd0),
    .dma_completion_tag_i(32'd0),.dma_completion_generation_i(16'd1),
    .completion_valid_o(),.completion_ready_i(1'b1),.completion_length_o(),
    .completion_error_o(),.completion_tag_o(),.completion_generation_o(),
    .abort_count_o(adapter_abort_count),.stale_completion_count_o(adapter_stale_count));

  wire [DATA_WIDTH-1:0] axis_out_data,payload_read_data;
  wire [DATA_WIDTH/8-1:0] axis_out_keep,payload_read_keep;
  wire axis_in_ready,axis_out_valid,axis_out_last,ring_status;
  wire [$clog2((288+(DATA_WIDTH/8)-1)/(DATA_WIDTH/8))-1:0] payload_beat;
  assign payload_beat='0;
  wire [PHYSICAL_MODULE_COUNT-1:0] frame_admitted={PHYSICAL_MODULE_COUNT{dma_kick_protocol}};
  wire [PHYSICAL_MODULE_COUNT-1:0] waveform={PHYSICAL_MODULE_COUNT{stimulus_lfsr[0]}};

  ir_p8d_resource_top #(.LANE_COUNT(LANE_COUNT),.WINDOW_SIZE(WINDOW_SIZE),
    .SACK_BITS(SACK_BITS),.DATA_WIDTH(DATA_WIDTH),
    .PHYSICAL_MODULE_COUNT(PHYSICAL_MODULE_COUNT)) u_portable_architecture(
    .clk(protocol_clk_i),.rst_n(protocol_reset_n),.global_permit_i(global_permit_i),
    .endpoint_armed_i(arm_request_protocol),.tx_request_i(dma_kick_protocol),
    .rx_request_i(protocol_rx_event_i),.ack_valid_i(protocol_ack_event_i),
    .abort_i(abort_protocol),.payload_length_i(16'd128),
    .sequence_i(stimulus_lfsr[15:0]),
    .descriptor_index_i(stimulus_lfsr[$clog2(WINDOW_SIZE)-1:0]),
    .s_axis_tdata_i({DATA_WIDTH{stimulus_lfsr[0]}}),
    .s_axis_tkeep_i({DATA_WIDTH/8{1'b1}}),.s_axis_tvalid_i(dma_kick_protocol),
    .s_axis_tlast_i(1'b1),.payload_beat_i(payload_beat),
    .tx_complete_index_i(stimulus_lfsr[5:0]),.tx_complete_generation_i(16'd1),
    .tx_complete_valid_i(1'b0),.rx_complete_index_i(stimulus_lfsr[5:0]),
    .rx_complete_generation_i(16'd1),.rx_complete_valid_i(1'b0),
    .safety_frame_admitted_i(frame_admitted),.safety_waveform_i(waveform),
    .safety_txd_o(physical_txd_o),.physical_attempt_valid_o,
    .physical_attempt_lane_o,.physical_attempt_sequence_o,
    .s_axis_tready_o(axis_in_ready),.m_axis_tvalid_o(axis_out_valid),
    .m_axis_tdata_o(axis_out_data),.m_axis_tkeep_o(axis_out_keep),
    .m_axis_tlast_o(axis_out_last),.payload_read_data_o(payload_read_data),
    .payload_read_keep_o(payload_read_keep),.ring_status_o(ring_status),
    .architecture_status_o);

  assign clock_domain_status_o=^{protocol_reset_n,axis_dma_reset_n,axi_lite_reset_n,
    dma_kick_ready,adapter_tx_valid,adapter_tx_last,adapter_tx_data,adapter_tx_keep,
    adapter_desc_valid,adapter_desc_address,adapter_desc_length,adapter_desc_tag,
    adapter_desc_generation,adapter_abort_count,adapter_stale_count,axis_in_ready,
    axis_out_valid,axis_out_data,axis_out_keep,axis_out_last,payload_read_data,
    payload_read_keep,ring_status};
endmodule
`default_nettype wire
