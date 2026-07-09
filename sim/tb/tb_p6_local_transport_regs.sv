`timescale 1ns/1ps

module tb_p6_local_transport_regs;
  logic clk = 1'b0;
  always #5 clk = ~clk;

  logic rst_n;
  logic wr_en;
  logic [11:0] wr_addr;
  logic [31:0] wr_data;
  logic rd_en;
  logic [11:0] rd_addr;
  logic [31:0] rd_data;
  logic rd_valid;

  localparam logic [11:0] REG_CONTROL = 12'h000;
  localparam logic [11:0] REG_P6_CTRL = 12'h100;
  localparam logic [11:0] REG_P6_STATUS = 12'h104;
  localparam logic [11:0] REG_P6_SESSION = 12'h108;
  localparam logic [11:0] REG_P6_LANE_MASK = 12'h10C;
  localparam logic [11:0] REG_P6_ACK_LANE_MASK = 12'h110;
  localparam logic [11:0] REG_P6_PAYLOAD_LEN = 12'h114;
  localparam logic [11:0] REG_P6_PAYLOAD_PATTERN_ID = 12'h118;
  localparam logic [11:0] REG_P6_PAYLOAD_SEED = 12'h11C;
  localparam logic [11:0] REG_P6_PAYLOAD_CRC32 = 12'h120;
  localparam logic [11:0] REG_P6_RX_PAYLOAD_CRC32 = 12'h124;
  localparam logic [11:0] REG_P6_RX_PAYLOAD_LEN = 12'h128;
  localparam logic [11:0] REG_P6_TX_COUNT = 12'h12C;
  localparam logic [11:0] REG_P6_RX_GOOD_COUNT_L0 = 12'h130;
  localparam logic [11:0] REG_P6_RX_GOOD_COUNT_L1 = 12'h134;
  localparam logic [11:0] REG_P6_CRC_BAD = 12'h138;
  localparam logic [11:0] REG_P6_PAYLOAD_MISMATCH = 12'h13C;
  localparam logic [11:0] REG_P6_RETRY_EXHAUSTED = 12'h144;
  localparam logic [11:0] REG_P6_TX_FAIL = 12'h148;
  localparam logic [11:0] REG_P6_ERROR_CODE = 12'h160;
  localparam logic [11:0] REG_P6_STICKY_ERROR = 12'h164;
  localparam logic [11:0] REG_P6_RX_DIGEST = 12'h168;
  localparam logic [11:0] REG_P6_PAYLOAD_WORD_INDEX = 12'h16C;
  localparam logic [11:0] REG_P6_PAYLOAD_WORD_DATA = 12'h170;
  localparam logic [11:0] REG_P6_RX_WORD_INDEX = 12'h174;
  localparam logic [11:0] REG_P6_RX_WORD_DATA = 12'h178;
  localparam logic [11:0] REG_P6_CAPS = 12'h17C;

  localparam logic [31:0] P6_ERROR_SESSION = 32'h0000_0001;
  localparam logic [31:0] P6_ERROR_LANE_MASK = 32'h0000_0002;
  localparam logic [31:0] P6_ERROR_ACK_MASK = 32'h0000_0003;

  ir_axi_regs_new dut (
    .clk(clk),
    .rst_n(rst_n),
    .wr_en(wr_en),
    .wr_addr(wr_addr),
    .wr_data(wr_data),
    .rd_en(rd_en),
    .rd_addr(rd_addr),
    .rd_data(rd_data),
    .rd_valid(rd_valid),
    .core_reset_pulse(),
    .enable_phy(),
    .start_pulse(),
    .stop_pulse(),
    .clear_sticky_pulse(),
    .commit_pulse(),
    .profile_committed(),
    .cfg_payload_lane_mask(),
    .cfg_rx_lane_mask(),
    .cfg_ack_lane_mask(),
    .cfg_session(),
    .cfg_payload_len(),
    .cfg_fragment_bytes(),
    .cfg_cnt_chip_max(),
    .cfg_cnt_preamble(),
    .cfg_detect_start(),
    .cfg_detect_end(),
    .cfg_guard_cycles(),
    .cfg_retry_timeout(),
    .cfg_startup_us(),
    .cfg_duty_window(),
    .cfg_duty_max_permille(),
    .cfg_stuck_high_limit_us(),
    .status_phy_ready(1'b1),
    .status_busy(1'b0),
    .status_tx_done(1'b0),
    .status_rx_done(1'b0),
    .status_tx_fail(1'b0),
    .status_retry_count(8'd0),
    .status_crc_bad_count(8'd0),
    .status_session_bad_count(8'd0),
    .status_mask_bad_count(8'd0),
    .safety_shutdown_reason(32'd0),
    .counter_tx_pulse(32'd0),
    .counter_rx_raw_pulse(32'd0),
    .counter_frame_good(32'd0),
    .counter_frame_bad(32'd0),
    .counter_ack_sent(32'd0),
    .counter_ack_seen(32'd0),
    .commit_count(),
    .debug_status()
  );

  task automatic check_expect(input bit cond, input string msg);
    if (!cond) begin
      $error("EXPECT_FAIL: %s", msg);
      $finish;
    end
  endtask

  task automatic tick(input int n);
    repeat (n) begin
      @(posedge clk);
      #1;
    end
  endtask

  task automatic write_reg(input logic [11:0] addr, input logic [31:0] data);
    begin
      wr_addr <= addr;
      wr_data <= data;
      wr_en <= 1'b1;
      tick(1);
      wr_en <= 1'b0;
      tick(1);
    end
  endtask

  task automatic read_reg(input logic [11:0] addr, output logic [31:0] data);
    begin
      rd_addr <= addr;
      rd_en <= 1'b1;
      tick(1);
      rd_en <= 1'b0;
      data = rd_data;
      check_expect(rd_valid, "read valid asserted");
      tick(1);
    end
  endtask

  function automatic logic [31:0] crc32_next_byte(input logic [7:0] data, input logic [31:0] crc_in);
    logic [31:0] c;
    begin
      c = crc_in;
      for (int bit_idx = 0; bit_idx < 8; bit_idx++) begin
        if ((c[0] ^ data[bit_idx]) != 1'b0) begin
          c = (c >> 1) ^ 32'hEDB8_8320;
        end else begin
          c = c >> 1;
        end
      end
      crc32_next_byte = c;
    end
  endfunction

  function automatic logic [7:0] pattern_byte(input int pattern_id, input int byte_idx);
    logic [6:0] prbs7;
    logic [14:0] prbs15;
    logic [31:0] rand_state;
    logic [7:0] out_byte;
    logic new_bit;
    begin
      unique case (pattern_id)
        0: pattern_byte = 8'h00;
        1: pattern_byte = 8'hFF;
        2: pattern_byte = 8'hAA;
        3: pattern_byte = 8'h55;
        4: pattern_byte = byte_idx[7:0];
        5: pattern_byte = 8'h01 << (byte_idx % 8);
        6: pattern_byte = ~(8'h01 << (byte_idx % 8));
        7: begin
          prbs7 = 7'h5A;
          out_byte = 8'h00;
          for (int idx = 0; idx <= byte_idx; idx++) begin
            out_byte = 8'h00;
            for (int bit_idx = 0; bit_idx < 8; bit_idx++) begin
              new_bit = prbs7[6] ^ prbs7[5];
              prbs7 = {prbs7[5:0], new_bit};
              out_byte[bit_idx] = prbs7[0];
            end
          end
          pattern_byte = out_byte;
        end
        8: begin
          prbs15 = 15'h4A5A;
          out_byte = 8'h00;
          for (int idx = 0; idx <= byte_idx; idx++) begin
            out_byte = 8'h00;
            for (int bit_idx = 0; bit_idx < 8; bit_idx++) begin
              new_bit = prbs15[14] ^ prbs15[13];
              prbs15 = {prbs15[13:0], new_bit};
              out_byte[bit_idx] = prbs15[0];
            end
          end
          pattern_byte = out_byte;
        end
        default: begin
          rand_state = 32'h0000_2201;
          out_byte = 8'h00;
          for (int idx = 0; idx <= byte_idx; idx++) begin
            rand_state = (32'd1664525 * rand_state) + 32'd1013904223;
            out_byte = rand_state[31:24];
          end
          pattern_byte = out_byte;
        end
      endcase
    end
  endfunction

  function automatic logic [31:0] expected_crc(input int length, input int pattern_id);
    logic [31:0] c;
    begin
      c = 32'hFFFF_FFFF;
      for (int byte_idx = 0; byte_idx < 247; byte_idx++) begin
        if (byte_idx < length) begin
          c = crc32_next_byte(pattern_byte(pattern_id, byte_idx), c);
        end
      end
      expected_crc = ~c;
    end
  endfunction

  function automatic logic [31:0] expected_word(input int word_idx, input int length, input int pattern_id);
    logic [31:0] word;
    int byte_index;
    begin
      word = 32'h0000_0000;
      for (int lane = 0; lane < 4; lane++) begin
        byte_index = word_idx * 4 + lane;
        if (byte_index < length) begin
          word[8*lane +: 8] = pattern_byte(pattern_id, byte_index);
        end
      end
      expected_word = word;
    end
  endfunction

  task automatic write_payload(input int length, input int pattern_id);
    int word_count;
    begin
      word_count = (length + 3) / 4;
      for (int word_idx = 0; word_idx < word_count; word_idx++) begin
        write_reg(REG_P6_PAYLOAD_WORD_INDEX, word_idx[31:0]);
        write_reg(REG_P6_PAYLOAD_WORD_DATA, expected_word(word_idx, length, pattern_id));
      end
    end
  endtask

  task automatic positive_case(input int length, input int pattern_id, input int lane_mask);
    logic [31:0] value;
    logic [31:0] tx_before;
    logic [31:0] l0_before;
    logic [31:0] l1_before;
    logic [31:0] crc_expected;
    int word_count;
    begin
      crc_expected = expected_crc(length, pattern_id);
      read_reg(REG_P6_TX_COUNT, tx_before);
      read_reg(REG_P6_RX_GOOD_COUNT_L0, l0_before);
      read_reg(REG_P6_RX_GOOD_COUNT_L1, l1_before);
      write_reg(REG_P6_CTRL, 32'h0000_0002);
      write_reg(REG_P6_SESSION, 32'h0000_2201);
      write_reg(REG_P6_LANE_MASK, lane_mask[31:0]);
      write_reg(REG_P6_ACK_LANE_MASK, lane_mask[31:0]);
      write_reg(REG_P6_PAYLOAD_LEN, length[31:0]);
      write_reg(REG_P6_PAYLOAD_PATTERN_ID, pattern_id[31:0]);
      write_reg(REG_P6_PAYLOAD_SEED, 32'h0000_2201);
      write_payload(length, pattern_id);
      write_reg(REG_P6_CTRL, 32'h0000_0004);
      read_reg(REG_P6_STATUS, value);
      check_expect(value[2], "P6 commit status set");
      check_expect(!value[5] && !value[6] && !value[7], "P6 commit status has no fail bits");
      read_reg(REG_P6_PAYLOAD_LEN, value);
      check_expect(value[15:0] == length[15:0], "P6 payload_len readback");
      read_reg(REG_P6_LANE_MASK, value);
      check_expect(value[7:0] == lane_mask[7:0], "P6 lane_mask readback");
      read_reg(REG_P6_ACK_LANE_MASK, value);
      check_expect(value[7:0] == lane_mask[7:0], "P6 ack_mask readback");
      read_reg(REG_P6_PAYLOAD_CRC32, value);
      check_expect(value == crc_expected, "P6 payload CRC readback");
      write_reg(REG_P6_CTRL, 32'h0000_0008);
      read_reg(REG_P6_STATUS, value);
      check_expect(value[4], "P6 start done set");
      check_expect(!value[5] && !value[6] && !value[7], "P6 start has no fail bits");
      read_reg(REG_P6_TX_COUNT, value);
      check_expect(value == tx_before + 1, "P6 tx count increments");
      read_reg(REG_P6_RX_PAYLOAD_LEN, value);
      check_expect(value[15:0] == length[15:0], "P6 rx payload len readback");
      read_reg(REG_P6_RX_PAYLOAD_CRC32, value);
      check_expect(value == crc_expected, "P6 rx CRC readback");
      read_reg(REG_P6_RX_DIGEST, value);
      check_expect(value == crc_expected, "P6 rx digest readback");
      read_reg(REG_P6_CRC_BAD, value);
      check_expect(value == 32'd0, "P6 crc bad remains zero");
      read_reg(REG_P6_PAYLOAD_MISMATCH, value);
      check_expect(value == 32'd0, "P6 payload mismatch remains zero");
      read_reg(REG_P6_RETRY_EXHAUSTED, value);
      check_expect(value == 32'd0, "P6 retry exhausted remains zero");
      read_reg(REG_P6_TX_FAIL, value);
      check_expect(value == 32'd0, "P6 tx fail remains zero");
      if ((lane_mask & 1) != 0) begin
        read_reg(REG_P6_RX_GOOD_COUNT_L0, value);
        check_expect(value == l0_before + 1, "P6 lane0 rx good increments");
      end
      if ((lane_mask & 2) != 0) begin
        read_reg(REG_P6_RX_GOOD_COUNT_L1, value);
        check_expect(value == l1_before + 1, "P6 lane1 rx good increments");
      end
      word_count = (length + 3) / 4;
      for (int word_idx = 0; word_idx < word_count; word_idx++) begin
        write_reg(REG_P6_RX_WORD_INDEX, word_idx[31:0]);
        read_reg(REG_P6_RX_WORD_DATA, value);
        check_expect(value == expected_word(word_idx, length, pattern_id), "P6 rx payload word readback");
      end
    end
  endtask

  task automatic negative_case(
    input logic [31:0] session_value,
    input int lane_mask,
    input int ack_mask,
    input logic [31:0] expected_error
  );
    logic [31:0] value;
    logic [31:0] tx_before;
    begin
      read_reg(REG_P6_TX_COUNT, tx_before);
      write_reg(REG_P6_CTRL, 32'h0000_0002);
      write_reg(REG_P6_SESSION, session_value);
      write_reg(REG_P6_LANE_MASK, lane_mask[31:0]);
      write_reg(REG_P6_ACK_LANE_MASK, ack_mask[31:0]);
      write_reg(REG_P6_PAYLOAD_LEN, 32'd16);
      write_payload(16, 4);
      write_reg(REG_P6_CTRL, 32'h0000_0004);
      read_reg(REG_P6_STATUS, value);
      check_expect(value[5] && value[6], "P6 negative case fail/config rejected");
      read_reg(REG_P6_ERROR_CODE, value);
      check_expect(value == expected_error, "P6 negative error code");
      read_reg(REG_P6_STICKY_ERROR, value);
      check_expect(value != 32'd0, "P6 sticky error set");
      write_reg(REG_P6_CTRL, 32'h0000_0008);
      read_reg(REG_P6_TX_COUNT, value);
      check_expect(value == tx_before, "P6 negative did not increment tx count");
      write_reg(REG_P6_CTRL, 32'h0000_0002);
      read_reg(REG_P6_STICKY_ERROR, value);
      check_expect(value == 32'd0, "P6 sticky error clear");
    end
  endtask

  int lengths [16] = '{1, 2, 3, 4, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 191, 247};
  int lane_masks [3] = '{1, 2, 3};
  logic [31:0] value;
  int positive_count;

  initial begin
    rst_n = 1'b0;
    wr_en = 1'b0;
    wr_addr = 12'd0;
    wr_data = 32'd0;
    rd_en = 1'b0;
    rd_addr = 12'd0;
    positive_count = 0;
    tick(3);
    rst_n = 1'b1;
    tick(2);

    write_reg(REG_CONTROL, 32'h0000_0002);
    read_reg(REG_P6_CAPS, value);
    check_expect(value[15:0] == 16'd247, "P6 caps expose 247-byte payload");
    check_expect(value[23:16] == 8'h03, "P6 caps expose max lane mask 0x3");

    for (int length_idx = 0; length_idx < 16; length_idx++) begin
      for (int pattern_id = 0; pattern_id < 10; pattern_id++) begin
        for (int mask_idx = 0; mask_idx < 3; mask_idx++) begin
          positive_case(lengths[length_idx], pattern_id, lane_masks[mask_idx]);
          positive_count++;
        end
      end
    end

    negative_case(32'h0000_2202, 1, 1, P6_ERROR_SESSION);
    negative_case(32'h0000_2201, 1, 2, P6_ERROR_ACK_MASK);
    negative_case(32'h0000_2201, 4, 4, P6_ERROR_LANE_MASK);

    $display("TB_P6_LOCAL_TRANSPORT_POSITIVE_CASES=%0d", positive_count);
    $display("TB_P6_LOCAL_TRANSPORT_NEGATIVE_CASES=3");
    $display("TB_P6_LOCAL_TRANSPORT_REGS_PASS=1");
    $finish;
  end
endmodule
