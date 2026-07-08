module ir_sink_b0_bd #(
  parameter integer B_CNT_PREAMBLE = 64,
  parameter integer B_GUARD_CYCLES = 1408
)(
  input  wire clk_phy,
  input  wire rst_n,
  output wire ir_tx_out,
  input  wire ir_rx_in,
  output wire ir_sd,
  output wire ir_mode_out,
  output wire [31:0] debug_status
);
  localparam integer MAX_PACKET_BYTES = 256;
  localparam integer FRAGMENT_BYTES   = 255;
  localparam integer MAX_FRAGS        = 2;
  localparam integer MAX_FRAME_BYTES  = 269;
  localparam [15:0] B_GUARD_CYCLES_16 = B_GUARD_CYCLES;

  wire [7:0] sink_rx_tdata;
  wire       sink_rx_tvalid;
  wire       sink_rx_tlast;

  wire [0:0] ir_tx_vec;
  wire [0:0] ir_rx_vec;
  wire [0:0] ir_sd_vec;
  wire [0:0] ir_mode_vec;
  wire [0:0] lane_tx_busy_dbg;
  wire [0:0] lane_tx_load_pulse_dbg;
  wire [0:0] lane_rx_frame_pulse_dbg;
  wire [0:0] lane_rx_crc_error_dbg;
  wire [0:0] lane_rx_error_dbg;
  wire [31:0] lane_rx_debug_status_dbg;

  wire tx_packet_active;
  wire tx_packet_loading;
  wire tx_done_pulse;
  wire tx_error_overflow;
  wire tx_error_retry_exhausted;
  wire rx_ctx_valid;
  wire rx_ctx_complete;
  wire rx_done_pulse;
  wire rx_header_error;
  wire rx_protocol_error;
  wire rx_frame_overflow_any;
  wire rx_crc_error_any;
  wire rx_overrun_error_any;
  wire [MAX_FRAGS-1:0] tx_frag_pending_dbg;
  wire [MAX_FRAGS-1:0] tx_frag_inflight_dbg;
  wire [MAX_FRAGS-1:0] tx_frag_acked_dbg;
  wire [MAX_FRAGS-1:0] rx_recv_bitmap_dbg;

  reg [7:0]  b_rx_done_count;
  reg [7:0]  b_rx_frame_count;
  reg [7:0]  b_rx_byte_count;
  reg [3:0]  b_rx_crc_count;
  reg [3:0]  b_rx_error_count;
  reg [15:0] b_tx_guard;
  reg        b_tx_d;
  reg        b_rx_d;
  reg [3:0]  b_tx_edge_count;
  reg [3:0]  b_rx_edge_count;

  assign ir_rx_vec[0] = ir_rx_in;
  assign ir_tx_out    = ir_tx_vec[0];
  assign ir_sd        = ir_sd_vec[0];
  assign ir_mode_out  = ir_mode_vec[0];

  assign debug_status = {
    4'hE,
    rx_done_pulse,
    rx_ctx_valid,
    rx_ctx_complete,
    tx_error_retry_exhausted,
    rx_recv_bitmap_dbg[1:0],
    b_tx_edge_count[2:0],
    b_rx_edge_count[2:0],
    b_rx_done_count,
    b_rx_frame_count
  };

  always @(posedge clk_phy) begin
    if (!rst_n) begin
      b_rx_done_count  <= 8'h00;
      b_rx_frame_count <= 8'h00;
      b_rx_byte_count  <= 8'h00;
      b_rx_crc_count   <= 4'h0;
      b_rx_error_count <= 4'h0;
      b_tx_guard       <= 16'h0000;
      b_tx_d           <= 1'b0;
      b_rx_d           <= 1'b0;
      b_tx_edge_count  <= 4'h0;
      b_rx_edge_count  <= 4'h0;
    end else begin
      b_tx_d <= ir_tx_out;
      b_rx_d <= ir_rx_in;

      if ((ir_tx_out ^ b_tx_d) && b_tx_edge_count != 4'hf) begin
        b_tx_edge_count <= b_tx_edge_count + 4'd1;
      end
      if ((ir_rx_in ^ b_rx_d) && b_rx_edge_count != 4'hf) begin
        b_rx_edge_count <= b_rx_edge_count + 4'd1;
      end
      if (lane_rx_frame_pulse_dbg[0] && b_rx_frame_count != 8'hff) begin
        b_rx_frame_count <= b_rx_frame_count + 8'd1;
      end
      if (lane_rx_frame_pulse_dbg[0]) begin
        b_tx_guard <= B_GUARD_CYCLES_16;
      end else if (b_tx_guard != 16'h0000) begin
        b_tx_guard <= b_tx_guard - 1'b1;
      end
      if (lane_rx_crc_error_dbg[0] && b_rx_crc_count != 4'hf) begin
        b_rx_crc_count <= b_rx_crc_count + 4'd1;
      end
      if (lane_rx_error_dbg[0] && b_rx_error_count != 4'hf) begin
        b_rx_error_count <= b_rx_error_count + 4'd1;
      end
      if (sink_rx_tvalid && b_rx_byte_count != 8'hff) begin
        b_rx_byte_count <= b_rx_byte_count + 8'd1;
      end
      if (rx_done_pulse && b_rx_done_count != 8'hff) begin
        b_rx_done_count <= b_rx_done_count + 8'd1;
      end
    end
  end

  ir_array_top #(
    .LANE_COUNT(1),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_RETRY(4),
    .CNT_CHIP_MAX(7),
    .CNT_PREAMBLE(B_CNT_PREAMBLE),
    .EOF_SILENCE_SYMS(3),
    .FRAG_TIMEOUT_CYCLES(50000),
    .TX_POST_ACK_GUARD_CYCLES(B_GUARD_CYCLES),
    .RX_TO_TX_GUARD_CYCLES(B_GUARD_CYCLES),
    .REASSEMBLY_TIMEOUT_CYCLES(200000),
    .MAX_FRAGS(MAX_FRAGS),
    .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
  ) u_partner (
    .clk_phy(clk_phy),
    .rst_n(rst_n),
    .enable(1'b1),
    .session_id(16'h2201),
    .lane_enable_mask((b_tx_guard == 16'h0000) ? 1'b1 : 1'b0),
    .rx_lane_enable_mask(1'b1),
    .s_axis_tx_tdata(8'h00),
    .s_axis_tx_tvalid(1'b0),
    .s_axis_tx_tready(),
    .s_axis_tx_tlast(1'b0),
    .m_axis_rx_tdata(sink_rx_tdata),
    .m_axis_rx_tvalid(sink_rx_tvalid),
    .m_axis_rx_tready(1'b1),
    .m_axis_rx_tlast(sink_rx_tlast),
    .ir_tx_out(ir_tx_vec),
    .ir_rx_in(ir_rx_vec),
    .ir_sd(ir_sd_vec),
    .ir_mode_out(ir_mode_vec),
    .tx_packet_active(tx_packet_active),
    .tx_packet_loading(tx_packet_loading),
    .tx_done_pulse(tx_done_pulse),
    .tx_error_overflow(tx_error_overflow),
    .tx_error_retry_exhausted(tx_error_retry_exhausted),
    .rx_ctx_valid(rx_ctx_valid),
    .rx_ctx_complete(rx_ctx_complete),
    .rx_done_pulse(rx_done_pulse),
    .rx_header_error(rx_header_error),
    .rx_protocol_error(rx_protocol_error),
    .rx_frame_overflow_any(rx_frame_overflow_any),
    .rx_crc_error_any(rx_crc_error_any),
    .rx_overrun_error_any(rx_overrun_error_any),
    .lane_tx_busy_dbg(lane_tx_busy_dbg),
    .lane_tx_load_pulse_dbg(lane_tx_load_pulse_dbg),
    .lane_rx_frame_pulse_dbg(lane_rx_frame_pulse_dbg),
    .lane_rx_crc_error_dbg(lane_rx_crc_error_dbg),
    .lane_rx_error_dbg(lane_rx_error_dbg),
    .lane_rx_debug_status_dbg(lane_rx_debug_status_dbg),
    .tx_frag_pending_dbg(tx_frag_pending_dbg),
    .tx_frag_inflight_dbg(tx_frag_inflight_dbg),
    .tx_frag_acked_dbg(tx_frag_acked_dbg),
    .rx_recv_bitmap_dbg(rx_recv_bitmap_dbg),
    .rx_debug_status_dbg()
  );
endmodule
