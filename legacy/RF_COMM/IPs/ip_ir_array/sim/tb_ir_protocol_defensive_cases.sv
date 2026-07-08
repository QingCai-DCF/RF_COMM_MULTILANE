`timescale 1ns/1ps

import ir_protocol_pkg::*;

module tb_ir_protocol_defensive_cases;
  localparam int MAX_PACKET_BYTES = 64;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int MAX_FRAME_BYTES  = 64;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;

  logic clk;
  logic rst_n;
  logic enable;

  logic                         rx_in_frame_valid;
  logic                         rx_in_frame_ready;
  logic [8*MAX_FRAME_BYTES-1:0] rx_in_frame_data;
  logic [15:0]                  rx_in_frame_len;
  logic [7:0]                   rx_in_lane_id;
  logic                         rx_ack_update_valid;
  logic [15:0]                  rx_ack_update_session_id;
  logic [15:0]                  rx_ack_update_pkt_seq;
  logic                         rx_ack_update_complete;
  logic [MAX_FRAGS-1:0]         rx_ack_update_bitmap;
  logic                         rx_ack_issue_valid;
  logic                         rx_ack_issue_ready;
  logic [8*MAX_FRAME_BYTES-1:0] rx_ack_issue_frame_data;
  logic [15:0]                  rx_ack_issue_frame_len;
  logic [7:0]                   rx_axis_tdata;
  logic                         rx_axis_tvalid;
  logic                         rx_axis_tready;
  logic                         rx_axis_tlast;
  logic                         rx_ctx_valid;
  logic                         rx_ctx_complete;
  logic                         rx_done_pulse;
  logic                         rx_header_error;
  logic                         rx_protocol_error;
  logic [MAX_FRAGS-1:0]         rx_recv_bitmap_dbg;

  logic [7:0]                   tx_axis_tdata;
  logic                         tx_axis_tvalid;
  logic                         tx_axis_tready;
  logic                         tx_axis_tlast;
  logic                         tx_ack_valid;
  logic [15:0]                  tx_ack_session_id;
  logic [15:0]                  tx_ack_pkt_seq;
  logic                         tx_ack_complete;
  logic [MAX_FRAGS-1:0]         tx_ack_bitmap;
  logic                         tx_issue_valid;
  logic                         tx_issue_ready;
  logic [7:0]                   tx_issue_frag_idx;
  logic [8*MAX_FRAME_BYTES-1:0] tx_issue_frame_data;
  logic [15:0]                  tx_issue_frame_len;
  logic [15:0]                  tx_active_pkt_seq;
  logic                         tx_packet_active;
  logic                         tx_packet_loading;
  logic                         tx_done_pulse;
  logic                         tx_error_overflow;
  logic                         tx_error_retry_exhausted;
  logic [MAX_FRAGS-1:0]         tx_frag_pending_dbg;
  logic [MAX_FRAGS-1:0]         tx_frag_inflight_dbg;
  logic [MAX_FRAGS-1:0]         tx_frag_acked_dbg;

  int rx_byte_count;
  int rx_done_count;
  int rx_header_error_count;
  int rx_protocol_error_count;
  int rx_complete_ack_count;
  int tx_issue_count;
  int tx_done_count;

  always #8 clk = ~clk; // Unit-level protocol clock; not PHY-rate evidence.

  task automatic build_data_frame(
    input  logic [15:0]                  session_id,
    input  logic [15:0]                  pkt_seq,
    input  int                           frag_idx,
    input  int                           frag_count,
    input  int                           total_len,
    input  int                           payload_len,
    input  logic [7:0]                   payload_base,
    output logic [8*MAX_FRAME_BYTES-1:0] frame_data,
    output logic [15:0]                  frame_len
  );
    logic [15:0] crc16_acc;
    begin
      frame_data = '0;
      frame_len  = IRP_DATA_HDR_BYTES + payload_len;
      frame_data[8*0  +: 8] = IRP_SOF;
      frame_data[8*1  +: 8] = {IRP_VERSION, IRP_TYPE_DATA};
      frame_data[8*2  +: 8] = session_id[7:0];
      frame_data[8*3  +: 8] = session_id[15:8];
      frame_data[8*4  +: 8] = pkt_seq[7:0];
      frame_data[8*5  +: 8] = pkt_seq[15:8];
      frame_data[8*6  +: 8] = frag_idx[7:0];
      frame_data[8*7  +: 8] = frag_count[7:0];
      frame_data[8*8  +: 8] = total_len[7:0];
      frame_data[8*9  +: 8] = total_len[15:8];
      frame_data[8*10 +: 8] = payload_len[7:0];
      frame_data[8*11 +: 8] = 8'h00;
      crc16_acc = 16'hFFFF;
      for (int i = 0; i < 12; i++) begin
        crc16_acc = crc16_ccitt_next_byte(frame_data[8*i +: 8], crc16_acc);
      end
      frame_data[8*12 +: 8] = crc16_acc[7:0];
      frame_data[8*13 +: 8] = crc16_acc[15:8];
      for (int i = 0; i < payload_len; i++) begin
        frame_data[8*(IRP_DATA_HDR_BYTES + i) +: 8] =
          payload_base + logic'(frag_idx * FRAGMENT_BYTES + i);
      end
    end
  endtask

  task automatic drive_rx_frame(
    input logic [8*MAX_FRAME_BYTES-1:0] frame_data,
    input logic [15:0]                  frame_len,
    input logic [7:0]                   lane_id
  );
    int wait_cycles;
    begin
      wait_cycles = 0;
      @(negedge clk);
      rx_in_frame_data  = frame_data;
      rx_in_frame_len   = frame_len;
      rx_in_lane_id     = lane_id;
      rx_in_frame_valid = 1'b1;
      while (!rx_in_frame_ready) begin
        @(posedge clk);
        wait_cycles++;
        if (wait_cycles > 2000) begin
          $fatal(1, "Timeout waiting for RX manager input ready lane=%0d", lane_id);
        end
      end
      @(posedge clk);
      @(negedge clk);
      rx_in_frame_valid = 1'b0;
      rx_in_frame_data  = '0;
      rx_in_frame_len   = 16'h0000;
      repeat (6) @(posedge clk);
    end
  endtask

  task automatic wait_rx_done_count(input int expected_count);
    int wait_cycles;
    begin
      wait_cycles = 0;
      while (rx_done_count < expected_count) begin
        @(posedge clk);
        wait_cycles++;
        if (wait_cycles > 20000) begin
          $fatal(1, "Timeout waiting for RX done count=%0d expected=%0d bytes=%0d",
            rx_done_count, expected_count, rx_byte_count);
        end
      end
    end
  endtask

  task automatic send_tx_payload(input int payload_len, input logic [7:0] payload_base);
    int wait_cycles;
    begin
      for (int i = 0; i < payload_len; i++) begin
        wait_cycles = 0;
        @(negedge clk);
        tx_axis_tdata  = payload_base + logic'(i);
        tx_axis_tvalid = 1'b1;
        tx_axis_tlast  = (i == payload_len - 1);
        while (!tx_axis_tready) begin
          @(posedge clk);
          wait_cycles++;
          if (wait_cycles > 2000) begin
            $fatal(1, "Timeout waiting for TX input ready byte=%0d", i);
          end
        end
        @(posedge clk);
      end
      @(negedge clk);
      tx_axis_tvalid = 1'b0;
      tx_axis_tlast  = 1'b0;
      tx_axis_tdata  = 8'h00;
    end
  endtask

  task automatic pulse_tx_ack(
    input logic [15:0]          session_id,
    input logic [15:0]          pkt_seq,
    input logic                 complete,
    input logic [MAX_FRAGS-1:0] bitmap
  );
    begin
      @(negedge clk);
      tx_ack_session_id = session_id;
      tx_ack_pkt_seq    = pkt_seq;
      tx_ack_complete   = complete;
      tx_ack_bitmap     = bitmap;
      tx_ack_valid      = 1'b1;
      @(posedge clk);
      @(negedge clk);
      tx_ack_valid      = 1'b0;
      tx_ack_complete   = 1'b0;
      tx_ack_bitmap     = '0;
      repeat (4) @(posedge clk);
    end
  endtask

  task automatic wait_tx_issue_count(input int expected_count);
    int wait_cycles;
    begin
      wait_cycles = 0;
      while (tx_issue_count < expected_count) begin
        @(posedge clk);
        wait_cycles++;
        if (wait_cycles > 20000) begin
          $fatal(1, "Timeout waiting for TX issue count=%0d expected=%0d pending=%04b inflight=%04b acked=%04b",
            tx_issue_count, expected_count, tx_frag_pending_dbg, tx_frag_inflight_dbg, tx_frag_acked_dbg);
        end
      end
    end
  endtask

  task automatic wait_tx_done_count(input int expected_count);
    int wait_cycles;
    begin
      wait_cycles = 0;
      while (tx_done_count < expected_count) begin
        @(posedge clk);
        wait_cycles++;
        if (wait_cycles > 20000) begin
          $fatal(1, "Timeout waiting for TX done count=%0d expected=%0d active=%0b acked=%04b",
            tx_done_count, expected_count, tx_packet_active, tx_frag_acked_dbg);
        end
      end
    end
  endtask

  always @(posedge clk) begin
    if (!rst_n) begin
      rx_byte_count          <= 0;
      rx_done_count          <= 0;
      rx_header_error_count  <= 0;
      rx_protocol_error_count <= 0;
      rx_complete_ack_count  <= 0;
    end else begin
      if (rx_axis_tvalid && rx_axis_tready) begin
        if (rx_byte_count >= 32) begin
          $fatal(1, "RX manager emitted unexpected extra data byte=%02x count=%0d", rx_axis_tdata, rx_byte_count);
        end
        if (rx_axis_tdata !== (8'h30 + logic'(rx_byte_count))) begin
          $fatal(1, "RX payload mismatch byte=%0d exp=%02x got=%02x",
            rx_byte_count, 8'h30 + logic'(rx_byte_count), rx_axis_tdata);
        end
        rx_byte_count <= rx_byte_count + 1;
      end
      if (rx_done_pulse) begin
        rx_done_count <= rx_done_count + 1;
      end
      if (rx_header_error) begin
        rx_header_error_count <= rx_header_error_count + 1;
      end
      if (rx_protocol_error) begin
        rx_protocol_error_count <= rx_protocol_error_count + 1;
      end
      if (rx_ack_issue_valid && rx_ack_issue_ready &&
          (rx_ack_issue_frame_data[8*1 +: 4] == IRP_TYPE_ACK) &&
          rx_ack_issue_frame_data[8*8]) begin
        rx_complete_ack_count <= rx_complete_ack_count + 1;
      end
    end
  end

  always @(posedge clk) begin
    if (!rst_n) begin
      tx_issue_count <= 0;
      tx_done_count  <= 0;
    end else begin
      if (tx_issue_valid && tx_issue_ready) begin
        tx_issue_count <= tx_issue_count + 1;
      end
      if (tx_done_pulse) begin
        tx_done_count <= tx_done_count + 1;
      end
      if (tx_error_overflow || tx_error_retry_exhausted) begin
        $fatal(1, "Unexpected TX defensive error overflow=%0b retry=%0b",
          tx_error_overflow, tx_error_retry_exhausted);
      end
    end
  end

  ir_array_rx_mgr #(
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_FRAME_BYTES(MAX_FRAME_BYTES),
    .REASSEMBLY_TIMEOUT_CYCLES(2000)
  ) u_rx_mgr (
    .clk(clk),
    .rst_n(rst_n),
    .enable(enable),
    .session_id(16'h55aa),
    .in_frame_valid(rx_in_frame_valid),
    .in_frame_ready(rx_in_frame_ready),
    .in_frame_data(rx_in_frame_data),
    .in_frame_len(rx_in_frame_len),
    .in_lane_id(rx_in_lane_id),
    .ack_update_valid(rx_ack_update_valid),
    .ack_update_session_id(rx_ack_update_session_id),
    .ack_update_pkt_seq(rx_ack_update_pkt_seq),
    .ack_update_complete(rx_ack_update_complete),
    .ack_update_bitmap(rx_ack_update_bitmap),
    .ack_issue_valid(rx_ack_issue_valid),
    .ack_issue_ready(rx_ack_issue_ready),
    .ack_issue_frame_data(rx_ack_issue_frame_data),
    .ack_issue_frame_len(rx_ack_issue_frame_len),
    .m_axis_tdata(rx_axis_tdata),
    .m_axis_tvalid(rx_axis_tvalid),
    .m_axis_tready(rx_axis_tready),
    .m_axis_tlast(rx_axis_tlast),
    .rx_ctx_valid(rx_ctx_valid),
    .rx_ctx_complete(rx_ctx_complete),
    .rx_done_pulse(rx_done_pulse),
    .header_error(rx_header_error),
    .protocol_error(rx_protocol_error),
    .recv_bitmap_dbg(rx_recv_bitmap_dbg)
  );

  ir_array_tx_mgr #(
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_FRAME_BYTES(MAX_FRAME_BYTES),
    .FRAG_TIMEOUT_CYCLES(2000),
    .MAX_INFLIGHT_FRAGS(2)
  ) u_tx_mgr (
    .clk(clk),
    .rst_n(rst_n),
    .enable(enable),
    .session_id(16'h55aa),
    .s_axis_tdata(tx_axis_tdata),
    .s_axis_tvalid(tx_axis_tvalid),
    .s_axis_tready(tx_axis_tready),
    .s_axis_tlast(tx_axis_tlast),
    .ack_valid(tx_ack_valid),
    .ack_session_id(tx_ack_session_id),
    .ack_pkt_seq(tx_ack_pkt_seq),
    .ack_complete(tx_ack_complete),
    .ack_bitmap(tx_ack_bitmap),
    .issue_valid(tx_issue_valid),
    .issue_ready(tx_issue_ready),
    .issue_frag_idx(tx_issue_frag_idx),
    .issue_frame_data(tx_issue_frame_data),
    .issue_frame_len(tx_issue_frame_len),
    .active_pkt_seq(tx_active_pkt_seq),
    .packet_active(tx_packet_active),
    .packet_loading(tx_packet_loading),
    .done_pulse(tx_done_pulse),
    .error_overflow(tx_error_overflow),
    .error_retry_exhausted(tx_error_retry_exhausted),
    .frag_pending_dbg(tx_frag_pending_dbg),
    .frag_inflight_dbg(tx_frag_inflight_dbg),
    .frag_acked_dbg(tx_frag_acked_dbg)
  );

  initial begin
    logic [8*MAX_FRAME_BYTES-1:0] frame0;
    logic [8*MAX_FRAME_BYTES-1:0] frame1;
    logic [8*MAX_FRAME_BYTES-1:0] bad_frame;
    logic [15:0] frame0_len;
    logic [15:0] frame1_len;
    logic [15:0] bad_frame_len;
    logic [15:0] active_seq;

    clk = 1'b0;
    rst_n = 1'b0;
    enable = 1'b0;
    rx_in_frame_valid = 1'b0;
    rx_in_frame_data  = '0;
    rx_in_frame_len   = 16'h0000;
    rx_in_lane_id     = 8'h00;
    rx_ack_issue_ready = 1'b1;
    rx_axis_tready = 1'b1;
    tx_axis_tdata = 8'h00;
    tx_axis_tvalid = 1'b0;
    tx_axis_tlast = 1'b0;
    tx_ack_valid = 1'b0;
    tx_ack_session_id = 16'h0000;
    tx_ack_pkt_seq = 16'h0000;
    tx_ack_complete = 1'b0;
    tx_ack_bitmap = '0;
    tx_issue_ready = 1'b1;

    build_data_frame(16'h55aa, 16'h0101, 0, 2, 32, 16, 8'h30, frame0, frame0_len);
    build_data_frame(16'h55aa, 16'h0101, 1, 2, 32, 16, 8'h30, frame1, frame1_len);
    build_data_frame(16'h55aa, 16'h0102, 1, 2, 32, 16, 8'h30, bad_frame, bad_frame_len);

    repeat (8) @(posedge clk);
    rst_n = 1'b1;
    repeat (8) @(posedge clk);
    enable = 1'b1;
    repeat (4) @(posedge clk);

    drive_rx_frame(frame0, frame0_len, 8'h00);
    drive_rx_frame(frame0, frame0_len, 8'h01);
    drive_rx_frame(frame1, frame1_len, 8'h02);
    wait_rx_done_count(1);
    if (rx_byte_count != 32) begin
      $fatal(1, "RX duplicate suppression byte count mismatch count=%0d", rx_byte_count);
    end
    drive_rx_frame(frame1, frame1_len, 8'h03);
    repeat (100) @(posedge clk);
    if (rx_done_count != 1 || rx_byte_count != 32) begin
      $fatal(1, "Duplicate completed packet was emitted again done=%0d bytes=%0d",
        rx_done_count, rx_byte_count);
    end
    if (rx_complete_ack_count == 0) begin
      $fatal(1, "Duplicate completed packet did not trigger a protective complete ACK");
    end

    drive_rx_frame(frame0, frame0_len, 8'h00);
    drive_rx_frame(bad_frame, bad_frame_len, 8'h01);
    repeat (2100) @(posedge clk);
    if (rx_protocol_error_count == 0) begin
      $fatal(1, "Mismatched in-progress DATA frame did not raise protocol_error");
    end
    if (rx_done_count != 1 || rx_byte_count != 32) begin
      $fatal(1, "Bad in-progress frame caused unexpected delivery done=%0d bytes=%0d",
        rx_done_count, rx_byte_count);
    end

    send_tx_payload(32, 8'h80);
    wait_tx_issue_count(2);
    active_seq = tx_active_pkt_seq;
    pulse_tx_ack(16'h1234, active_seq, 1'b1, 4'b0011);
    if (tx_done_count != 0 || tx_frag_acked_dbg != '0) begin
      $fatal(1, "Wrong-session ACK affected TX state done=%0d acked=%04b",
        tx_done_count, tx_frag_acked_dbg);
    end
    pulse_tx_ack(16'h55aa, active_seq - 16'h0001, 1'b1, 4'b0011);
    if (tx_done_count != 0 || tx_frag_acked_dbg != '0) begin
      $fatal(1, "Stale ACK affected TX state done=%0d acked=%04b",
        tx_done_count, tx_frag_acked_dbg);
    end
    pulse_tx_ack(16'h55aa, active_seq, 1'b0, 4'b0001);
    if (tx_done_count != 0 || !tx_packet_active || tx_frag_acked_dbg[0] != 1'b1) begin
      $fatal(1, "Valid partial ACK did not produce expected partial state done=%0d active=%0b acked=%04b",
        tx_done_count, tx_packet_active, tx_frag_acked_dbg);
    end
    pulse_tx_ack(16'h55aa, active_seq, 1'b1, 4'b0011);
    wait_tx_done_count(1);

    $display(
      "IR_PROTOCOL_DEFENSIVE_CASES_PASS rx_bytes=%0d rx_done=%0d protocol_errors=%0d complete_acks=%0d tx_issues=%0d tx_done=%0d",
      rx_byte_count, rx_done_count, rx_protocol_error_count, rx_complete_ack_count,
      tx_issue_count, tx_done_count);
    $finish;
  end
endmodule
