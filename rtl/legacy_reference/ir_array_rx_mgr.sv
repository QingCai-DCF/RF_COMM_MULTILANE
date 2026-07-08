import ir_protocol_pkg::*;

module ir_array_rx_mgr #(
  parameter int MAX_PACKET_BYTES = 256,
  parameter int FRAGMENT_BYTES   = 16,
  parameter int MAX_FRAME_BYTES  = 64,
  parameter int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES,
  parameter int REASSEMBLY_TIMEOUT_CYCLES = 200000
)(
  input  logic                         clk,
  input  logic                         rst_n,
  input  logic                         enable,
  input  logic [15:0]                  session_id,
  input  logic                         in_frame_valid,
  output logic                         in_frame_ready,
  input  logic [8*MAX_FRAME_BYTES-1:0] in_frame_data,
  input  logic [15:0]                  in_frame_len,
  input  logic [7:0]                   in_lane_id,
  output logic                         ack_update_valid,
  output logic [15:0]                  ack_update_session_id,
  output logic [15:0]                  ack_update_pkt_seq,
  output logic                         ack_update_complete,
  output logic [MAX_FRAGS-1:0]         ack_update_bitmap,
  output logic                         ack_issue_valid,
  input  logic                         ack_issue_ready,
  output logic [8*MAX_FRAME_BYTES-1:0] ack_issue_frame_data,
  output logic [15:0]                  ack_issue_frame_len,
  output logic [7:0]                   m_axis_tdata,
  output logic                         m_axis_tvalid,
  input  logic                         m_axis_tready,
  output logic                         m_axis_tlast,
  output logic                         rx_ctx_valid,
  output logic                         rx_ctx_complete,
  output logic                         rx_done_pulse,
  output logic                         header_error,
  output logic                         protocol_error,
  output logic [MAX_FRAGS-1:0]         recv_bitmap_dbg,
  output logic [31:0]                  rx_debug_status
);
  localparam int DATA_HDR_BYTES   = IRP_DATA_HDR_BYTES;
  localparam int ACK_HDR_BYTES    = IRP_ACK_HDR_BYTES;
  localparam int ACK_BITMAP_BYTES = (MAX_FRAGS + 7) / 8;
  localparam int FLUSH_FRAG_W     = (MAX_FRAGS <= 1) ? 1 : $clog2(MAX_FRAGS);
  localparam int FLUSH_BYTE_W     = (FRAGMENT_BYTES <= 1) ? 1 : $clog2(FRAGMENT_BYTES);

  logic [7:0] reassembly_frag [0:MAX_FRAGS-1][0:FRAGMENT_BYTES-1];

  logic        frame_pending;
  logic [8*MAX_FRAME_BYTES-1:0] pend_frame_data;
  logic [15:0]                  pend_frame_len;
  logic [7:0]                   pend_lane_id;

  logic        parse_pending;
  logic        parse_is_ack;
  logic        parse_is_data;
  logic        parse_ack_ok;
  logic        parse_data_ok;
  logic        parse_data_crc_ok;
  logic        parse_data_session_ok;
  logic        parse_data_shape_ok;
  logic        parse_hdr_bad;
  logic [15:0] parse_session;
  logic [15:0] parse_seq;
  logic [7:0]  parse_frag_idx;
  logic [7:0]  parse_frag_count;
  logic [15:0] parse_total_len;
  logic [7:0]  parse_payload_len;
  logic        parse_ack_complete;
  logic [MAX_FRAGS-1:0] parse_ack_bitmap;
  logic [MAX_FRAGS-1:0] parse_full_mask;
  logic [8*FRAGMENT_BYTES-1:0] parse_payload;

  logic        parse_is_ack_c;
  logic        parse_is_data_c;
  logic        parse_ack_ok_c;
  logic        parse_data_ok_c;
  logic        parse_data_crc_ok_c;
  logic        parse_data_session_ok_c;
  logic        parse_data_shape_ok_c;
  logic        parse_hdr_bad_c;
  logic [15:0] parse_session_c;
  logic [15:0] parse_seq_c;
  logic [7:0]  parse_frag_idx_c;
  logic [7:0]  parse_frag_count_c;
  logic [15:0] parse_total_len_c;
  logic [7:0]  parse_payload_len_c;
  logic        parse_ack_complete_c;
  logic [MAX_FRAGS-1:0] parse_ack_bitmap_c;
  logic [MAX_FRAGS-1:0] parse_full_mask_c;
  logic [8*FRAGMENT_BYTES-1:0] parse_payload_c;

  logic [15:0] ctx_session_id;
  logic [15:0] ctx_pkt_seq;
  logic [15:0] ctx_total_len;
  logic [7:0]  ctx_frag_count;
  logic [MAX_FRAGS-1:0] recv_bitmap;
  logic [31:0] ctx_timeout;
  logic [15:0] flush_count;
  logic [FLUSH_FRAG_W-1:0] flush_frag_idx;
  logic [FLUSH_BYTE_W-1:0] flush_byte_idx;

  logic        last_done_valid;
  logic [15:0] last_done_session_id;
  logic [15:0] last_done_pkt_seq;
  logic [7:0]  last_done_frag_count;
  logic [MAX_FRAGS-1:0] last_done_bitmap;
  logic [31:0] last_done_timeout;

  logic [MAX_FRAGS-1:0] next_bitmap_v;
  integer i;
  integer hb;
  integer bb;
  integer pb;

  initial begin
    if (MAX_FRAGS > IRP_MAX_FRAGS_FIELD) begin
      $error("MAX_FRAGS=%0d exceeds protocol field width", MAX_FRAGS);
    end
  end

  function automatic logic [MAX_FRAGS-1:0] frag_mask(input integer count);
    integer n;
    begin
      frag_mask = '0;
      for (n = 0; n < MAX_FRAGS; n = n + 1) begin
        if (n < count) frag_mask[n] = 1'b1;
      end
    end
  endfunction

  function automatic logic [3:0] frag_bits_low4(input logic [MAX_FRAGS-1:0] bits);
    integer n;
    begin
      frag_bits_low4 = 4'h0;
      for (n = 0; n < MAX_FRAGS && n < 4; n = n + 1) begin
        frag_bits_low4[n] = bits[n];
      end
    end
  endfunction

  function automatic logic [7:0] ack_bitmap_bytes_fn(input logic [7:0] frag_count_f);
    begin
      ack_bitmap_bytes_fn = (frag_count_f + 7) / 8;
    end
  endfunction

  function automatic logic [15:0] ack_frame_len_fn(input logic [7:0] frag_count_f);
    begin
      ack_frame_len_fn = ACK_HDR_BYTES + ack_bitmap_bytes_fn(frag_count_f);
    end
  endfunction

  function automatic logic [8*MAX_FRAME_BYTES-1:0] ack_frame_data_fn(
    input logic [15:0] a_session,
    input logic [15:0] a_seq,
    input logic [7:0]  a_frag_count,
    input logic [MAX_FRAGS-1:0] a_bitmap,
    input logic        a_complete
  );
    logic [8*MAX_FRAME_BYTES-1:0] data_v;
    logic [15:0] crc16_acc;
    logic [7:0]  bitmap_bytes;
    logic [7:0]  byte_val;
    integer ack_i;
    integer ack_j;
    begin
      data_v = '0;
      bitmap_bytes = ack_bitmap_bytes_fn(a_frag_count);
      data_v[8*0  +: 8] = IRP_SOF;
      data_v[8*1  +: 8] = {IRP_VERSION, IRP_TYPE_ACK};
      data_v[8*2  +: 8] = a_session[7:0];
      data_v[8*3  +: 8] = a_session[15:8];
      data_v[8*4  +: 8] = a_seq[7:0];
      data_v[8*5  +: 8] = a_seq[15:8];
      data_v[8*6  +: 8] = a_frag_count;
      data_v[8*7  +: 8] = bitmap_bytes;
      data_v[8*8  +: 8] = {7'd0, a_complete};
      data_v[8*9  +: 8] = 8'h00;
      crc16_acc = 16'hFFFF;
      for (ack_i = 0; ack_i < 10; ack_i = ack_i + 1) begin
        crc16_acc = crc16_ccitt_next_byte(data_v[8*ack_i +: 8], crc16_acc);
      end
      data_v[8*10 +: 8] = crc16_acc[7:0];
      data_v[8*11 +: 8] = crc16_acc[15:8];
      for (ack_i = 0; ack_i < ACK_BITMAP_BYTES; ack_i = ack_i + 1) begin
        byte_val = 8'h00;
        if (ack_i < bitmap_bytes) begin
          for (ack_j = 0; ack_j < 8; ack_j = ack_j + 1) begin
            if ((ack_i*8 + ack_j) < MAX_FRAGS) byte_val[ack_j] = a_bitmap[ack_i*8 + ack_j];
          end
        end
        data_v[8*(ACK_HDR_BYTES + ack_i) +: 8] = byte_val;
      end
      ack_frame_data_fn = data_v;
    end
  endfunction

  assign in_frame_ready  = enable && !frame_pending && !parse_pending && !ack_issue_valid && !(rx_ctx_valid && rx_ctx_complete);
  assign recv_bitmap_dbg = recv_bitmap;

  always_comb begin
    logic [7:0]  vt_byte;
    logic [3:0]  frame_type_v;
    logic [15:0] hdr_crc_rx;
    logic [15:0] hdr_crc_calc;
    logic [7:0]  ack_bitmap_len;
    logic [15:0] frag_offset;

    parse_is_ack_c       = 1'b0;
    parse_is_data_c      = 1'b0;
    parse_ack_ok_c       = 1'b0;
    parse_data_ok_c      = 1'b0;
    parse_data_crc_ok_c  = 1'b0;
    parse_data_session_ok_c = 1'b0;
    parse_data_shape_ok_c = 1'b0;
    parse_hdr_bad_c      = 1'b1;
    parse_session_c      = {pend_frame_data[8*3 +: 8], pend_frame_data[8*2 +: 8]};
    parse_seq_c          = {pend_frame_data[8*5 +: 8], pend_frame_data[8*4 +: 8]};
    parse_frag_idx_c     = pend_frame_data[8*6 +: 8];
    parse_frag_count_c   = pend_frame_data[8*7 +: 8];
    parse_total_len_c    = {pend_frame_data[8*9 +: 8], pend_frame_data[8*8 +: 8]};
    parse_payload_len_c  = pend_frame_data[8*10 +: 8];
    parse_ack_complete_c = pend_frame_data[8*8];
    parse_ack_bitmap_c   = '0;
    parse_full_mask_c    = frag_mask(pend_frame_data[8*7 +: 8]);
    parse_payload_c      = '0;

    vt_byte      = pend_frame_data[8*1 +: 8];
    frame_type_v = vt_byte[3:0];
    ack_bitmap_len = pend_frame_data[8*7 +: 8];
    frag_offset = pend_frame_data[8*6 +: 8] * FRAGMENT_BYTES;

    for (pb = 0; pb < FRAGMENT_BYTES; pb = pb + 1) begin
      if (pb < pend_frame_data[8*10 +: 8]) parse_payload_c[8*pb +: 8] = pend_frame_data[8*(DATA_HDR_BYTES + pb) +: 8];
    end

    if ((pend_frame_data[8*0 +: 8] == IRP_SOF) && (vt_byte[7:4] == IRP_VERSION)) begin
      parse_hdr_bad_c = 1'b0;
      if (frame_type_v == IRP_TYPE_ACK) begin
        parse_is_ack_c = 1'b1;
        hdr_crc_rx   = {pend_frame_data[8*11 +: 8], pend_frame_data[8*10 +: 8]};
        hdr_crc_calc = 16'hFFFF;
        for (hb = 0; hb < 10; hb = hb + 1) begin
          hdr_crc_calc = crc16_ccitt_next_byte(pend_frame_data[8*hb +: 8], hdr_crc_calc);
        end
        if ((pend_frame_len >= ACK_HDR_BYTES) && (ack_bitmap_len <= ACK_BITMAP_BYTES) &&
            (pend_frame_len >= (ACK_HDR_BYTES + ack_bitmap_len)) && (hdr_crc_calc == hdr_crc_rx)) begin
          for (bb = 0; bb < MAX_FRAGS; bb = bb + 1) begin
            if ((bb/8) < ack_bitmap_len)
              parse_ack_bitmap_c[bb] = pend_frame_data[8*(ACK_HDR_BYTES + (bb/8)) + (bb%8)];
          end
          parse_ack_ok_c = 1'b1;
        end
      end else if (frame_type_v == IRP_TYPE_DATA) begin
        parse_is_data_c = 1'b1;
        hdr_crc_rx   = {pend_frame_data[8*13 +: 8], pend_frame_data[8*12 +: 8]};
        hdr_crc_calc = 16'hFFFF;
        for (hb = 0; hb < 12; hb = hb + 1) begin
          hdr_crc_calc = crc16_ccitt_next_byte(pend_frame_data[8*hb +: 8], hdr_crc_calc);
        end
        parse_data_crc_ok_c = (hdr_crc_calc == hdr_crc_rx);
        parse_data_session_ok_c = (parse_session_c == session_id);
        parse_data_shape_ok_c =
            (pend_frame_len >= DATA_HDR_BYTES) &&
            (pend_frame_len == (DATA_HDR_BYTES + pend_frame_data[8*10 +: 8])) &&
            (parse_frag_count_c != 0) &&
            (parse_frag_count_c <= MAX_FRAGS) &&
            (parse_frag_idx_c < parse_frag_count_c) &&
            (parse_payload_len_c != 0) &&
            (parse_payload_len_c <= FRAGMENT_BYTES) &&
            (parse_total_len_c <= MAX_PACKET_BYTES) &&
            ((frag_offset + parse_payload_len_c) <= parse_total_len_c);
        if (parse_data_shape_ok_c &&
            parse_data_crc_ok_c &&
            parse_data_session_ok_c) begin
          parse_data_ok_c = 1'b1;
        end
      end
    end
  end

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      frame_pending         <= 1'b0;
      pend_frame_data       <= '0;
      pend_frame_len        <= 16'h0000;
      pend_lane_id          <= 8'h00;
      parse_pending         <= 1'b0;
      parse_is_ack          <= 1'b0;
      parse_is_data         <= 1'b0;
      parse_ack_ok          <= 1'b0;
      parse_data_ok         <= 1'b0;
      parse_data_crc_ok     <= 1'b0;
      parse_data_session_ok <= 1'b0;
      parse_data_shape_ok   <= 1'b0;
      parse_hdr_bad         <= 1'b0;
      parse_session         <= 16'h0000;
      parse_seq             <= 16'h0000;
      parse_frag_idx        <= 8'h00;
      parse_frag_count      <= 8'h00;
      parse_total_len       <= 16'h0000;
      parse_payload_len     <= 8'h00;
      parse_ack_complete    <= 1'b0;
      parse_ack_bitmap      <= '0;
      parse_full_mask       <= '0;
      parse_payload         <= '0;
      ack_update_valid      <= 1'b0;
      ack_update_session_id <= 16'h0000;
      ack_update_pkt_seq    <= 16'h0000;
      ack_update_complete   <= 1'b0;
      ack_update_bitmap     <= '0;
      ack_issue_valid       <= 1'b0;
      ack_issue_frame_data  <= '0;
      ack_issue_frame_len   <= 16'h0000;
      m_axis_tdata          <= 8'h00;
      m_axis_tvalid         <= 1'b0;
      m_axis_tlast          <= 1'b0;
      rx_ctx_valid          <= 1'b0;
      rx_ctx_complete       <= 1'b0;
      rx_done_pulse         <= 1'b0;
      header_error          <= 1'b0;
      protocol_error        <= 1'b0;
      rx_debug_status       <= 32'h0000_0000;
      ctx_session_id        <= 16'h0000;
      ctx_pkt_seq           <= 16'h0000;
      ctx_total_len         <= 16'h0000;
      ctx_frag_count        <= 8'h00;
      recv_bitmap           <= '0;
      ctx_timeout           <= 32'h0000_0000;
      flush_count           <= 16'h0000;
      flush_frag_idx        <= '0;
      flush_byte_idx        <= '0;
      last_done_valid       <= 1'b0;
      last_done_session_id  <= 16'h0000;
      last_done_pkt_seq     <= 16'h0000;
      last_done_frag_count  <= 8'h00;
      last_done_bitmap      <= '0;
      last_done_timeout     <= 32'h0000_0000;
    end else begin
      ack_update_valid    <= 1'b0;
      ack_update_complete <= 1'b0;
      rx_done_pulse       <= 1'b0;
      header_error        <= 1'b0;
      protocol_error      <= 1'b0;

      if (in_frame_valid && in_frame_ready) begin
        frame_pending   <= 1'b1;
        pend_frame_data <= in_frame_data;
        pend_frame_len  <= in_frame_len;
        pend_lane_id    <= in_lane_id;
      end

      if (!enable) begin
        frame_pending      <= 1'b0;
        parse_pending      <= 1'b0;
        ack_issue_valid    <= 1'b0;
        m_axis_tvalid      <= 1'b0;
        m_axis_tlast       <= 1'b0;
        rx_ctx_valid       <= 1'b0;
        rx_ctx_complete    <= 1'b0;
        recv_bitmap        <= '0;
        ctx_timeout        <= 32'h0000_0000;
        flush_count        <= 16'h0000;
        flush_frag_idx     <= '0;
        flush_byte_idx     <= '0;
        last_done_valid    <= 1'b0;
        last_done_timeout  <= 32'h0000_0000;
        rx_debug_status    <= 32'h0000_0000;
      end else begin
        if (ack_issue_valid && ack_issue_ready) begin
          ack_issue_valid <= 1'b0;
        end

        if (last_done_valid) begin
          if (last_done_timeout != 0) last_done_timeout <= last_done_timeout - 1'b1;
          else                        last_done_valid   <= 1'b0;
        end

        if (rx_ctx_valid && !rx_ctx_complete) begin
          if (ctx_timeout != 0) begin
            ctx_timeout <= ctx_timeout - 1'b1;
          end else begin
            protocol_error   <= 1'b1;
            rx_debug_status  <= {4'hD, 4'h1, rx_ctx_valid, rx_ctx_complete, 2'b00,
                                 frag_bits_low4(recv_bitmap), ctx_frag_count[3:0],
                                 ctx_total_len[7:0], ctx_pkt_seq[3:0]};
            rx_ctx_valid     <= 1'b0;
            rx_ctx_complete  <= 1'b0;
            recv_bitmap      <= '0;
            flush_count      <= 16'h0000;
            flush_frag_idx   <= '0;
            flush_byte_idx   <= '0;
          end
        end

        if (frame_pending) begin
          frame_pending      <= 1'b0;
          parse_pending      <= 1'b1;
          parse_is_ack       <= parse_is_ack_c;
          parse_is_data      <= parse_is_data_c;
          parse_ack_ok       <= parse_ack_ok_c;
          parse_data_ok      <= parse_data_ok_c;
          parse_data_crc_ok  <= parse_data_crc_ok_c;
          parse_data_session_ok <= parse_data_session_ok_c;
          parse_data_shape_ok <= parse_data_shape_ok_c;
          parse_hdr_bad      <= parse_hdr_bad_c;
          parse_session      <= parse_session_c;
          parse_seq          <= parse_seq_c;
          parse_frag_idx     <= parse_frag_idx_c;
          parse_frag_count   <= parse_frag_count_c;
          parse_total_len    <= parse_total_len_c;
          parse_payload_len  <= parse_payload_len_c;
          parse_ack_complete <= parse_ack_complete_c;
          parse_ack_bitmap   <= parse_ack_bitmap_c;
          parse_full_mask    <= parse_full_mask_c;
          parse_payload      <= parse_payload_c;
        end

        if (parse_pending) begin
          parse_pending <= 1'b0;
          if (parse_hdr_bad) begin
            header_error <= 1'b1;
          end else if (parse_is_ack) begin
            if (parse_ack_ok) begin
              ack_update_valid      <= 1'b1;
              ack_update_session_id <= parse_session;
              ack_update_pkt_seq    <= parse_seq;
              ack_update_complete   <= parse_ack_complete;
              ack_update_bitmap     <= parse_ack_bitmap;
            end else begin
              header_error <= 1'b1;
            end
          end else begin
            if (!parse_data_ok) begin
              if (parse_is_data && parse_data_crc_ok && !parse_data_session_ok) begin
                header_error <= 1'b1;
                rx_debug_status <= {4'hD, 4'h4, parse_session[11:0], session_id[11:0]};
              end else if (parse_is_data && parse_data_shape_ok && !parse_data_crc_ok) begin
                protocol_error <= 1'b1;
                rx_debug_status <= {4'hD, 4'h5, parse_session[7:0], parse_seq[7:0], pend_frame_len[7:0]};
              end else if (parse_is_data && !parse_data_shape_ok) begin
                protocol_error <= 1'b1;
                rx_debug_status <= {4'hD, 4'h6, parse_frag_idx[3:0], parse_frag_count[3:0],
                                    parse_total_len[7:0], parse_payload_len[7:0]};
              end else if ((parse_session == session_id) && (pend_frame_len >= DATA_HDR_BYTES)) begin
                protocol_error  <= 1'b1;
                rx_debug_status <= {4'hD, 4'h2, parse_is_ack, parse_ack_ok, parse_data_ok, parse_hdr_bad,
                                    parse_frag_idx[3:0], parse_frag_count[3:0],
                                    parse_total_len[7:0], parse_payload_len[3:0]};
              end else begin
                header_error <= 1'b1;
              end
            end else if (last_done_valid && (parse_session == last_done_session_id) && (parse_seq == last_done_pkt_seq)) begin
              rx_debug_status <= {4'hD, 4'h9, pend_lane_id[3:0], parse_frag_idx[3:0],
                                  parse_frag_count[3:0], parse_payload_len[3:0],
                                  parse_seq[7:0]};
              if (!ack_issue_valid) begin
                ack_issue_frame_data <= ack_frame_data_fn(last_done_session_id, last_done_pkt_seq, last_done_frag_count, last_done_bitmap, 1'b1);
                ack_issue_frame_len  <= ack_frame_len_fn(last_done_frag_count);
                ack_issue_valid      <= 1'b1;
              end
            end else if (!rx_ctx_valid) begin
              rx_debug_status <= {4'hD, 4'h9, pend_lane_id[3:0], parse_frag_idx[3:0],
                                  parse_frag_count[3:0], parse_payload_len[3:0],
                                  parse_seq[7:0]};
              rx_ctx_valid    <= 1'b1;
              rx_ctx_complete <= 1'b0;
              ctx_session_id  <= parse_session;
              ctx_pkt_seq     <= parse_seq;
              ctx_total_len   <= parse_total_len;
              ctx_frag_count  <= parse_frag_count;
              recv_bitmap     <= '0;
              ctx_timeout     <= REASSEMBLY_TIMEOUT_CYCLES;
              flush_count     <= 16'h0000;
              flush_frag_idx  <= '0;
              flush_byte_idx  <= '0;
              for (i = 0; i < FRAGMENT_BYTES; i = i + 1) begin
                if (i < parse_payload_len) reassembly_frag[parse_frag_idx][i] <= parse_payload[8*i +: 8];
              end
              next_bitmap_v = '0;
              next_bitmap_v[parse_frag_idx] = 1'b1;
              recv_bitmap <= next_bitmap_v;
              if ((next_bitmap_v & parse_full_mask) == parse_full_mask) rx_ctx_complete <= 1'b1;
              if (!ack_issue_valid) begin
                ack_issue_frame_data <= ack_frame_data_fn(parse_session, parse_seq, parse_frag_count, next_bitmap_v,
                                                          ((next_bitmap_v & parse_full_mask) == parse_full_mask));
                ack_issue_frame_len  <= ack_frame_len_fn(parse_frag_count);
                ack_issue_valid      <= 1'b1;
              end
            end else if ((parse_session != ctx_session_id) || (parse_seq != ctx_pkt_seq) || (parse_frag_count != ctx_frag_count) || (parse_total_len != ctx_total_len)) begin
              protocol_error <= 1'b1;
              rx_debug_status <= {4'hD, 4'h3, parse_seq[3:0], ctx_pkt_seq[3:0],
                                  parse_frag_count[3:0], ctx_frag_count[3:0],
                                  parse_total_len[3:0], ctx_total_len[3:0]};
            end else begin
              rx_debug_status <= {4'hD, 4'h9, pend_lane_id[3:0], parse_frag_idx[3:0],
                                  parse_frag_count[3:0], parse_payload_len[3:0],
                                  parse_seq[7:0]};
              next_bitmap_v = recv_bitmap;
              if (!recv_bitmap[parse_frag_idx]) begin
                for (i = 0; i < FRAGMENT_BYTES; i = i + 1) begin
                  if (i < parse_payload_len) reassembly_frag[parse_frag_idx][i] <= parse_payload[8*i +: 8];
                end
              end
              next_bitmap_v[parse_frag_idx] = 1'b1;
              recv_bitmap <= next_bitmap_v;
              ctx_timeout <= REASSEMBLY_TIMEOUT_CYCLES;
              if ((next_bitmap_v & parse_full_mask) == parse_full_mask) rx_ctx_complete <= 1'b1;
              if (!ack_issue_valid) begin
                ack_issue_frame_data <= ack_frame_data_fn(parse_session, parse_seq, parse_frag_count, next_bitmap_v,
                                                          ((next_bitmap_v & parse_full_mask) == parse_full_mask));
                ack_issue_frame_len  <= ack_frame_len_fn(parse_frag_count);
                ack_issue_valid      <= 1'b1;
              end
            end
          end
        end

        if (rx_ctx_valid && rx_ctx_complete) begin
          if (!m_axis_tvalid || m_axis_tready) begin
            if (flush_count < ctx_total_len) begin
              m_axis_tdata  <= reassembly_frag[flush_frag_idx][flush_byte_idx];
              m_axis_tvalid <= 1'b1;
              m_axis_tlast  <= (flush_count == ctx_total_len - 1'b1);
              flush_count   <= flush_count + 1'b1;
              if (flush_byte_idx == FRAGMENT_BYTES-1) begin
                flush_byte_idx <= '0;
                flush_frag_idx <= flush_frag_idx + 1'b1;
              end else begin
                flush_byte_idx <= flush_byte_idx + 1'b1;
              end
            end else begin
              m_axis_tvalid        <= 1'b0;
              m_axis_tlast         <= 1'b0;
              rx_done_pulse        <= 1'b1;
              last_done_valid      <= 1'b1;
              last_done_session_id <= ctx_session_id;
              last_done_pkt_seq    <= ctx_pkt_seq;
              last_done_frag_count <= ctx_frag_count;
              last_done_bitmap     <= recv_bitmap;
              last_done_timeout    <= REASSEMBLY_TIMEOUT_CYCLES;
              if (!ack_issue_valid) begin
                ack_issue_frame_data <= ack_frame_data_fn(ctx_session_id, ctx_pkt_seq, ctx_frag_count, recv_bitmap, 1'b1);
                ack_issue_frame_len  <= ack_frame_len_fn(ctx_frag_count);
                ack_issue_valid      <= 1'b1;
              end
              rx_ctx_valid         <= 1'b0;
              rx_ctx_complete      <= 1'b0;
              recv_bitmap          <= '0;
              ctx_timeout          <= 32'h0000_0000;
              flush_count          <= 16'h0000;
              flush_frag_idx       <= '0;
              flush_byte_idx       <= '0;
            end
          end
        end
      end
    end
  end
endmodule
