module ir_loopback_b0_bd (
  input  wire clk_phy,
  input  wire rst_n,
  output wire ir_tx_out,
  input  wire ir_rx_in,
  output wire ir_sd,
  output wire ir_mode_out,
  output wire [31:0] debug_status
);
  localparam integer MAX_PACKET_BYTES = 256;
  localparam integer FRAGMENT_BYTES   = 16;
  localparam integer MAX_FRAGS        = 16;
  localparam integer MAX_FRAME_BYTES  = 30;
  localparam [15:0] REPLY_GUARD_CYCLES = 16'd8192;

  wire [7:0] echo_rx_tdata;
  wire       echo_rx_tvalid;
  wire       echo_rx_tready;
  wire       echo_rx_tlast;
  wire [7:0] echo_tx_tdata;
  wire       echo_tx_tvalid;
  wire       echo_tx_tready;
  wire       echo_tx_tlast;

  reg [7:0]  echo_buf [0:MAX_PACKET_BYTES-1];
  reg [15:0] echo_wr_ptr;
  reg [15:0] echo_rd_ptr;
  reg [15:0] echo_tx_len;
  reg [15:0] echo_reply_guard;
  reg        echo_pkt_ready;
  reg        echo_tx_active;
  reg        echo_drop_rx;

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
  reg [7:0] b_tx_edge_count;
  reg [7:0] b_rx_edge_count;
  reg [3:0] b_rx_frame_count;
  reg [3:0] b_rx_crc_count;
  reg [3:0] b_rx_error_count;
  reg [15:0] b_tx_guard;
  reg       b_tx_d;
  reg       b_rx_d;

  assign ir_rx_vec[0] = ir_rx_in;
  assign ir_tx_out    = ir_tx_vec[0];
  assign ir_sd        = ir_sd_vec[0];
  assign ir_mode_out  = ir_mode_vec[0];
  assign debug_status = {
    4'hE,
    tx_packet_active,
    echo_tx_active,
    tx_error_retry_exhausted,
    tx_done_pulse,
    tx_frag_pending_dbg[3:0],
    tx_frag_inflight_dbg[3:0],
    tx_frag_acked_dbg[3:0],
    rx_recv_bitmap_dbg[3:0],
    b_rx_frame_count,
    b_rx_crc_count,
    b_rx_error_count
  };

  assign echo_rx_tready = !echo_pkt_ready && !echo_tx_active;
  assign echo_tx_tdata  = echo_buf[echo_rd_ptr];
  assign echo_tx_tvalid = echo_tx_active;
  assign echo_tx_tlast  = echo_tx_active && (echo_rd_ptr == (echo_tx_len - 1'b1));

  always @(posedge clk_phy) begin
    if (!rst_n) begin
      echo_wr_ptr    <= 16'h0000;
      echo_rd_ptr    <= 16'h0000;
      echo_tx_len    <= 16'h0000;
      echo_reply_guard <= 16'h0000;
      echo_pkt_ready <= 1'b0;
      echo_tx_active <= 1'b0;
      echo_drop_rx   <= 1'b0;
      b_tx_edge_count <= 8'h00;
      b_rx_edge_count <= 8'h00;
      b_rx_frame_count <= 4'h0;
      b_rx_crc_count <= 4'h0;
      b_rx_error_count <= 4'h0;
      b_tx_guard <= 16'h0000;
      b_tx_d <= 1'b0;
      b_rx_d <= 1'b0;
    end else begin
      b_tx_d <= ir_tx_out;
      b_rx_d <= ir_rx_in;
      if ((ir_tx_out ^ b_tx_d) && b_tx_edge_count != 8'hff) begin
        b_tx_edge_count <= b_tx_edge_count + 8'd1;
      end
      if ((ir_rx_in ^ b_rx_d) && b_rx_edge_count != 8'hff) begin
        b_rx_edge_count <= b_rx_edge_count + 8'd1;
      end
      if (lane_rx_frame_pulse_dbg[0] && b_rx_frame_count != 4'hf) begin
        b_rx_frame_count <= b_rx_frame_count + 4'd1;
      end
      if (lane_rx_frame_pulse_dbg[0]) begin
        b_tx_guard <= REPLY_GUARD_CYCLES;
      end else if (b_tx_guard != 16'h0000) begin
        b_tx_guard <= b_tx_guard - 1'b1;
      end
      if (lane_rx_crc_error_dbg[0] && b_rx_crc_count != 4'hf) begin
        b_rx_crc_count <= b_rx_crc_count + 4'd1;
      end
      if (lane_rx_error_dbg[0] && b_rx_error_count != 4'hf) begin
        b_rx_error_count <= b_rx_error_count + 4'd1;
      end

      if (echo_rx_tvalid && echo_rx_tready) begin
        if (!echo_drop_rx && (echo_wr_ptr < MAX_PACKET_BYTES)) begin
          echo_buf[echo_wr_ptr] <= echo_rx_tdata;
          echo_wr_ptr <= echo_wr_ptr + 1'b1;
        end else begin
          echo_drop_rx <= 1'b1;
        end

        if (echo_rx_tlast) begin
          if (!echo_drop_rx && (echo_wr_ptr < MAX_PACKET_BYTES)) begin
            echo_tx_len    <= echo_wr_ptr + 1'b1;
            echo_reply_guard <= REPLY_GUARD_CYCLES;
            echo_pkt_ready <= 1'b1;
          end
          echo_wr_ptr  <= 16'h0000;
          echo_drop_rx <= 1'b0;
        end
      end

      if (!echo_tx_active && echo_pkt_ready && (echo_reply_guard != 16'h0000)) begin
        echo_reply_guard <= echo_reply_guard - 1'b1;
      end else if (!echo_tx_active && echo_pkt_ready) begin
        echo_tx_active <= 1'b1;
        echo_pkt_ready <= 1'b0;
        echo_rd_ptr    <= 16'h0000;
      end else if (echo_tx_active && echo_tx_tready) begin
        if (echo_rd_ptr == (echo_tx_len - 1'b1)) begin
          echo_tx_active <= 1'b0;
          echo_rd_ptr    <= 16'h0000;
          echo_reply_guard <= 16'h0000;
        end else begin
          echo_rd_ptr <= echo_rd_ptr + 1'b1;
        end
      end
    end
  end

  ir_array_top #(
    .LANE_COUNT(1),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_RETRY(4),
    .CNT_CHIP_MAX(7),
    .CNT_PREAMBLE(64),
    .EOF_SILENCE_SYMS(3),
    .FRAG_TIMEOUT_CYCLES(50000),
    .RX_TO_TX_GUARD_CYCLES(REPLY_GUARD_CYCLES),
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
    .s_axis_tx_tdata(echo_tx_tdata),
    .s_axis_tx_tvalid(echo_tx_tvalid),
    .s_axis_tx_tready(echo_tx_tready),
    .s_axis_tx_tlast(echo_tx_tlast),
    .m_axis_rx_tdata(echo_rx_tdata),
    .m_axis_rx_tvalid(echo_rx_tvalid),
    .m_axis_rx_tready(echo_rx_tready),
    .m_axis_rx_tlast(echo_rx_tlast),
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
    .rx_recv_bitmap_dbg(rx_recv_bitmap_dbg)
  );
endmodule
