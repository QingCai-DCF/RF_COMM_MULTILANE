`timescale 1ns/1ps

module tb_p6_dynamic_transport_engine;
  logic clk = 1'b0;
  always #5 clk = ~clk;

  logic rst_n;
  logic reset_pulse;
  logic clear_pulse;
  logic start_pulse;
  logic stop_pulse;
  logic shutdown_pulse;
  logic enable_phy;
  logic [15:0] cfg_session;
  logic [7:0] cfg_lane_mask;
  logic [7:0] cfg_ack_lane_mask;
  logic [15:0] cfg_payload_len;
  logic [31:0] cfg_timeout_cycles;
  logic [8*256-1:0] tx_payload_flat;
  logic [31:0] tx_payload_crc32;
  logic [7:0] tx_payload_read_index;
  logic [7:0] tx_payload_read_data;
  logic [7:0] compare_payload_read_index;
  logic [7:0] compare_payload_read_data;
  logic [1:0] a_rxd;
  logic [1:0] a_txd;
  logic [1:0] a_sd;
  logic [1:0] a_mode;
  logic [1:0] b_rxd;
  logic [1:0] b_txd;
  logic [1:0] b_sd;
  logic [1:0] b_mode;
  logic ready;
  logic busy;
  logic done_pulse;
  logic fail_pulse;
  logic timeout_pulse;
  logic [31:0] error_code;
  logic rx_byte_write_pulse;
  logic [7:0] rx_byte_write_index;
  logic [7:0] rx_byte_write_data;
  logic [8*256-1:0] observed_rx_payload;
  logic [15:0] rx_payload_len;
  logic [31:0] rx_payload_crc32;
  logic [31:0] rx_digest;
  logic [1:0] rx_good_mask;
  logic [31:0] crc_bad_count;
  logic [31:0] payload_mismatch_count;
  logic [31:0] retry_count;
  logic [31:0] retry_exhausted_count;
  logic [31:0] tx_fail_count;
  logic [31:0] txd_high_max;
  logic [31:0] duty_violation_count;
  logic [31:0] shutdown_reason;
  logic [31:0] tx_pulse_count;
  logic [31:0] rx_raw_count;
  logic [31:0] frame_good_count;
  logic [31:0] frame_bad_count;
  logic [31:0] ack_sent_count;
  logic [31:0] ack_seen_count;
  logic [31:0] debug_status;

  // Ideal optical coupling: a positive Txd optical pulse produces a low Rxd
  // pulse at the opposite endpoint on the same physical lane.
  assign b_rxd = ~a_txd;
  assign a_rxd = ~b_txd;
  assign tx_payload_read_data = tx_payload_flat[8*tx_payload_read_index +: 8];
  assign compare_payload_read_data = tx_payload_flat[8*compare_payload_read_index +: 8];

  p6_dynamic_transport_engine #(
    .CLK_HZ(1_000_000),
    .STARTUP_US(1),
    .CHIP_CYCLES(8),
    .TX_PULSE_CYCLES(2),
    .PREAMBLE_SYMBOLS(4),
    .TURNAROUND_CYCLES(8),
    .MAX_RETRY(2)
  ) dut (
    .clk, .rst_n, .reset_pulse, .clear_pulse, .start_pulse, .stop_pulse,
    .shutdown_pulse, .enable_phy, .cfg_session, .cfg_lane_mask,
    .cfg_ack_lane_mask, .cfg_payload_len, .cfg_timeout_cycles,
    .tx_payload_read_index, .tx_payload_read_data,
    .compare_payload_read_index, .compare_payload_read_data, .tx_payload_crc32,
    .a_rxd, .a_txd, .a_sd, .a_mode, .b_rxd, .b_txd, .b_sd, .b_mode,
    .ready, .busy, .done_pulse, .fail_pulse, .timeout_pulse, .error_code,
    .rx_byte_write_pulse, .rx_byte_write_index, .rx_byte_write_data,
    .rx_payload_len, .rx_payload_crc32, .rx_digest,
    .rx_good_mask, .crc_bad_count, .payload_mismatch_count, .retry_count,
    .retry_exhausted_count, .tx_fail_count, .txd_high_max,
    .duty_violation_count, .shutdown_reason, .tx_pulse_count, .rx_raw_count,
    .frame_good_count, .frame_bad_count, .ack_sent_count, .ack_seen_count,
    .debug_status
  );

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) observed_rx_payload <= '0;
    else if (clear_pulse) observed_rx_payload <= '0;
    else if (rx_byte_write_pulse) observed_rx_payload[8*rx_byte_write_index +: 8] <= rx_byte_write_data;
  end

  task automatic tick(input int count);
    repeat (count) begin
      @(posedge clk);
      #1;
    end
  endtask

  task automatic check_expect(input bit condition, input string message);
    if (!condition) begin
      $error("EXPECT_FAIL: %s", message);
      $finish;
    end
  endtask

  function automatic logic [31:0] crc32_next_byte(
    input logic [7:0] data,
    input logic [31:0] crc_in
  );
    logic [31:0] c;
    begin
      c = crc_in;
      for (int bit_idx = 0; bit_idx < 8; bit_idx++) begin
        c = (c[0] ^ data[bit_idx]) ? ((c >> 1) ^ 32'hEDB8_8320) : (c >> 1);
      end
      crc32_next_byte = c;
    end
  endfunction

  function automatic logic [7:0] pattern_byte(input int pattern_id, input int byte_idx);
    logic [6:0] prbs7;
    logic [14:0] prbs15;
    logic [31:0] random_state;
    logic [7:0] out_byte;
    logic feedback;
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
              feedback = prbs7[6] ^ prbs7[5];
              prbs7 = {prbs7[5:0], feedback};
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
              feedback = prbs15[14] ^ prbs15[13];
              prbs15 = {prbs15[13:0], feedback};
              out_byte[bit_idx] = prbs15[0];
            end
          end
          pattern_byte = out_byte;
        end
        default: begin
          random_state = 32'h0000_2201;
          out_byte = 8'h00;
          for (int idx = 0; idx <= byte_idx; idx++) begin
            random_state = (32'd1664525 * random_state) + 32'd1013904223;
            out_byte = random_state[31:24];
          end
          pattern_byte = out_byte;
        end
      endcase
    end
  endfunction

  task automatic load_payload(input int length, input int pattern_id);
    logic [31:0] crc_value;
    begin
      tx_payload_flat = '0;
      crc_value = 32'hFFFF_FFFF;
      for (int idx = 0; idx < 247; idx++) begin
        if (idx < length) begin
          tx_payload_flat[8*idx +: 8] = pattern_byte(pattern_id, idx);
          crc_value = crc32_next_byte(pattern_byte(pattern_id, idx), crc_value);
        end
      end
      tx_payload_crc32 = ~crc_value;
    end
  endtask

  task automatic run_case(input int length, input int pattern_id, input int lane_mask);
    bit completed;
    begin
      clear_pulse = 1'b1;
      tick(1);
      clear_pulse = 1'b0;
      cfg_session = 16'h2201;
      cfg_lane_mask = lane_mask[7:0];
      cfg_ack_lane_mask = lane_mask[7:0];
      cfg_payload_len = length[15:0];
      cfg_timeout_cycles = 32'd200_000;
      load_payload(length, pattern_id);
      start_pulse = 1'b1;
      tick(1);
      start_pulse = 1'b0;
      completed = 1'b0;
      for (int cycles = 0; cycles < 500_000; cycles++) begin
        tick(1);
        if (fail_pulse || timeout_pulse) begin
          $error("ENGINE_FAIL len=%0d pattern=%0d mask=0x%0x error=0x%08x", length, pattern_id, lane_mask, error_code);
          $finish;
        end
        if (done_pulse) begin
          completed = 1'b1;
          break;
        end
      end
      check_expect(completed, "dynamic physical transfer completed within bound");
      check_expect(rx_payload_len == length, "RX payload length matches");
      check_expect(rx_payload_crc32 == tx_payload_crc32, "RX CRC matches committed TX CRC");
      check_expect(rx_digest == tx_payload_crc32, "RX digest matches committed TX CRC");
      check_expect((rx_good_mask & lane_mask[1:0]) == lane_mask[1:0], "selected lanes report good RX");
      check_expect(crc_bad_count == 0, "CRC_BAD remains zero");
      check_expect(payload_mismatch_count == 0, "PAYLOAD_MISMATCH remains zero");
      check_expect(retry_exhausted_count == 0, "retry exhausted remains zero");
      check_expect(tx_fail_count == 0, "TX fail remains zero");
      check_expect(duty_violation_count == 0, "duty violation remains zero");
      for (int idx = 0; idx < length; idx++) begin
        check_expect(observed_rx_payload[8*idx +: 8] == pattern_byte(pattern_id, idx), "RX payload byte matches");
      end
    end
  endtask

  int lengths [16] = '{1, 2, 3, 4, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 191, 247};
  int lane_masks [3] = '{1, 2, 3};
  int positive_count;

  initial begin
    rst_n = 1'b0;
    reset_pulse = 1'b0;
    clear_pulse = 1'b0;
    start_pulse = 1'b0;
    stop_pulse = 1'b0;
    shutdown_pulse = 1'b0;
    enable_phy = 1'b1;
    cfg_session = 16'h2201;
    cfg_lane_mask = 8'h01;
    cfg_ack_lane_mask = 8'h01;
    cfg_payload_len = 16'd1;
    cfg_timeout_cycles = 32'd200_000;
    tx_payload_flat = '0;
    tx_payload_crc32 = 32'd0;
    positive_count = 0;
    tick(5);
    rst_n = 1'b1;
    tick(5);

    for (int length_idx = 0; length_idx < 16; length_idx++) begin
      for (int pattern_id = 0; pattern_id < 10; pattern_id++) begin
        for (int mask_idx = 0; mask_idx < 3; mask_idx++) begin
          run_case(lengths[length_idx], pattern_id, lane_masks[mask_idx]);
          positive_count++;
        end
      end
    end

    shutdown_pulse = 1'b1;
    tick(1);
    shutdown_pulse = 1'b0;
    enable_phy = 1'b0;
    tick(4);
    check_expect(a_sd == 2'b11 && b_sd == 2'b11, "shutdown asserts all TFDU SD pins");
    check_expect(a_txd == 2'b00 && b_txd == 2'b00, "shutdown holds all TFDU Txd pins low");
    $display("TB_P6_DYNAMIC_ENGINE_POSITIVE_CASES=%0d", positive_count);
    $display("TB_P6_DYNAMIC_ENGINE_PASS=1");
    $finish;
  end
endmodule
