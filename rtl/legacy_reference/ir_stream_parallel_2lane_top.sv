module ir_stream_parallel_2lane_top #(
  parameter int NODE_ID                   = 0,
  parameter int MAX_PACKET_BYTES          = 255,
  parameter int FRAGMENT_BYTES            = 255,
  parameter int MAX_RETRY                 = 4,
  parameter int CNT_CHIP_MAX              = 7,
  parameter int CNT_PREAMBLE              = 64,
  parameter int EOF_SILENCE_SYMS          = 3,
  parameter int RX_DATA_PHASE_DELAY_CYCLES = 0,
  parameter int RX_DETECT_START_CYCLES    = 0,
  parameter int RX_DETECT_END_CYCLES      = (CNT_CHIP_MAX >= 15) ? 10 : ((CNT_CHIP_MAX >= 7) ? (CNT_CHIP_MAX - 2) : CNT_CHIP_MAX),
  parameter int RX_PREAMBLE_REALIGN_EDGE  = 0,
  parameter int RX_SELF_BLANK_CYCLES      = (CNT_CHIP_MAX >= 15) ? 8 : ((CNT_CHIP_MAX >= 7) ? 4 : 1),
  parameter int FORCE_SD_SHUTDOWN         = 0,
  parameter logic [1:0] ACK_LANE_MASK     = 2'b01,
  parameter int FRAG_TIMEOUT_CYCLES       = 120000,
  parameter int TX_TO_RX_GUARD_CYCLES     = 1024,
  parameter int BACKOFF_SLOT_CYCLES       = 1024,
  parameter int REASSEMBLY_TIMEOUT_CYCLES = 200000,
  parameter int MAX_FRAGS                 = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES,
  parameter int MAX_FRAME_BYTES           = (14 + FRAGMENT_BYTES)
)(
  input  logic                  clk_phy,
  input  logic                  rst_n,
  input  logic                  enable,
  input  logic [15:0]           session_id,
  input  logic [1:0]            lane_enable_mask,
  input  logic [1:0]            rx_lane_enable_mask,

  input  logic [7:0]            s_axis_tx_tdata,
  input  logic                  s_axis_tx_tvalid,
  output logic                  s_axis_tx_tready,
  input  logic                  s_axis_tx_tlast,

  output logic [7:0]            m_axis_rx_tdata,
  output logic                  m_axis_rx_tvalid,
  input  logic                  m_axis_rx_tready,
  output logic                  m_axis_rx_tlast,

  output logic [1:0]            ir_tx_out,
  input  logic [1:0]            ir_rx_in,
  output logic [1:0]            ir_sd,
  output logic [1:0]            ir_mode_out,

  output logic                  tx_packet_active,
  output logic                  tx_packet_loading,
  output logic                  tx_done_pulse,
  output logic                  tx_error_overflow,
  output logic                  tx_error_retry_exhausted,
  output logic                  rx_ctx_valid,
  output logic                  rx_ctx_complete,
  output logic                  rx_done_pulse,
  output logic                  rx_header_error,
  output logic                  rx_protocol_error,
  output logic                  rx_frame_overflow_any,
  output logic                  rx_crc_error_any,
  output logic                  rx_overrun_error_any,
  output logic [1:0]            lane_tx_busy_dbg,
  output logic [1:0]            lane_tx_load_pulse_dbg,
  output logic [1:0]            lane_rx_frame_pulse_dbg,
  output logic [1:0]            lane_rx_crc_error_dbg,
  output logic [1:0]            lane_rx_error_dbg,
  output logic [63:0]           lane_rx_debug_status_dbg,
  output logic [MAX_FRAGS-1:0]  tx_frag_pending_dbg,
  output logic [MAX_FRAGS-1:0]  tx_frag_inflight_dbg,
  output logic [MAX_FRAGS-1:0]  tx_frag_acked_dbg,
  output logic [MAX_FRAGS-1:0]  rx_recv_bitmap_dbg,
  output logic [31:0]           debug_status
);
  localparam int STRIPE_HDR_BYTES = 8;
  localparam int ACK_BYTES        = 7;
  localparam int TX_CNT_PREAMBLE  = CNT_PREAMBLE + 96;
  localparam int RX_GUARD_CYCLES  = (TX_TO_RX_GUARD_CYCLES < 16) ? 16 : TX_TO_RX_GUARD_CYCLES;
  localparam logic [7:0] DATA_MAGIC = 8'hD5;
  localparam logic [7:0] ACK_MAGIC  = 8'hAD;
  localparam logic [7:0] TYPE_DATA  = 8'h20;
  localparam logic [7:0] TYPE_ACK   = 8'h22;

  typedef enum logic [2:0] {
    A_IDLE,
    A_COLLECT,
    A_START_SEND,
    A_WAIT_SEND,
    A_WAIT_ACK
  } a_state_t;

  logic [7:0] tx_pkt_buf [0:MAX_PACKET_BYTES-1];
  logic [7:0] rx_pkt_buf [0:MAX_PACKET_BYTES-1];

  a_state_t a_state;
  logic [15:0] tx_wr_ptr;
  logic [15:0] tx_pkt_len;
  logic [15:0] tx_seq;
  logic [15:0] tx_seq_next;
  logic [31:0] tx_ack_timeout;
  logic [7:0] tx_retry_count;
  logic [1:0] tx_lane_sent_mask;
  logic [1:0] tx_ack_bitmap;
  logic ack_good_pulse;
  logic [3:0] dbg_tlast_count;
  logic [3:0] dbg_start_count;
  logic [3:0] dbg_overflow_count;

  logic [1:0] send_active;
  logic [1:0] send_is_ack;
  logic [15:0] send_idx [0:1];
  logic [15:0] send_len [0:1];
  logic [15:0] send_seq;
  logic [15:0] send_total_len;
  logic [1:0] send_ack_bitmap;
  logic a_send_start_req;
  logic [15:0] a_send_start_seq;
  logic [15:0] a_send_start_total_len;
  logic b_send_start_req;
  logic [15:0] b_send_start_seq;
  logic [1:0] b_send_start_ack_bitmap;

  logic [1:0] lane_tx_tvalid;
  logic [1:0] lane_tx_tready;
  logic [1:0] lane_tx_tlast;
  logic [7:0] lane_tx_tdata [0:1];
  logic [1:0] lane_tx_busy;

  logic [1:0] lane_rx_tvalid;
  logic [1:0] lane_rx_tready;
  logic [1:0] lane_rx_tlast;
  logic [7:0] lane_rx_tdata [0:1];
  logic [1:0] lane_rx_active;
  logic [1:0] lane_rx_crc_error;
  logic [1:0] lane_rx_overrun_error;
  logic [31:0] lane_rx_debug [0:1];

  logic [15:0] rx_idx [0:1];
  logic [7:0] rx_magic [0:1];
  logic [7:0] rx_type [0:1];
  logic [15:0] rx_session [0:1];
  logic [15:0] rx_seq [0:1];
  logic [15:0] rx_total_len [0:1];
  logic [15:0] rx_payload_idx [0:1];
  logic [1:0] rx_parse_error;

  logic [15:0] b_seq;
  logic [15:0] b_total_len;
  logic [1:0] b_seg_bitmap;
  logic b_ctx_valid;
  logic b_ack_pending;
  logic b_ack_set_req;
  logic [15:0] b_ack_set_seq;
  logic [1:0] b_ack_set_bitmap;
  logic b_ack_guard_active;
  logic [31:0] b_ack_guard_cnt;
  logic [15:0] b_ack_seq;
  logic [1:0] b_ack_bitmap;
  logic [15:0] b_out_idx;
  logic b_output_active;
  logic b_output_start_req;

  logic [7:0] rx_done_count;
  logic [7:0] tx_done_count;
  logic [7:0] ack_rx_count;
  logic [7:0] ack_tx_count;
  logic [7:0] retry_count_dbg;

  function automatic [15:0] split0_len(input logic [15:0] total_len);
    begin
      split0_len = (total_len + 16'd1) >> 1;
    end
  endfunction

  function automatic [15:0] split1_len(input logic [15:0] total_len);
    begin
      split1_len = total_len - split0_len(total_len);
    end
  endfunction

  function automatic [15:0] lane_payload_len(
    input logic lane,
    input logic [15:0] total_len
  );
    begin
      lane_payload_len = lane ? split1_len(total_len) : split0_len(total_len);
    end
  endfunction

  function automatic [15:0] lane_payload_offset(
    input logic lane,
    input logic [15:0] total_len
  );
    begin
      lane_payload_offset = lane ? split0_len(total_len) : 16'd0;
    end
  endfunction

  function automatic [7:0] data_frame_byte(
    input logic lane,
    input logic [15:0] idx
  );
    logic [15:0] payload_idx;
    begin
      payload_idx = idx - STRIPE_HDR_BYTES[15:0] + lane_payload_offset(lane, send_total_len);
      case (idx)
        16'd0: data_frame_byte = DATA_MAGIC;
        16'd1: data_frame_byte = TYPE_DATA | {7'd0, lane};
        16'd2: data_frame_byte = session_id[7:0];
        16'd3: data_frame_byte = session_id[15:8];
        16'd4: data_frame_byte = send_seq[7:0];
        16'd5: data_frame_byte = send_seq[15:8];
        16'd6: data_frame_byte = send_total_len[7:0];
        16'd7: data_frame_byte = send_total_len[15:8];
        default: data_frame_byte = tx_pkt_buf[payload_idx];
      endcase
    end
  endfunction

  function automatic [7:0] ack_frame_byte(input logic [15:0] idx);
    begin
      case (idx)
        16'd0: ack_frame_byte = ACK_MAGIC;
        16'd1: ack_frame_byte = TYPE_ACK;
        16'd2: ack_frame_byte = session_id[7:0];
        16'd3: ack_frame_byte = session_id[15:8];
        16'd4: ack_frame_byte = send_seq[7:0];
        16'd5: ack_frame_byte = send_seq[15:8];
        16'd6: ack_frame_byte = {6'b000000, send_ack_bitmap};
        default: ack_frame_byte = 8'h00;
      endcase
    end
  endfunction

  genvar gi;
  generate
    for (gi = 0; gi < 2; gi = gi + 1) begin : g_phy
      logic rx_masked_in;
      logic [31:0] self_blank_cnt;

      assign ir_sd[gi] = (FORCE_SD_SHUTDOWN != 0) ? 1'b1 : ~(enable && (lane_enable_mask[gi] || rx_lane_enable_mask[gi]));
      assign ir_mode_out[gi] = 1'b1;
      assign rx_masked_in = (ir_tx_out[gi] || (self_blank_cnt != 32'h0000_0000)) ? 1'b1 : ir_rx_in[gi];

      always_ff @(posedge clk_phy) begin
        if (!rst_n || !enable) begin
          self_blank_cnt <= 32'h0000_0000;
        end else if (ir_tx_out[gi]) begin
          self_blank_cnt <= RX_SELF_BLANK_CYCLES[31:0];
        end else if (self_blank_cnt != 32'h0000_0000) begin
          self_blank_cnt <= self_blank_cnt - 1'b1;
        end
      end

      ir_tx_4ppm_frame #(
        .CNT_CHIP_MAX(CNT_CHIP_MAX),
        .CNT_PREAMBLE(TX_CNT_PREAMBLE),
        .CNT_EOF_SILENCE(EOF_SILENCE_SYMS + 4)
      ) u_tx (
        .clk(clk_phy),
        .rst_n(rst_n),
        .enable(enable && lane_enable_mask[gi]),
        .s_axis_tdata(lane_tx_tdata[gi]),
        .s_axis_tvalid(lane_tx_tvalid[gi]),
        .s_axis_tready(lane_tx_tready[gi]),
        .s_axis_tlast(lane_tx_tlast[gi]),
        .tx_busy(lane_tx_busy[gi]),
        .ir_tx_out(ir_tx_out[gi])
      );

      ir_rx_4ppm_frame #(
        .MAX_FRAME_BYTES(MAX_FRAME_BYTES),
        .CNT_CHIP_MAX(CNT_CHIP_MAX),
        .PREAMBLE_SYMS(CNT_PREAMBLE),
        .EOF_SILENCE_SYMS(EOF_SILENCE_SYMS),
        .DATA_PHASE_DELAY_CYCLES(RX_DATA_PHASE_DELAY_CYCLES),
        .DETECT_START_CYCLES(RX_DETECT_START_CYCLES),
        .DETECT_END_CYCLES(RX_DETECT_END_CYCLES),
        .PREAMBLE_REALIGN_EDGE(RX_PREAMBLE_REALIGN_EDGE),
        .PREAMBLE_WAIT_FOR_DATA_SYMBOL(1)
      ) u_rx (
        .clk(clk_phy),
        .rst_n(rst_n),
        .enable(enable && rx_lane_enable_mask[gi]),
        .ir_rx_in(rx_masked_in),
        .m_axis_tdata(lane_rx_tdata[gi]),
        .m_axis_tvalid(lane_rx_tvalid[gi]),
        .m_axis_tready(lane_rx_tready[gi]),
        .m_axis_tlast(lane_rx_tlast[gi]),
        .rx_active(lane_rx_active[gi]),
        .crc_error(lane_rx_crc_error[gi]),
        .overrun_error(lane_rx_overrun_error[gi]),
        .debug_status(lane_rx_debug[gi])
      );
    end
  endgenerate

  always_comb begin
    integer li;
    for (li = 0; li < 2; li = li + 1) begin
      lane_tx_tvalid[li] = send_active[li];
      lane_tx_tlast[li] = (send_idx[li] == (send_len[li] - 16'd1));
      lane_tx_tdata[li] = send_is_ack[li] ? ack_frame_byte(send_idx[li]) :
                                           data_frame_byte(li[0], send_idx[li]);
      lane_rx_tready[li] = 1'b1;
    end
  end

  always_ff @(posedge clk_phy) begin
    integer si;
    if (!rst_n || !enable) begin
      send_active <= 2'b00;
      send_is_ack <= 2'b00;
      send_idx[0] <= 16'h0000;
      send_idx[1] <= 16'h0000;
      send_len[0] <= 16'h0000;
      send_len[1] <= 16'h0000;
      send_seq <= 16'h0000;
      send_total_len <= 16'h0000;
      send_ack_bitmap <= 2'b00;
      lane_tx_load_pulse_dbg <= 2'b00;
    end else begin
      lane_tx_load_pulse_dbg <= 2'b00;
      if (a_send_start_req) begin
        send_seq <= a_send_start_seq;
        send_total_len <= a_send_start_total_len;
        send_ack_bitmap <= 2'b00;
        send_is_ack <= 2'b00;
        send_idx[0] <= 16'h0000;
        send_idx[1] <= 16'h0000;
        send_len[0] <= STRIPE_HDR_BYTES[15:0] + split0_len(a_send_start_total_len);
        send_len[1] <= STRIPE_HDR_BYTES[15:0] + split1_len(a_send_start_total_len);
        send_active[0] <= lane_enable_mask[0] && (split0_len(a_send_start_total_len) != 16'h0000);
        send_active[1] <= lane_enable_mask[1] && (split1_len(a_send_start_total_len) != 16'h0000);
      end else if (b_send_start_req) begin
        send_seq <= b_send_start_seq;
        send_total_len <= 16'h0000;
        send_ack_bitmap <= b_send_start_ack_bitmap;
        send_is_ack <= 2'b01;
        send_idx[0] <= 16'h0000;
        send_idx[1] <= 16'h0000;
        send_len[0] <= ACK_BYTES[15:0];
        send_len[1] <= 16'h0000;
        send_active[0] <= lane_enable_mask[0];
        send_active[1] <= 1'b0;
      end else begin
        for (si = 0; si < 2; si = si + 1) begin
          if (send_active[si] && lane_tx_tready[si]) begin
            if (send_idx[si] == 16'h0000) begin
              lane_tx_load_pulse_dbg[si] <= 1'b1;
            end
            if (send_idx[si] == (send_len[si] - 16'd1)) begin
              send_active[si] <= 1'b0;
              send_idx[si] <= 16'h0000;
            end else begin
              send_idx[si] <= send_idx[si] + 16'd1;
            end
          end
        end
      end
    end
  end

  assign s_axis_tx_tready = (NODE_ID == 0) && enable &&
                            ((a_state == A_IDLE) || (a_state == A_COLLECT));

  always_ff @(posedge clk_phy) begin
    integer next_len_v;
    if (!rst_n || !enable) begin
      a_state <= A_IDLE;
      tx_wr_ptr <= 16'h0000;
      tx_pkt_len <= 16'h0000;
      tx_seq <= 16'h0000;
      tx_seq_next <= 16'h0001;
      tx_ack_timeout <= 32'h0000_0000;
      tx_retry_count <= 8'h00;
      tx_lane_sent_mask <= 2'b00;
      tx_ack_bitmap <= 2'b00;
      tx_packet_active <= 1'b0;
      tx_packet_loading <= 1'b0;
      tx_done_pulse <= 1'b0;
      tx_error_overflow <= 1'b0;
      tx_error_retry_exhausted <= 1'b0;
      tx_done_count <= 8'h00;
      retry_count_dbg <= 8'h00;
      dbg_tlast_count <= 4'h0;
      dbg_start_count <= 4'h0;
      dbg_overflow_count <= 4'h0;
      a_send_start_req <= 1'b0;
      a_send_start_seq <= 16'h0000;
      a_send_start_total_len <= 16'h0000;
    end else begin
      tx_done_pulse <= 1'b0;
      tx_error_overflow <= 1'b0;
      a_send_start_req <= 1'b0;

      if (NODE_ID == 0) begin
        if (ack_good_pulse && tx_packet_active) begin
          tx_ack_bitmap <= tx_ack_bitmap | tx_lane_sent_mask;
        end

        case (a_state)
          A_IDLE: begin
            tx_wr_ptr <= 16'h0000;
            tx_packet_active <= 1'b0;
            tx_packet_loading <= 1'b0;
            tx_ack_bitmap <= 2'b00;
            if (s_axis_tx_tvalid && s_axis_tx_tready) begin
              tx_pkt_buf[0] <= s_axis_tx_tdata;
              tx_wr_ptr <= 16'd1;
              tx_packet_active <= 1'b1;
              tx_packet_loading <= 1'b1;
              if (s_axis_tx_tlast) begin
                if (dbg_tlast_count != 4'hf) dbg_tlast_count <= dbg_tlast_count + 4'd1;
                tx_pkt_len <= 16'd1;
                tx_seq <= tx_seq_next;
                tx_lane_sent_mask <= lane_enable_mask;
                tx_packet_loading <= 1'b0;
                a_state <= A_START_SEND;
              end else begin
                a_state <= A_COLLECT;
              end
            end
          end

          A_COLLECT: begin
            if (s_axis_tx_tvalid && s_axis_tx_tready) begin
              if (tx_wr_ptr < MAX_PACKET_BYTES[15:0]) begin
                tx_pkt_buf[tx_wr_ptr] <= s_axis_tx_tdata;
                next_len_v = tx_wr_ptr + 1;
                tx_wr_ptr <= tx_wr_ptr + 16'd1;
                if (s_axis_tx_tlast) begin
                  if (dbg_tlast_count != 4'hf) dbg_tlast_count <= dbg_tlast_count + 4'd1;
                  tx_pkt_len <= next_len_v[15:0];
                  tx_seq <= tx_seq_next;
                  tx_lane_sent_mask <= lane_enable_mask;
                  tx_packet_loading <= 1'b0;
                  a_state <= A_START_SEND;
                end
              end else begin
                if (dbg_overflow_count != 4'hf) dbg_overflow_count <= dbg_overflow_count + 4'd1;
                tx_error_overflow <= 1'b1;
                tx_packet_active <= 1'b0;
                tx_packet_loading <= 1'b0;
                a_state <= A_IDLE;
              end
            end
          end

          A_START_SEND: begin
            if (send_active == 2'b00 && lane_tx_busy == 2'b00) begin
              a_send_start_req <= 1'b1;
              a_send_start_seq <= tx_seq;
              a_send_start_total_len <= tx_pkt_len;
              if (dbg_start_count != 4'hf) dbg_start_count <= dbg_start_count + 4'd1;
              tx_ack_timeout <= FRAG_TIMEOUT_CYCLES[31:0];
              a_state <= A_WAIT_SEND;
            end
          end

          A_WAIT_SEND: begin
            if (!a_send_start_req && send_active == 2'b00 && lane_tx_busy == 2'b00) begin
              a_state <= A_WAIT_ACK;
            end
          end

          A_WAIT_ACK: begin
            if (ack_good_pulse) begin
              tx_done_pulse <= 1'b1;
              tx_packet_active <= 1'b0;
              tx_seq_next <= tx_seq_next + 16'd1;
              tx_retry_count <= 8'h00;
              if (tx_done_count != 8'hff) tx_done_count <= tx_done_count + 8'd1;
              a_state <= A_IDLE;
            end else if (tx_ack_timeout != 32'h0000_0000) begin
              tx_ack_timeout <= tx_ack_timeout - 1'b1;
            end else if (tx_retry_count >= MAX_RETRY[7:0]) begin
              tx_error_retry_exhausted <= 1'b1;
              tx_packet_active <= 1'b0;
              a_state <= A_IDLE;
            end else begin
              tx_retry_count <= tx_retry_count + 8'd1;
              retry_count_dbg <= retry_count_dbg + 8'd1;
              a_state <= A_START_SEND;
            end
          end

          default: a_state <= A_IDLE;
        endcase
      end else begin
        tx_packet_active <= b_ack_pending || (send_active != 2'b00);
        tx_packet_loading <= 1'b0;
      end
    end
  end

  always_ff @(posedge clk_phy) begin
    integer ri;
    integer store_idx_v;
    integer seg_len_v;
    integer expected_len_v;
    logic [1:0] bit_v;

    if (!rst_n || !enable) begin
      rx_idx[0] <= 16'h0000;
      rx_idx[1] <= 16'h0000;
      rx_magic[0] <= 8'h00;
      rx_magic[1] <= 8'h00;
      rx_type[0] <= 8'h00;
      rx_type[1] <= 8'h00;
      rx_session[0] <= 16'h0000;
      rx_session[1] <= 16'h0000;
      rx_seq[0] <= 16'h0000;
      rx_seq[1] <= 16'h0000;
      rx_total_len[0] <= 16'h0000;
      rx_total_len[1] <= 16'h0000;
      rx_payload_idx[0] <= 16'h0000;
      rx_payload_idx[1] <= 16'h0000;
      rx_parse_error <= 2'b00;
      b_seq <= 16'h0000;
      b_total_len <= 16'h0000;
      b_seg_bitmap <= 2'b00;
      b_ctx_valid <= 1'b0;
      b_ack_set_req <= 1'b0;
      b_ack_set_seq <= 16'h0000;
      b_ack_set_bitmap <= 2'b00;
      b_output_start_req <= 1'b0;
      rx_done_pulse <= 1'b0;
      rx_done_count <= 8'h00;
      ack_good_pulse <= 1'b0;
      ack_rx_count <= 8'h00;
      rx_header_error <= 1'b0;
      rx_protocol_error <= 1'b0;
    end else begin
      rx_done_pulse <= 1'b0;
      ack_good_pulse <= 1'b0;
      rx_header_error <= 1'b0;
      rx_protocol_error <= 1'b0;
      b_ack_set_req <= 1'b0;
      b_output_start_req <= 1'b0;

      for (ri = 0; ri < 2; ri = ri + 1) begin
        if (lane_rx_tvalid[ri] && lane_rx_tready[ri]) begin
          case (rx_idx[ri])
            16'd0: begin
              rx_magic[ri] <= lane_rx_tdata[ri];
              rx_parse_error[ri] <= 1'b0;
            end
            16'd1: rx_type[ri] <= lane_rx_tdata[ri];
            16'd2: rx_session[ri][7:0] <= lane_rx_tdata[ri];
            16'd3: rx_session[ri][15:8] <= lane_rx_tdata[ri];
            16'd4: rx_seq[ri][7:0] <= lane_rx_tdata[ri];
            16'd5: rx_seq[ri][15:8] <= lane_rx_tdata[ri];
            16'd6: rx_total_len[ri][7:0] <= lane_rx_tdata[ri];
            16'd7: rx_total_len[ri][15:8] <= lane_rx_tdata[ri];
            default: begin
              if ((NODE_ID == 1) && (rx_magic[ri] == DATA_MAGIC) &&
                  (rx_session[ri] == session_id) &&
                  (rx_total_len[ri] != 16'h0000) &&
                  (rx_total_len[ri] <= MAX_PACKET_BYTES[15:0])) begin
                store_idx_v = lane_payload_offset(ri[0], rx_total_len[ri]) + rx_payload_idx[ri];
                if (store_idx_v < MAX_PACKET_BYTES) begin
                  rx_pkt_buf[store_idx_v] <= lane_rx_tdata[ri];
                end else begin
                  rx_parse_error[ri] <= 1'b1;
                end
                rx_payload_idx[ri] <= rx_payload_idx[ri] + 16'd1;
              end
            end
          endcase

          if (lane_rx_tlast[ri]) begin
            seg_len_v = rx_idx[ri] + 1 - STRIPE_HDR_BYTES;
            if ((NODE_ID == 0) && (rx_magic[ri] == ACK_MAGIC)) begin
              if ((ri == 0) &&
                  (rx_session[ri] == session_id) &&
                  (rx_seq[ri] == tx_seq) &&
                  (rx_idx[ri] == (ACK_BYTES - 1)) &&
                  ((lane_rx_tdata[ri][1:0] & tx_lane_sent_mask) == tx_lane_sent_mask)) begin
                ack_good_pulse <= 1'b1;
                if (ack_rx_count != 8'hff) ack_rx_count <= ack_rx_count + 8'd1;
              end else begin
                rx_protocol_error <= 1'b1;
              end
            end else if ((NODE_ID == 1) && (rx_magic[ri] == DATA_MAGIC)) begin
              expected_len_v = lane_payload_len(ri[0], rx_total_len[ri]);
              if ((rx_type[ri][0] == ri[0]) &&
                  (rx_session[ri] == session_id) &&
                  (rx_total_len[ri] != 16'h0000) &&
                  (rx_total_len[ri] <= MAX_PACKET_BYTES[15:0]) &&
                  (seg_len_v == expected_len_v) &&
                  !rx_parse_error[ri]) begin
                if (!b_ctx_valid || (b_seq != rx_seq[ri])) begin
                  b_ctx_valid <= 1'b1;
                  b_seq <= rx_seq[ri];
                  b_total_len <= rx_total_len[ri];
                  b_seg_bitmap <= 2'b00;
                end
                bit_v = (ri == 0) ? 2'b01 : 2'b10;
                b_seg_bitmap <= ((!b_ctx_valid || (b_seq != rx_seq[ri])) ? 2'b00 : b_seg_bitmap) | bit_v;
                if ((((!b_ctx_valid || (b_seq != rx_seq[ri])) ? 2'b00 : b_seg_bitmap) | bit_v) == 2'b11) begin
                  b_ack_set_req <= 1'b1;
                  b_ack_set_seq <= rx_seq[ri];
                  b_ack_set_bitmap <= 2'b11;
                  b_output_start_req <= 1'b1;
                  rx_done_pulse <= 1'b1;
                  if (rx_done_count != 8'hff) rx_done_count <= rx_done_count + 8'd1;
                end
              end else begin
                rx_protocol_error <= 1'b1;
              end
            end else begin
              rx_header_error <= 1'b1;
            end
            rx_idx[ri] <= 16'h0000;
            rx_payload_idx[ri] <= 16'h0000;
          end else begin
            rx_idx[ri] <= rx_idx[ri] + 16'd1;
          end
        end
      end
    end
  end

  always_ff @(posedge clk_phy) begin
    if (!rst_n || !enable) begin
      b_output_active <= 1'b0;
      b_out_idx <= 16'h0000;
    end else if (NODE_ID == 1) begin
      if (b_output_start_req) begin
        b_output_active <= 1'b1;
        b_out_idx <= 16'h0000;
      end else if (b_output_active && m_axis_rx_tready) begin
        if (b_out_idx == (b_total_len - 16'd1)) begin
          b_output_active <= 1'b0;
          b_out_idx <= 16'h0000;
        end else begin
          b_out_idx <= b_out_idx + 16'd1;
        end
      end
    end else begin
      b_output_active <= 1'b0;
      b_out_idx <= 16'h0000;
    end
  end

  always_ff @(posedge clk_phy) begin
    if (!rst_n || !enable) begin
      ack_tx_count <= 8'h00;
      b_ack_pending <= 1'b0;
      b_ack_seq <= 16'h0000;
      b_ack_bitmap <= 2'b00;
      b_ack_guard_active <= 1'b0;
      b_ack_guard_cnt <= 32'h0000_0000;
      b_send_start_req <= 1'b0;
      b_send_start_seq <= 16'h0000;
      b_send_start_ack_bitmap <= 2'b00;
    end else if (NODE_ID == 1) begin
      b_send_start_req <= 1'b0;
      if (b_ack_set_req) begin
        b_ack_pending <= 1'b1;
        b_ack_seq <= b_ack_set_seq;
        b_ack_bitmap <= b_ack_set_bitmap;
        b_ack_guard_active <= 1'b0;
        b_ack_guard_cnt <= 32'h0000_0000;
      end else if (!b_ack_pending) begin
        b_ack_guard_active <= 1'b0;
        b_ack_guard_cnt <= 32'h0000_0000;
      end else if (!b_ack_guard_active) begin
        b_ack_guard_active <= 1'b1;
        b_ack_guard_cnt <= RX_GUARD_CYCLES[31:0];
      end else if (b_ack_guard_cnt != 32'h0000_0000) begin
        b_ack_guard_cnt <= b_ack_guard_cnt - 1'b1;
      end else if ((send_active == 2'b00) && (lane_tx_busy == 2'b00) &&
                   (lane_rx_active == 2'b00)) begin
        b_send_start_req <= 1'b1;
        b_send_start_seq <= b_ack_seq;
        b_send_start_ack_bitmap <= b_ack_bitmap;
        b_ack_pending <= 1'b0;
        b_ack_guard_active <= 1'b0;
        if (ack_tx_count != 8'hff) ack_tx_count <= ack_tx_count + 8'd1;
      end
    end else begin
      b_ack_pending <= 1'b0;
      b_send_start_req <= 1'b0;
    end
  end

  assign m_axis_rx_tvalid = (NODE_ID == 1) && b_output_active;
  assign m_axis_rx_tdata  = rx_pkt_buf[b_out_idx];
  assign m_axis_rx_tlast  = b_output_active && (b_out_idx == (b_total_len - 16'd1));

  assign rx_ctx_valid = b_ctx_valid;
  assign rx_ctx_complete = b_output_active;
  assign rx_frame_overflow_any = 1'b0;
  assign rx_crc_error_any = |lane_rx_crc_error;
  assign rx_overrun_error_any = |lane_rx_overrun_error;

  assign lane_tx_busy_dbg = lane_tx_busy;
  assign lane_rx_frame_pulse_dbg = lane_rx_tvalid & lane_rx_tready & lane_rx_tlast;
  assign lane_rx_crc_error_dbg = lane_rx_crc_error;
  assign lane_rx_error_dbg = lane_rx_overrun_error | {rx_parse_error[1], rx_parse_error[0]};
  assign lane_rx_debug_status_dbg = {lane_rx_debug[1], lane_rx_debug[0]};

  assign tx_frag_pending_dbg = {{(MAX_FRAGS-1){1'b0}}, tx_packet_active};
  assign tx_frag_inflight_dbg = {{(MAX_FRAGS-1){1'b0}}, (send_active != 2'b00)};
  assign tx_frag_acked_dbg = {{(MAX_FRAGS-1){1'b0}}, ack_good_pulse};
  assign rx_recv_bitmap_dbg = {{(MAX_FRAGS-1){1'b0}}, (b_seg_bitmap == 2'b11)};

  always_comb begin
    debug_status = 32'hC000_0000;
    debug_status[27:24] = NODE_ID[3:0];
    debug_status[23:21] = a_state;
    if (NODE_ID == 0) begin
      debug_status[20] = s_axis_tx_tvalid;
      debug_status[19] = s_axis_tx_tready;
      debug_status[18] = s_axis_tx_tlast;
      debug_status[17] = tx_packet_active;
      debug_status[16] = tx_packet_loading;
      debug_status[15:12] = dbg_tlast_count;
      debug_status[11:8] = dbg_start_count;
      debug_status[7:0] = tx_wr_ptr[7:0];
    end else begin
      debug_status[20:19] = send_active;
      debug_status[18:17] = lane_tx_busy;
      debug_status[16] = b_ack_pending;
      debug_status[15:14] = b_seg_bitmap;
      debug_status[13:12] = lane_rx_frame_pulse_dbg;
      debug_status[11:10] = lane_rx_crc_error;
      debug_status[9:8] = lane_rx_overrun_error;
      debug_status[7:0] = rx_done_count;
    end
  end
endmodule
