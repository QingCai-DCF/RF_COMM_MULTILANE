import ir_protocol_pkg::*;

module ir_array_tx_mgr #(
  parameter int MAX_PACKET_BYTES    = 256,
  parameter int FRAGMENT_BYTES      = 16,
  parameter int MAX_FRAME_BYTES     = 64,
  parameter int MAX_RETRY           = 4,
  parameter int FRAG_TIMEOUT_CYCLES = 50000,
  parameter int MAX_FRAGS           = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES
)(
  input  logic                         clk,
  input  logic                         rst_n,
  input  logic                         enable,
  input  logic [15:0]                  session_id,
  input  logic [7:0]                   s_axis_tdata,
  input  logic                         s_axis_tvalid,
  output logic                         s_axis_tready,
  input  logic                         s_axis_tlast,
  input  logic                         ack_valid,
  input  logic [15:0]                  ack_session_id,
  input  logic [15:0]                  ack_pkt_seq,
  input  logic                         ack_complete,
  input  logic [MAX_FRAGS-1:0]         ack_bitmap,
  output logic                         issue_valid,
  input  logic                         issue_ready,
  output logic [7:0]                   issue_frag_idx,
  output logic [8*MAX_FRAME_BYTES-1:0] issue_frame_data,
  output logic [15:0]                  issue_frame_len,
  output logic [15:0]                  active_pkt_seq,
  output logic                         packet_active,
  output logic                         packet_loading,
  output logic                         done_pulse,
  output logic                         error_overflow,
  output logic                         error_retry_exhausted,
  output logic [MAX_FRAGS-1:0]         frag_pending_dbg,
  output logic [MAX_FRAGS-1:0]         frag_inflight_dbg,
  output logic [MAX_FRAGS-1:0]         frag_acked_dbg
);
  localparam int DATA_HDR_BYTES = IRP_DATA_HDR_BYTES;

  logic [7:0] pkt_buf [0:MAX_PACKET_BYTES-1];
  logic [15:0] pkt_len;
  logic [7:0]  frag_count;
  logic [MAX_FRAGS-1:0] frag_pending;
  logic [MAX_FRAGS-1:0] frag_inflight;
  logic [MAX_FRAGS-1:0] frag_acked;
  logic [7:0]  retry_cnt   [0:MAX_FRAGS-1];
  logic [31:0] timeout_cnt [0:MAX_FRAGS-1];
  logic [15:0] wr_ptr;
  logic [15:0] seq_counter;
  logic        drop_loading;
  logic        waiting_final_ack;
  logic [31:0] final_ack_timeout;

  logic                         build_valid;
  logic [7:0]                   build_frag_idx;
  logic [15:0]                  build_offset;
  logic [7:0]                   build_payload_len;
  logic [8*MAX_FRAME_BYTES-1:0] build_frame_data;
  logic [15:0]                  build_frame_len;
  logic [15:0]                  build_hdr_crc;
  logic [MAX_FRAGS-1:0]         valid_mask;
  logic                         any_inflight;

  integer i;
  integer f;
  integer hb;
  integer pb;

  function automatic logic [MAX_FRAGS-1:0] frag_mask(input integer count);
    integer n;
    begin
      frag_mask = '0;
      for (n = 0; n < MAX_FRAGS; n = n + 1) begin
        if (n < count) frag_mask[n] = 1'b1;
      end
    end
  endfunction

  assign s_axis_tready     = enable && (!packet_active || packet_loading);
  assign frag_pending_dbg  = frag_pending;
  assign frag_inflight_dbg = frag_inflight;
  assign frag_acked_dbg    = frag_acked;
  assign any_inflight      = |frag_inflight;

  always_comb begin
    build_valid       = 1'b0;
    build_frag_idx    = 8'h00;
    build_offset      = 16'h0000;
    build_payload_len = 8'h00;
    build_frame_data  = '0;
    build_frame_len   = 16'h0000;
    build_hdr_crc     = 16'hFFFF;
    valid_mask        = frag_mask(frag_count);

    if (packet_active && !packet_loading && !issue_valid && !any_inflight && !waiting_final_ack) begin
      for (f = 0; f < MAX_FRAGS; f = f + 1) begin
        if (!build_valid && (f < frag_count) && frag_pending[f] && !frag_inflight[f] && !frag_acked[f]) begin
          build_valid    = 1'b1;
          build_frag_idx = f[7:0];
          build_offset   = f * FRAGMENT_BYTES;
          if ((pkt_len - (f * FRAGMENT_BYTES)) >= FRAGMENT_BYTES)
            build_payload_len = FRAGMENT_BYTES[7:0];
          else
            build_payload_len = (pkt_len - (f * FRAGMENT_BYTES));
        end
      end
    end

    if (build_valid) begin
      build_frame_data[8*0  +: 8] = IRP_SOF;
      build_frame_data[8*1  +: 8] = {IRP_VERSION, IRP_TYPE_DATA};
      build_frame_data[8*2  +: 8] = session_id[7:0];
      build_frame_data[8*3  +: 8] = session_id[15:8];
      build_frame_data[8*4  +: 8] = active_pkt_seq[7:0];
      build_frame_data[8*5  +: 8] = active_pkt_seq[15:8];
      build_frame_data[8*6  +: 8] = build_frag_idx;
      build_frame_data[8*7  +: 8] = frag_count;
      build_frame_data[8*8  +: 8] = pkt_len[7:0];
      build_frame_data[8*9  +: 8] = pkt_len[15:8];
      build_frame_data[8*10 +: 8] = build_payload_len;
      build_frame_data[8*11 +: 8] = retry_cnt[build_frag_idx];
      build_hdr_crc = 16'hFFFF;
      for (hb = 0; hb < 12; hb = hb + 1) begin
        build_hdr_crc = crc16_ccitt_next_byte(build_frame_data[8*hb +: 8], build_hdr_crc);
      end
      build_frame_data[8*12 +: 8] = build_hdr_crc[7:0];
      build_frame_data[8*13 +: 8] = build_hdr_crc[15:8];
      for (pb = 0; pb < FRAGMENT_BYTES; pb = pb + 1) begin
        if (pb < build_payload_len)
          build_frame_data[8*(DATA_HDR_BYTES + pb) +: 8] = pkt_buf[build_offset + pb];
      end
      build_frame_len = DATA_HDR_BYTES + build_payload_len;
    end
  end

  always_ff @(posedge clk) begin
    integer new_frag_count;
    integer store_index;
    integer new_pkt_len;
    if (!rst_n) begin
      pkt_len               <= 16'h0000;
      frag_count            <= 8'h00;
      frag_pending          <= '0;
      frag_inflight         <= '0;
      frag_acked            <= '0;
      wr_ptr                <= 16'h0000;
      seq_counter           <= 16'h0001;
      active_pkt_seq        <= 16'h0000;
      packet_active         <= 1'b0;
      packet_loading        <= 1'b0;
      drop_loading          <= 1'b0;
      waiting_final_ack     <= 1'b0;
      final_ack_timeout     <= 32'h0000_0000;
      issue_valid           <= 1'b0;
      issue_frag_idx        <= 8'h00;
      issue_frame_data      <= '0;
      issue_frame_len       <= 16'h0000;
      done_pulse            <= 1'b0;
      error_overflow        <= 1'b0;
      error_retry_exhausted <= 1'b0;
      for (i = 0; i < MAX_FRAGS; i = i + 1) begin
        retry_cnt[i]   <= 8'h00;
        timeout_cnt[i] <= 32'h0000_0000;
      end
    end else begin
      done_pulse            <= 1'b0;
      error_overflow        <= 1'b0;
      error_retry_exhausted <= 1'b0;

      if (!enable) begin
        pkt_len        <= 16'h0000;
        frag_count     <= 8'h00;
        frag_pending   <= '0;
        frag_inflight  <= '0;
        frag_acked     <= '0;
        wr_ptr         <= 16'h0000;
        active_pkt_seq <= 16'h0000;
        packet_active  <= 1'b0;
        packet_loading <= 1'b0;
        drop_loading   <= 1'b0;
        waiting_final_ack <= 1'b0;
        final_ack_timeout <= 32'h0000_0000;
        issue_valid    <= 1'b0;
        for (i = 0; i < MAX_FRAGS; i = i + 1) begin
          retry_cnt[i]   <= 8'h00;
          timeout_cnt[i] <= 32'h0000_0000;
        end
      end else begin
        if (s_axis_tvalid && s_axis_tready) begin
          if (!packet_loading) begin
            packet_loading <= 1'b1;
            wr_ptr         <= 16'h0000;
            drop_loading   <= 1'b0;
            store_index    = 0;
          end else begin
            store_index    = wr_ptr;
          end

          if (!drop_loading && (store_index < MAX_PACKET_BYTES)) begin
            pkt_buf[store_index] <= s_axis_tdata;
            wr_ptr <= store_index + 1'b1;
          end else begin
            drop_loading   <= 1'b1;
            error_overflow <= 1'b1;
          end

          if (s_axis_tlast) begin
            if (!drop_loading && (store_index < MAX_PACKET_BYTES))
              new_pkt_len = store_index + 1;
            else
              new_pkt_len = store_index;

            packet_loading <= 1'b0;
            wr_ptr         <= 16'h0000;

            if (drop_loading || !(store_index < MAX_PACKET_BYTES) || (new_pkt_len == 0)) begin
              packet_active <= 1'b0;
              drop_loading  <= 1'b0;
            end else begin
              pkt_len        <= new_pkt_len[15:0];
              active_pkt_seq <= seq_counter;
              seq_counter    <= seq_counter + 1'b1;
              new_frag_count = (new_pkt_len + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
              frag_count     <= new_frag_count[7:0];
              frag_pending   <= frag_mask(new_frag_count);
              frag_inflight  <= '0;
              frag_acked     <= '0;
              packet_active  <= 1'b1;
              waiting_final_ack <= 1'b0;
              final_ack_timeout <= 32'h0000_0000;
              issue_valid    <= 1'b0;
              for (i = 0; i < MAX_FRAGS; i = i + 1) begin
                retry_cnt[i]   <= 8'h00;
                timeout_cnt[i] <= 32'h0000_0000;
              end
            end
          end
        end

        if (!issue_valid && build_valid) begin
          issue_valid      <= 1'b1;
          issue_frag_idx   <= build_frag_idx;
          issue_frame_data <= build_frame_data;
          issue_frame_len  <= build_frame_len;
        end

        if (issue_valid && issue_ready) begin
          issue_valid                    <= 1'b0;
          frag_pending[issue_frag_idx]   <= 1'b0;
          frag_inflight[issue_frag_idx]  <= 1'b1;
          timeout_cnt[issue_frag_idx]    <= FRAG_TIMEOUT_CYCLES;
        end

        if (ack_valid && packet_active && (ack_session_id == session_id) && (ack_pkt_seq == active_pkt_seq)) begin
          for (i = 0; i < MAX_FRAGS; i = i + 1) begin
            if ((i < frag_count) && ack_bitmap[i]) begin
              frag_acked[i]    <= 1'b1;
              frag_inflight[i] <= 1'b0;
              frag_pending[i]  <= 1'b0;
              timeout_cnt[i]   <= 32'h0000_0000;
            end
          end
          if ((((frag_acked | ack_bitmap) & valid_mask) == valid_mask) && (frag_count != 0)) begin
            if (ack_complete) begin
              packet_active      <= 1'b0;
              waiting_final_ack  <= 1'b0;
              final_ack_timeout  <= 32'h0000_0000;
              issue_valid        <= 1'b0;
              done_pulse         <= 1'b1;
            end else begin
              waiting_final_ack <= 1'b1;
              final_ack_timeout <= FRAG_TIMEOUT_CYCLES;
            end
          end
        end

        if (packet_active && waiting_final_ack && !issue_valid && !(ack_valid && (ack_session_id == session_id) && (ack_pkt_seq == active_pkt_seq) && ack_complete)) begin
          if (final_ack_timeout != 0) begin
            final_ack_timeout <= final_ack_timeout - 1'b1;
          end else begin
            if (retry_cnt[0] < MAX_RETRY) begin
              retry_cnt[0]    <= retry_cnt[0] + 1'b1;
              frag_acked[0]   <= 1'b0;
              frag_pending[0] <= 1'b1;
              waiting_final_ack <= 1'b0;
              final_ack_timeout <= FRAG_TIMEOUT_CYCLES;
            end else begin
              error_retry_exhausted <= 1'b1;
              packet_active         <= 1'b0;
              waiting_final_ack     <= 1'b0;
              issue_valid           <= 1'b0;
            end
          end
        end

        if (packet_active) begin
          for (i = 0; i < MAX_FRAGS; i = i + 1) begin
            if ((i < frag_count) && frag_inflight[i] && !frag_acked[i] && !(ack_valid && (ack_session_id == session_id) && (ack_pkt_seq == active_pkt_seq) && ack_bitmap[i])) begin
              if (timeout_cnt[i] != 0) begin
                timeout_cnt[i] <= timeout_cnt[i] - 1'b1;
              end else begin
                frag_inflight[i] <= 1'b0;
                if (retry_cnt[i] < MAX_RETRY) begin
                  retry_cnt[i]   <= retry_cnt[i] + 1'b1;
                  frag_pending[i] <= 1'b1;
                end else begin
                  error_retry_exhausted <= 1'b1;
                  packet_active         <= 1'b0;
                  issue_valid           <= 1'b0;
                end
              end
            end
          end
        end
      end
    end
  end
endmodule
