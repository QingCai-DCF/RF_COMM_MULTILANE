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
  output logic [MAX_FRAGS-1:0]         recv_bitmap_dbg
);
  localparam int DATA_HDR_BYTES = IRP_DATA_HDR_BYTES;
  localparam int ACK_HDR_BYTES  = IRP_ACK_HDR_BYTES;
  localparam int ACK_BITMAP_BYTES = (MAX_FRAGS + 7) / 8;

  logic [7:0] reassembly_buf [0:MAX_PACKET_BYTES-1];
  logic [15:0] ctx_session_id;
  logic [15:0] ctx_pkt_seq;
  logic [15:0] ctx_total_len;
  logic [7:0]  ctx_frag_count;
  logic [MAX_FRAGS-1:0] recv_bitmap;
  logic [31:0] ctx_timeout;
  logic [15:0] flush_ptr;

  logic        last_done_valid;
  logic [15:0] last_done_session_id;
  logic [15:0] last_done_pkt_seq;
  logic [7:0]  last_done_frag_count;
  logic [MAX_FRAGS-1:0] last_done_bitmap;

  logic [7:0]  frame_type;
  logic [7:0]  frame_vt_byte;
  logic [15:0] frame_session;
  logic [15:0] frame_seq;
  logic [7:0]  frame_frag_idx;
  logic [7:0]  frame_frag_count;
  logic [15:0] frame_total_len;
  logic [7:0]  frame_payload_len;
  logic [15:0] frame_hdr_crc_rx;
  logic [15:0] frame_hdr_crc_calc;
  logic [7:0]  ack_bitmap_len;
  logic [MAX_FRAGS-1:0] parsed_ack_bitmap;
  logic [MAX_FRAGS-1:0] full_mask;
  logic [15:0] frag_offset;
  logic        data_frame_ok;
  logic        ack_frame_ok;
  integer i;
  integer hb;
  integer bb;

  function automatic logic [MAX_FRAGS-1:0] frag_mask(input integer count);
    integer n;
    begin
      frag_mask = '0;
      for (n = 0; n < MAX_FRAGS; n = n + 1) begin
        if (n < count) frag_mask[n] = 1'b1;
      end
    end
  endfunction

  task automatic build_ack_frame(
    input logic [15:0] a_session,
    input logic [15:0] a_seq,
    input logic [7:0]  a_frag_count,
    input logic [MAX_FRAGS-1:0] a_bitmap,
    input logic        a_complete
  );
    logic [15:0] crc16_acc;
    logic [7:0]  bitmap_bytes;
    logic [7:0]  byte_val;
    integer ack_i;
    integer ack_j;
    begin
      ack_issue_frame_data = '0;
      bitmap_bytes = (a_frag_count + 7) / 8;
      ack_issue_frame_data[8*0  +: 8] = IRP_SOF;
      ack_issue_frame_data[8*1  +: 8] = {IRP_VERSION, IRP_TYPE_ACK};
      ack_issue_frame_data[8*2  +: 8] = a_session[7:0];
      ack_issue_frame_data[8*3  +: 8] = a_session[15:8];
      ack_issue_frame_data[8*4  +: 8] = a_seq[7:0];
      ack_issue_frame_data[8*5  +: 8] = a_seq[15:8];
      ack_issue_frame_data[8*6  +: 8] = a_frag_count;
      ack_issue_frame_data[8*7  +: 8] = bitmap_bytes;
      ack_issue_frame_data[8*8  +: 8] = {7'd0, a_complete};
      ack_issue_frame_data[8*9  +: 8] = 8'h00;
      crc16_acc = 16'hFFFF;
      for (ack_i = 0; ack_i < 10; ack_i = ack_i + 1) begin
        crc16_acc = crc16_ccitt_next_byte(ack_issue_frame_data[8*ack_i +: 8], crc16_acc);
      end
      ack_issue_frame_data[8*10 +: 8] = crc16_acc[7:0];
      ack_issue_frame_data[8*11 +: 8] = crc16_acc[15:8];
      for (ack_i = 0; ack_i < ACK_BITMAP_BYTES; ack_i = ack_i + 1) begin
        byte_val = 8'h00;
        if (ack_i < bitmap_bytes) begin
          for (ack_j = 0; ack_j < 8; ack_j = ack_j + 1) begin
            if ((ack_i*8 + ack_j) < MAX_FRAGS) byte_val[ack_j] = a_bitmap[ack_i*8 + ack_j];
          end
        end
        ack_issue_frame_data[8*(ACK_HDR_BYTES + ack_i) +: 8] = byte_val;
      end
      ack_issue_frame_len = ACK_HDR_BYTES + bitmap_bytes;
    end
  endtask

  assign in_frame_ready  = enable;
  assign recv_bitmap_dbg = recv_bitmap;

  always_comb begin
    frame_vt_byte      = in_frame_data[8*1 +: 8];
    frame_type         = frame_vt_byte[3:0];
    frame_session      = {in_frame_data[8*3 +: 8], in_frame_data[8*2 +: 8]};
    frame_seq          = {in_frame_data[8*5 +: 8], in_frame_data[8*4 +: 8]};
    frame_frag_idx     = in_frame_data[8*6 +: 8];
    frame_frag_count   = in_frame_data[8*7 +: 8];
    frame_total_len    = {in_frame_data[8*9 +: 8], in_frame_data[8*8 +: 8]};
    frame_payload_len  = in_frame_data[8*10 +: 8];
    frame_hdr_crc_rx   = 16'h0000;
    frame_hdr_crc_calc = 16'hFFFF;
    ack_bitmap_len     = in_frame_data[8*7 +: 8];
    parsed_ack_bitmap  = '0;
    full_mask          = frag_mask(frame_frag_count);
    frag_offset        = frame_frag_idx * FRAGMENT_BYTES;
    data_frame_ok      = 1'b0;
    ack_frame_ok       = 1'b0;

    if ((in_frame_data[8*0 +: 8] == IRP_SOF) && (frame_vt_byte[7:4] == IRP_VERSION)) begin
      if (frame_type == IRP_TYPE_ACK) begin
        frame_hdr_crc_rx   = {in_frame_data[8*11 +: 8], in_frame_data[8*10 +: 8]};
        frame_hdr_crc_calc = 16'hFFFF;
        for (hb = 0; hb < 10; hb = hb + 1) begin
          frame_hdr_crc_calc = crc16_ccitt_next_byte(in_frame_data[8*hb +: 8], frame_hdr_crc_calc);
        end
        if ((in_frame_len >= ACK_HDR_BYTES) && (ack_bitmap_len <= ACK_BITMAP_BYTES) && (in_frame_len >= (ACK_HDR_BYTES + ack_bitmap_len)) && (frame_hdr_crc_calc == frame_hdr_crc_rx)) begin
          for (bb = 0; bb < MAX_FRAGS; bb = bb + 1) begin
            if ((bb/8) < ack_bitmap_len)
              parsed_ack_bitmap[bb] = in_frame_data[8*(ACK_HDR_BYTES + (bb/8)) + (bb%8)];
          end
          ack_frame_ok = 1'b1;
        end
      end else if (frame_type == IRP_TYPE_DATA) begin
        frame_hdr_crc_rx   = {in_frame_data[8*13 +: 8], in_frame_data[8*12 +: 8]};
        frame_hdr_crc_calc = 16'hFFFF;
        for (hb = 0; hb < 12; hb = hb + 1) begin
          frame_hdr_crc_calc = crc16_ccitt_next_byte(in_frame_data[8*hb +: 8], frame_hdr_crc_calc);
        end
        if ((in_frame_len >= DATA_HDR_BYTES) &&
            (in_frame_len == (DATA_HDR_BYTES + frame_payload_len)) &&
            (frame_hdr_crc_calc == frame_hdr_crc_rx) &&
            (frame_session == session_id) &&
            (frame_frag_count != 0) &&
            (frame_frag_idx < frame_frag_count) &&
            (frame_payload_len != 0) &&
            (frame_payload_len <= FRAGMENT_BYTES) &&
            (frame_total_len <= MAX_PACKET_BYTES) &&
            ((frag_offset + frame_payload_len) <= frame_total_len)) begin
          data_frame_ok = 1'b1;
        end
      end
    end
  end

  always_ff @(posedge clk) begin
    if (!rst_n) begin
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
      ctx_session_id        <= 16'h0000;
      ctx_pkt_seq           <= 16'h0000;
      ctx_total_len         <= 16'h0000;
      ctx_frag_count        <= 8'h00;
      recv_bitmap           <= '0;
      ctx_timeout           <= 32'h0000_0000;
      flush_ptr             <= 16'h0000;
      last_done_valid       <= 1'b0;
      last_done_session_id  <= 16'h0000;
      last_done_pkt_seq     <= 16'h0000;
      last_done_frag_count  <= 8'h00;
      last_done_bitmap      <= '0;
    end else begin
      ack_update_valid    <= 1'b0;
      ack_update_complete <= 1'b0;
      rx_done_pulse    <= 1'b0;
      header_error     <= 1'b0;
      protocol_error   <= 1'b0;

      if (!enable) begin
        ack_issue_valid <= 1'b0;
        m_axis_tvalid   <= 1'b0;
        m_axis_tlast    <= 1'b0;
        rx_ctx_valid    <= 1'b0;
        rx_ctx_complete <= 1'b0;
        recv_bitmap     <= '0;
        ctx_timeout     <= 32'h0000_0000;
        flush_ptr       <= 16'h0000;
        last_done_valid <= 1'b0;
      end else begin
        if (ack_issue_valid && ack_issue_ready) ack_issue_valid <= 1'b0;

        if (rx_ctx_valid && !rx_ctx_complete) begin
          if (ctx_timeout != 0) begin
            ctx_timeout <= ctx_timeout - 1'b1;
          end else begin
            protocol_error <= 1'b1;
            rx_ctx_valid    <= 1'b0;
            rx_ctx_complete <= 1'b0;
            recv_bitmap     <= '0;
            flush_ptr       <= 16'h0000;
          end
        end

        if (in_frame_valid && in_frame_ready) begin
          if ((in_frame_data[8*0 +: 8] != IRP_SOF) || (frame_vt_byte[7:4] != IRP_VERSION)) begin
            header_error <= 1'b1;
          end else if (frame_type == IRP_TYPE_ACK) begin
            if (ack_frame_ok) begin
              ack_update_valid      <= 1'b1;
              ack_update_session_id <= frame_session;
              ack_update_pkt_seq    <= frame_seq;
              ack_update_complete   <= in_frame_data[8*8 +: 8][0];
              ack_update_bitmap     <= parsed_ack_bitmap;
            end else begin
              header_error <= 1'b1;
            end
          end else if (frame_type == IRP_TYPE_DATA) begin
            if (!data_frame_ok) begin
              if ((frame_session == session_id) && (in_frame_len >= DATA_HDR_BYTES)) protocol_error <= 1'b1;
              else header_error <= 1'b1;
            end else if (last_done_valid && (frame_session == last_done_session_id) && (frame_seq == last_done_pkt_seq)) begin
              build_ack_frame(last_done_session_id, last_done_pkt_seq, last_done_frag_count, last_done_bitmap, 1'b1);
              ack_issue_valid <= 1'b1;
            end else begin
              if (!rx_ctx_valid) begin
                rx_ctx_valid    <= 1'b1;
                rx_ctx_complete <= 1'b0;
                ctx_session_id  <= frame_session;
                ctx_pkt_seq     <= frame_seq;
                ctx_total_len   <= frame_total_len;
                ctx_frag_count  <= frame_frag_count;
                recv_bitmap     <= '0;
                flush_ptr       <= 16'h0000;

                begin
                  logic [MAX_FRAGS-1:0] next_bitmap_v;
                  next_bitmap_v = '0;
                  for (i = 0; i < FRAGMENT_BYTES; i = i + 1) begin
                    if (i < frame_payload_len) reassembly_buf[frag_offset + i] <= in_frame_data[8*(DATA_HDR_BYTES + i) +: 8];
                  end
                  next_bitmap_v[frame_frag_idx] = 1'b1;
                  recv_bitmap   <= next_bitmap_v;
                  ctx_timeout   <= REASSEMBLY_TIMEOUT_CYCLES;
                  if ((next_bitmap_v & full_mask) == full_mask) rx_ctx_complete <= 1'b1;
                  build_ack_frame(frame_session, frame_seq, frame_frag_count, next_bitmap_v, 1'b0);
                  ack_issue_valid <= 1'b1;
                end
              end else if ((frame_session != ctx_session_id) || (frame_seq != ctx_pkt_seq) || (frame_frag_count != ctx_frag_count) || (frame_total_len != ctx_total_len)) begin
                protocol_error <= 1'b1;
              end else begin
                begin
                  logic [MAX_FRAGS-1:0] next_bitmap_v;
                  next_bitmap_v = recv_bitmap;
                  if (!recv_bitmap[frame_frag_idx]) begin
                    for (i = 0; i < FRAGMENT_BYTES; i = i + 1) begin
                      if (i < frame_payload_len) reassembly_buf[frag_offset + i] <= in_frame_data[8*(DATA_HDR_BYTES + i) +: 8];
                    end
                  end
                  next_bitmap_v[frame_frag_idx] = 1'b1;
                  recv_bitmap   <= next_bitmap_v;
                  ctx_timeout   <= REASSEMBLY_TIMEOUT_CYCLES;
                  if ((next_bitmap_v & full_mask) == full_mask) rx_ctx_complete <= 1'b1;
                  build_ack_frame(frame_session, frame_seq, frame_frag_count, next_bitmap_v, 1'b0);
                  ack_issue_valid <= 1'b1;
                end
              end
            end
          end else begin
            protocol_error <= 1'b1;
          end
        end

        if (rx_ctx_valid && rx_ctx_complete) begin
          if (!m_axis_tvalid || m_axis_tready) begin
            if (flush_ptr < ctx_total_len) begin
              m_axis_tdata  <= reassembly_buf[flush_ptr];
              m_axis_tvalid <= 1'b1;
              m_axis_tlast  <= (flush_ptr == ctx_total_len - 1'b1);
              flush_ptr     <= flush_ptr + 1'b1;
            end else begin
              m_axis_tvalid        <= 1'b0;
              m_axis_tlast         <= 1'b0;
              rx_done_pulse        <= 1'b1;
              last_done_valid      <= 1'b1;
              last_done_session_id <= ctx_session_id;
              last_done_pkt_seq    <= ctx_pkt_seq;
              last_done_frag_count <= ctx_frag_count;
              last_done_bitmap     <= recv_bitmap;
              build_ack_frame(ctx_session_id, ctx_pkt_seq, ctx_frag_count, recv_bitmap, 1'b1);
              ack_issue_valid      <= 1'b1;
              rx_ctx_valid         <= 1'b0;
              rx_ctx_complete      <= 1'b0;
              recv_bitmap          <= '0;
              ctx_timeout          <= 32'h0000_0000;
              flush_ptr            <= 16'h0000;
            end
          end
        end
      end
    end
  end
endmodule
