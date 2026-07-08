`timescale 1ns/1ps
module ir_frame_l1 #(
  parameter int MAX_FRAME_BYTES = 512
) (
  input  logic                         clk,
  input  logic                         rst_n,
  input  logic                         clear_counters,
  input  logic                         validate,
  input  logic [8*MAX_FRAME_BYTES-1:0] frame_data,
  input  logic [15:0]                  frame_len,
  input  logic [15:0]                  expected_session,
  input  logic [7:0]                   expected_lane_mask,
  output logic                         validate_ready,
  output logic                         frame_good_pulse,
  output logic                         frame_bad_pulse,
  output logic                         crc_bad_pulse,
  output logic                         session_bad_pulse,
  output logic                         lane_mask_bad_pulse,
  output logic                         payload_len_bad_pulse,
  output logic [31:0]                  frame_good_count,
  output logic [31:0]                  frame_bad_count,
  output logic [31:0]                  crc_bad_count,
  output logic [31:0]                  session_bad_count,
  output logic [31:0]                  lane_mask_bad_count,
  output logic [31:0]                  payload_len_bad_count,
  output logic [31:0]                  debug_status
);
  localparam logic [7:0] IRP_SOF = 8'hA5;
  localparam logic [7:0] IRP_DATA_TYPE = 8'h11; // {version=1,type=DATA=1}
  localparam int IRP_DATA_HDR_BYTES = 14;
  localparam int IRP_CRC32_BYTES = 4;

  logic header_ok;
  logic session_ok;
  logic lane_mask_ok;
  logic payload_len_ok;
  logic header_crc_ok;
  logic payload_crc_ok;
  logic [7:0] payload_len;
  logic [15:0] total_len;
  logic [15:0] session_id;
  logic [7:0] lane_mask;
  logic [15:0] header_crc_expected;
  logic [15:0] header_crc_seen;
  logic [31:0] payload_crc_expected;
  logic [31:0] payload_crc_seen;
  logic crc_ok;
  logic frame_ok;

  assign validate_ready = 1'b1;
  assign payload_len = get_byte(frame_data, 10);
  assign lane_mask = get_byte(frame_data, 11);
  assign total_len = {get_byte(frame_data, 9), get_byte(frame_data, 8)};
  assign session_id = {get_byte(frame_data, 3), get_byte(frame_data, 2)};
  assign header_crc_seen = {get_byte(frame_data, 13), get_byte(frame_data, 12)};
  assign payload_crc_seen = {
    get_byte(frame_data, IRP_DATA_HDR_BYTES + payload_len + 3),
    get_byte(frame_data, IRP_DATA_HDR_BYTES + payload_len + 2),
    get_byte(frame_data, IRP_DATA_HDR_BYTES + payload_len + 1),
    get_byte(frame_data, IRP_DATA_HDR_BYTES + payload_len + 0)
  };
  assign header_crc_expected = calc_header_crc16(frame_data);
  assign payload_crc_expected = calc_payload_crc32(frame_data, payload_len);
  assign header_ok = (get_byte(frame_data, 0) == IRP_SOF) && (get_byte(frame_data, 1) == IRP_DATA_TYPE);
  assign session_ok = (session_id == expected_session);
  assign lane_mask_ok = (lane_mask == expected_lane_mask);
  assign payload_len_ok =
      (frame_len >= (IRP_DATA_HDR_BYTES + IRP_CRC32_BYTES)) &&
      (payload_len <= (MAX_FRAME_BYTES - IRP_DATA_HDR_BYTES - IRP_CRC32_BYTES)) &&
      (total_len == {8'h00, payload_len}) &&
      (frame_len == (IRP_DATA_HDR_BYTES + {8'h00, payload_len} + IRP_CRC32_BYTES));
  assign header_crc_ok = (header_crc_seen == header_crc_expected);
  assign payload_crc_ok = payload_len_ok && (payload_crc_seen == payload_crc_expected);
  assign crc_ok = header_crc_ok && payload_crc_ok;
  assign frame_ok = header_ok && session_ok && lane_mask_ok && payload_len_ok && crc_ok;
  assign debug_status = {
    frame_ok,
    header_ok,
    session_ok,
    lane_mask_ok,
    payload_len_ok,
    header_crc_ok,
    payload_crc_ok,
    1'b0,
    payload_len,
    lane_mask,
    session_id[7:0]
  };

  function automatic logic [7:0] get_byte(
    input logic [8*MAX_FRAME_BYTES-1:0] data,
    input int idx
  );
    begin
      if ((idx >= 0) && (idx < MAX_FRAME_BYTES)) begin
        get_byte = data[8*idx +: 8];
      end else begin
        get_byte = 8'h00;
      end
    end
  endfunction

  function automatic logic [15:0] crc16_ccitt_next_byte(
    input logic [7:0] data,
    input logic [15:0] crc_in
  );
    logic [15:0] c;
    logic [7:0] d;
    int i;
    begin
      c = crc_in;
      d = data;
      for (i = 0; i < 8; i = i + 1) begin
        if (c[15] ^ d[7]) begin
          c = {c[14:0], 1'b0} ^ 16'h1021;
        end else begin
          c = {c[14:0], 1'b0};
        end
        d = {d[6:0], 1'b0};
      end
      crc16_ccitt_next_byte = c;
    end
  endfunction

  function automatic logic [31:0] crc32_next_byte(
    input logic [7:0] data,
    input logic [31:0] crc_in
  );
    logic [31:0] c;
    int i;
    begin
      c = crc_in ^ {24'h0, data};
      for (i = 0; i < 8; i = i + 1) begin
        if (c[0]) begin
          c = (c >> 1) ^ 32'hEDB88320;
        end else begin
          c = (c >> 1);
        end
      end
      crc32_next_byte = c;
    end
  endfunction

  function automatic logic [15:0] calc_header_crc16(
    input logic [8*MAX_FRAME_BYTES-1:0] data
  );
    logic [15:0] c;
    int i;
    begin
      c = 16'hFFFF;
      for (i = 0; i < 12; i = i + 1) begin
        c = crc16_ccitt_next_byte(get_byte(data, i), c);
      end
      calc_header_crc16 = c;
    end
  endfunction

  function automatic logic [31:0] calc_payload_crc32(
    input logic [8*MAX_FRAME_BYTES-1:0] data,
    input int nbytes
  );
    logic [31:0] c;
    int i;
    begin
      c = 32'hFFFF_FFFF;
      for (i = 0; i < MAX_FRAME_BYTES; i = i + 1) begin
        if (i < nbytes) begin
          c = crc32_next_byte(get_byte(data, IRP_DATA_HDR_BYTES + i), c);
        end
      end
      calc_payload_crc32 = ~c;
    end
  endfunction

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      frame_good_pulse <= 1'b0;
      frame_bad_pulse <= 1'b0;
      crc_bad_pulse <= 1'b0;
      session_bad_pulse <= 1'b0;
      lane_mask_bad_pulse <= 1'b0;
      payload_len_bad_pulse <= 1'b0;
      frame_good_count <= 32'd0;
      frame_bad_count <= 32'd0;
      crc_bad_count <= 32'd0;
      session_bad_count <= 32'd0;
      lane_mask_bad_count <= 32'd0;
      payload_len_bad_count <= 32'd0;
    end else begin
      frame_good_pulse <= 1'b0;
      frame_bad_pulse <= 1'b0;
      crc_bad_pulse <= 1'b0;
      session_bad_pulse <= 1'b0;
      lane_mask_bad_pulse <= 1'b0;
      payload_len_bad_pulse <= 1'b0;

      if (clear_counters) begin
        frame_good_count <= 32'd0;
        frame_bad_count <= 32'd0;
        crc_bad_count <= 32'd0;
        session_bad_count <= 32'd0;
        lane_mask_bad_count <= 32'd0;
        payload_len_bad_count <= 32'd0;
      end else if (validate) begin
        if (frame_ok) begin
          frame_good_pulse <= 1'b1;
          frame_good_count <= frame_good_count + 1'b1;
        end else begin
          frame_bad_pulse <= 1'b1;
          frame_bad_count <= frame_bad_count + 1'b1;
          if (!crc_ok) begin
            crc_bad_pulse <= 1'b1;
            crc_bad_count <= crc_bad_count + 1'b1;
          end
          if (!session_ok) begin
            session_bad_pulse <= 1'b1;
            session_bad_count <= session_bad_count + 1'b1;
          end
          if (!lane_mask_ok) begin
            lane_mask_bad_pulse <= 1'b1;
            lane_mask_bad_count <= lane_mask_bad_count + 1'b1;
          end
          if (!payload_len_ok) begin
            payload_len_bad_pulse <= 1'b1;
            payload_len_bad_count <= payload_len_bad_count + 1'b1;
          end
        end
      end
    end
  end
endmodule
