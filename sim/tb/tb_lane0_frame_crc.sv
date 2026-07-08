`timescale 1ns/1ps
module tb_lane0_frame_crc;
  localparam int MAX_FRAME_BYTES = 64;
  localparam int HDR_BYTES = 14;

  logic clk = 1'b0;
  always #5 clk = ~clk;

  logic rst_n;
  logic clear_counters;
  logic validate;
  logic [8*MAX_FRAME_BYTES-1:0] frame_data;
  logic [15:0] frame_len;
  logic [15:0] expected_session;
  logic [7:0] expected_lane_mask;
  logic validate_ready;
  logic frame_good_pulse;
  logic frame_bad_pulse;
  logic crc_bad_pulse;
  logic session_bad_pulse;
  logic lane_mask_bad_pulse;
  logic payload_len_bad_pulse;
  logic [31:0] frame_good_count;
  logic [31:0] frame_bad_count;
  logic [31:0] crc_bad_count;
  logic [31:0] session_bad_count;
  logic [31:0] lane_mask_bad_count;
  logic [31:0] payload_len_bad_count;
  logic [31:0] debug_status;

  ir_frame_l1 #(
    .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
  ) dut (
    .clk(clk),
    .rst_n(rst_n),
    .clear_counters(clear_counters),
    .validate(validate),
    .frame_data(frame_data),
    .frame_len(frame_len),
    .expected_session(expected_session),
    .expected_lane_mask(expected_lane_mask),
    .validate_ready(validate_ready),
    .frame_good_pulse(frame_good_pulse),
    .frame_bad_pulse(frame_bad_pulse),
    .crc_bad_pulse(crc_bad_pulse),
    .session_bad_pulse(session_bad_pulse),
    .lane_mask_bad_pulse(lane_mask_bad_pulse),
    .payload_len_bad_pulse(payload_len_bad_pulse),
    .frame_good_count(frame_good_count),
    .frame_bad_count(frame_bad_count),
    .crc_bad_count(crc_bad_count),
    .session_bad_count(session_bad_count),
    .lane_mask_bad_count(lane_mask_bad_count),
    .payload_len_bad_count(payload_len_bad_count),
    .debug_status(debug_status)
  );

  task automatic expect(input bit cond, input string msg);
    if (!cond) begin
      $error("EXPECT_FAIL: %s", msg);
      $finish;
    end
  endtask

  task automatic tick(input int n);
    repeat (n) @(posedge clk);
  endtask

  function automatic logic [7:0] get_byte(input int idx);
    begin
      get_byte = frame_data[8*idx +: 8];
    end
  endfunction

  task automatic set_byte(input int idx, input logic [7:0] value);
    begin
      frame_data[8*idx +: 8] = value;
    end
  endtask

  function automatic logic [15:0] crc16_next(input logic [7:0] data, input logic [15:0] crc_in);
    logic [15:0] c;
    logic [7:0] d;
    int i;
    begin
      c = crc_in;
      d = data;
      for (i = 0; i < 8; i++) begin
        if (c[15] ^ d[7]) c = {c[14:0], 1'b0} ^ 16'h1021;
        else c = {c[14:0], 1'b0};
        d = {d[6:0], 1'b0};
      end
      crc16_next = c;
    end
  endfunction

  function automatic logic [31:0] crc32_next(input logic [7:0] data, input logic [31:0] crc_in);
    logic [31:0] c;
    int i;
    begin
      c = crc_in ^ {24'h0, data};
      for (i = 0; i < 8; i++) begin
        if (c[0]) c = (c >> 1) ^ 32'hEDB88320;
        else c = (c >> 1);
      end
      crc32_next = c;
    end
  endfunction

  task automatic make_frame(input logic [15:0] session, input logic [7:0] lane_mask, input logic [7:0] payload_len);
    logic [15:0] hcrc;
    logic [31:0] pcrc;
    logic [7:0] payload_byte;
    int i;
    begin
      frame_data = '0;
      frame_len = HDR_BYTES + payload_len + 4;
      set_byte(0, 8'hA5);
      set_byte(1, 8'h11);
      set_byte(2, session[7:0]);
      set_byte(3, session[15:8]);
      set_byte(4, 8'h34);
      set_byte(5, 8'h12);
      set_byte(6, 8'h00);
      set_byte(7, 8'h01);
      set_byte(8, payload_len);
      set_byte(9, 8'h00);
      set_byte(10, payload_len);
      set_byte(11, lane_mask);
      hcrc = 16'hFFFF;
      for (i = 0; i < 12; i++) hcrc = crc16_next(get_byte(i), hcrc);
      set_byte(12, hcrc[7:0]);
      set_byte(13, hcrc[15:8]);
      pcrc = 32'hFFFF_FFFF;
      for (i = 0; i < payload_len; i++) begin
        payload_byte = 8'h40 + i;
        set_byte(HDR_BYTES + i, payload_byte);
        pcrc = crc32_next(payload_byte, pcrc);
      end
      pcrc = ~pcrc;
      set_byte(HDR_BYTES + payload_len + 0, pcrc[7:0]);
      set_byte(HDR_BYTES + payload_len + 1, pcrc[15:8]);
      set_byte(HDR_BYTES + payload_len + 2, pcrc[23:16]);
      set_byte(HDR_BYTES + payload_len + 3, pcrc[31:24]);
    end
  endtask

  task automatic run_validate;
    begin
      expect(validate_ready, "frame validator ready");
      validate <= 1'b1;
      tick(1);
      validate <= 1'b0;
      tick(1);
    end
  endtask

  initial begin
    rst_n = 1'b0;
    clear_counters = 1'b0;
    validate = 1'b0;
    frame_data = '0;
    frame_len = 16'd0;
    expected_session = 16'h2201;
    expected_lane_mask = 8'h01;
    tick(3);

    rst_n = 1'b1;
    tick(2);

    make_frame(16'h2201, 8'h01, 8'd8);
    run_validate();
    expect(frame_good_count == 32'd1, "valid frame increments good count");
    expect(frame_bad_count == 32'd0, "valid frame has no bad count");

    make_frame(16'h2201, 8'h01, 8'd8);
    set_byte(HDR_BYTES + 8 + 0, get_byte(HDR_BYTES + 8 + 0) ^ 8'h01);
    run_validate();
    expect(crc_bad_count == 32'd1, "CRC bad increments crc counter");

    make_frame(16'h2202, 8'h01, 8'd8);
    run_validate();
    expect(session_bad_count == 32'd1, "session mismatch increments session counter");

    make_frame(16'h2201, 8'h02, 8'd8);
    run_validate();
    expect(lane_mask_bad_count == 32'd1, "lane mask mismatch increments lane counter");

    make_frame(16'h2201, 8'h01, 8'd8);
    frame_len = frame_len - 1'b1;
    run_validate();
    expect(payload_len_bad_count == 32'd1, "payload length mismatch increments length counter");

    $display("TB_LANE0_FRAME_CRC_PASS=1");
    $finish;
  end
endmodule
