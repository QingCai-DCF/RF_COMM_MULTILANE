`timescale 1ns/1ps

// Continuous-symbol P9 physical-frame serializer.  The caller stages one
// immutable frame in a lane-local buffer before start and supplies its frozen
// CRC32.  This keeps the 4PPM chip grid gap-free while the selective-repeat
// window itself remains in shared block RAM.
module p9_4ppm_frame_tx #(
  parameter int MAX_PAYLOAD_BYTES = 247,
  parameter int PAYLOAD_ADDR_WIDTH = 13
) (
  input  logic                          clk,
  input  logic                          rst_n,
  input  logic                          enable_i,
  input  logic                          abort_i,
  input  logic [1:0]                    rate_select_i,
  input  logic                          start_valid_i,
  output logic                          start_ready_o,
  input  logic                          frame_is_ack_i,
  input  logic [31:0]                   session_epoch_i,
  input  logic [15:0]                   path_epoch_i,
  input  logic [15:0]                   sequence_i,
  input  logic [15:0]                   payload_length_i,
  input  logic [31:0]                   payload_crc32_i,
  input  logic [7:0]                    flags_i,
  input  logic [7:0]                    lane_id_i,
  input  logic [31:0]                   object_id_i,
  input  logic [31:0]                   fragment_offset_i,
  input  logic [15:0]                   ack_base_i,
  input  logic [31:0]                   ack_bitmap_i,
  input  logic [15:0]                   ack_credit_i,
  input  logic                          direction_i,
  input  logic [PAYLOAD_ADDR_WIDTH-1:0] payload_base_i,
  output logic [PAYLOAD_ADDR_WIDTH-1:0] payload_read_address_o,
  input  logic [7:0]                    payload_read_data_i,
  output logic                          pulse_request_o,
  output logic                          busy_o,
  output logic                          done_pulse_o,
  output logic [31:0]                   frame_count_o,
  output logic [31:0]                   byte_count_o
);
  localparam int DATA_HEADER_BYTES = 24;
  localparam int ACK_HEADER_BYTES = 20;
  localparam int PREAMBLE_SYMBOLS = 16;

  logic active_ack;
  logic [31:0] active_session;
  logic [15:0] active_path;
  logic [15:0] active_sequence;
  logic [15:0] active_payload_length;
  logic [31:0] active_payload_crc32;
  logic [7:0] active_flags;
  logic [7:0] active_lane;
  logic [31:0] active_object;
  logic [31:0] active_fragment_offset;
  logic [15:0] active_ack_base;
  logic [31:0] active_ack_bitmap;
  logic [15:0] active_ack_credit;
  logic active_direction;
  logic [PAYLOAD_ADDR_WIDTH-1:0] active_payload_base;
  logic [7:0] active_chip_cycles;
  logic [7:0] active_pulse_cycles;
  logic [15:0] total_symbols;
  logic [15:0] symbol_index;
  logic [15:0] symbol_cycle;
  logic [1:0] symbol_value;
  logic [15:0] frame_byte_index;
  logic [1:0] symbol_in_byte;
  logic [15:0] payload_offset;
  logic [15:0] header_crc_data;
  logic [15:0] header_crc_ack;
  logic preparing;
  logic [4:0] header_crc_index;
  logic [15:0] header_crc_work;
  logic [15:0] header_crc_next;
  logic [7:0] header_crc_input;
  logic [7:0] selected_frame_byte;
  logic [7:0] payload_byte_q;
  logic [1:0] pulse_chip_index;
  logic [4:0] pulse_chip_offset;

  function automatic logic [15:0] crc16_next_byte(
    input logic [7:0] data, input logic [15:0] crc_in
  );
    logic [15:0] c;
    logic [7:0] d;
    begin
      c = crc_in;
      d = data;
      for (int idx = 0; idx < 8; idx++) begin
        c = (c[15] ^ d[7]) ? ({c[14:0], 1'b0} ^ 16'h1021) : {c[14:0], 1'b0};
        d = {d[6:0], 1'b0};
      end
      crc16_next_byte = c;
    end
  endfunction

  function automatic logic [7:0] data_header_byte_no_crc(input integer index);
    begin
      unique case (index)
        0: data_header_byte_no_crc = 8'hA5;
        1: data_header_byte_no_crc = 8'h31;
        2: data_header_byte_no_crc = active_session[7:0];
        3: data_header_byte_no_crc = active_session[15:8];
        4: data_header_byte_no_crc = active_session[23:16];
        5: data_header_byte_no_crc = active_session[31:24];
        6: data_header_byte_no_crc = active_path[7:0];
        7: data_header_byte_no_crc = active_path[15:8];
        8: data_header_byte_no_crc = active_sequence[7:0];
        9: data_header_byte_no_crc = active_sequence[15:8];
        10: data_header_byte_no_crc = active_payload_length[7:0];
        11: data_header_byte_no_crc = active_payload_length[15:8];
        12: data_header_byte_no_crc = active_flags;
        13: data_header_byte_no_crc = active_lane;
        14: data_header_byte_no_crc = active_object[7:0];
        15: data_header_byte_no_crc = active_object[15:8];
        16: data_header_byte_no_crc = active_object[23:16];
        17: data_header_byte_no_crc = active_object[31:24];
        18: data_header_byte_no_crc = active_fragment_offset[7:0];
        19: data_header_byte_no_crc = active_fragment_offset[15:8];
        20: data_header_byte_no_crc = active_fragment_offset[23:16];
        21: data_header_byte_no_crc = active_fragment_offset[31:24];
        default: data_header_byte_no_crc = 8'h00;
      endcase
    end
  endfunction

  function automatic logic [7:0] ack_header_byte_no_crc(input integer index);
    begin
      unique case (index)
        0: ack_header_byte_no_crc = 8'hAD;
        1: ack_header_byte_no_crc = 8'h32;
        2: ack_header_byte_no_crc = active_session[7:0];
        3: ack_header_byte_no_crc = active_session[15:8];
        4: ack_header_byte_no_crc = active_session[23:16];
        5: ack_header_byte_no_crc = active_session[31:24];
        6: ack_header_byte_no_crc = active_path[7:0];
        7: ack_header_byte_no_crc = active_path[15:8];
        8: ack_header_byte_no_crc = active_ack_base[7:0];
        9: ack_header_byte_no_crc = active_ack_base[15:8];
        10: ack_header_byte_no_crc = 8'd32;
        11: ack_header_byte_no_crc = {7'd0, active_direction};
        12: ack_header_byte_no_crc = active_ack_credit[7:0];
        13: ack_header_byte_no_crc = active_ack_credit[15:8];
        14: ack_header_byte_no_crc = active_ack_bitmap[7:0];
        15: ack_header_byte_no_crc = active_ack_bitmap[15:8];
        16: ack_header_byte_no_crc = active_ack_bitmap[23:16];
        17: ack_header_byte_no_crc = active_ack_bitmap[31:24];
        default: ack_header_byte_no_crc = 8'h00;
      endcase
    end
  endfunction

  function automatic logic [7:0] frame_byte(input integer index);
    integer data_payload_index;
    integer data_trailer_index;
    begin
      data_payload_index = index - DATA_HEADER_BYTES;
      data_trailer_index = index - DATA_HEADER_BYTES - active_payload_length;
      if (active_ack) begin
        if (index < 18) frame_byte = ack_header_byte_no_crc(index);
        else if (index == 18) frame_byte = header_crc_ack[7:0];
        else if (index == 19) frame_byte = header_crc_ack[15:8];
        else frame_byte = 8'h00;
      end else begin
        if (index < 22) frame_byte = data_header_byte_no_crc(index);
        else if (index == 22) frame_byte = header_crc_data[7:0];
        else if (index == 23) frame_byte = header_crc_data[15:8];
        else if (data_payload_index >= 0 && data_payload_index < active_payload_length)
          frame_byte = payload_byte_q;
        else begin
          unique case (data_trailer_index)
            0: frame_byte = active_payload_crc32[7:0];
            1: frame_byte = active_payload_crc32[15:8];
            2: frame_byte = active_payload_crc32[23:16];
            3: frame_byte = active_payload_crc32[31:24];
            default: frame_byte = 8'h00;
          endcase
        end
      end
    end
  endfunction

  always_comb begin
    header_crc_input = active_ack ? ack_header_byte_no_crc(header_crc_index) :
                                    data_header_byte_no_crc(header_crc_index);
    header_crc_next = crc16_next_byte(header_crc_input, header_crc_work);
    selected_frame_byte = frame_byte(frame_byte_index);
    if (symbol_index < PREAMBLE_SYMBOLS) begin
      frame_byte_index = 16'd0;
      symbol_in_byte = 2'd0;
      payload_offset = 16'd0;
      payload_read_address_o = active_payload_base;
      symbol_value = 2'b00;
    end else begin
      frame_byte_index = (symbol_index - PREAMBLE_SYMBOLS) >> 2;
      symbol_in_byte = (symbol_index - PREAMBLE_SYMBOLS) & 2'b11;
      payload_offset = (frame_byte_index >= DATA_HEADER_BYTES) ?
          frame_byte_index - DATA_HEADER_BYTES : 16'd0;
      if (!active_ack && frame_byte_index >= DATA_HEADER_BYTES &&
          frame_byte_index < DATA_HEADER_BYTES + active_payload_length &&
          payload_offset + 1'b1 < active_payload_length)
        payload_read_address_o = active_payload_base + payload_offset + 1'b1;
      else
        payload_read_address_o = active_payload_base + payload_offset;
      selected_frame_byte = frame_byte(frame_byte_index);
      symbol_value = selected_frame_byte[2*symbol_in_byte +: 2];
    end
  end

  assign start_ready_o = enable_i && !busy_o && !preparing;
  // All supported chip lengths are powers of two.  Keep this decode explicit
  // so implementation cannot infer a variable divider/modulo datapath in the
  // physical pulse generator.
  always_comb begin
    unique case (active_chip_cycles)
      8'd32: begin
        pulse_chip_index = symbol_cycle[6:5];
        pulse_chip_offset = symbol_cycle[4:0];
      end
      8'd16: begin
        pulse_chip_index = symbol_cycle[5:4];
        pulse_chip_offset = {1'b0, symbol_cycle[3:0]};
      end
      default: begin
        pulse_chip_index = symbol_cycle[4:3];
        pulse_chip_offset = {2'b00, symbol_cycle[2:0]};
      end
    endcase
  end
  assign pulse_request_o = enable_i && busy_o &&
      (pulse_chip_index == symbol_value) &&
      (pulse_chip_offset < active_pulse_cycles);

  // Serializer state drives synchronous payload-BRAM addresses.  Keep its
  // reset synchronous; the independent endpoint/physical kill path remains
  // asynchronously fail-low at the final Txd output.
  always_ff @(posedge clk) begin
    if (!rst_n) begin
      busy_o <= 1'b0;
      preparing <= 1'b0;
      done_pulse_o <= 1'b0;
      active_ack <= 1'b0;
      active_session <= 32'd0;
      active_path <= 16'd0;
      active_sequence <= 16'd0;
      active_payload_length <= 16'd0;
      active_payload_crc32 <= 32'd0;
      active_flags <= 8'd0;
      active_lane <= 8'd0;
      active_object <= 32'd0;
      active_fragment_offset <= 32'd0;
      active_ack_base <= 16'd0;
      active_ack_bitmap <= 32'd0;
      active_ack_credit <= 16'd0;
      active_direction <= 1'b0;
      active_payload_base <= '0;
      payload_byte_q <= 8'd0;
      header_crc_data <= 16'd0;
      header_crc_ack <= 16'd0;
      header_crc_index <= 5'd0;
      header_crc_work <= 16'hFFFF;
      active_chip_cycles <= 8'd8;
      active_pulse_cycles <= 8'd5;
      total_symbols <= 16'd0;
      symbol_index <= 16'd0;
      symbol_cycle <= 16'd0;
      frame_count_o <= 32'd0;
      byte_count_o <= 32'd0;
    end else begin
      done_pulse_o <= 1'b0;
      if (!enable_i || abort_i) begin
        busy_o <= 1'b0;
        preparing <= 1'b0;
        symbol_index <= 16'd0;
        symbol_cycle <= 16'd0;
      end else if (preparing) begin
        if (header_crc_index == (active_ack ? 5'd17 : 5'd21)) begin
          if (active_ack) header_crc_ack <= header_crc_next;
          else header_crc_data <= header_crc_next;
          preparing <= 1'b0;
          busy_o <= 1'b1;
          symbol_index <= 16'd0;
          symbol_cycle <= 16'd0;
        end else begin
          header_crc_work <= header_crc_next;
          header_crc_index <= header_crc_index + 1'b1;
        end
      end else if (!busy_o) begin
        if (start_valid_i) begin
          preparing <= 1'b1;
          header_crc_index <= 5'd0;
          header_crc_work <= 16'hFFFF;
          active_ack <= frame_is_ack_i;
          active_session <= session_epoch_i;
          active_path <= path_epoch_i;
          active_sequence <= sequence_i;
          active_payload_length <= (payload_length_i > MAX_PAYLOAD_BYTES) ?
              MAX_PAYLOAD_BYTES[15:0] : payload_length_i;
          active_payload_crc32 <= payload_crc32_i;
          active_flags <= flags_i;
          active_lane <= lane_id_i;
          active_object <= object_id_i;
          active_fragment_offset <= fragment_offset_i;
          active_ack_base <= ack_base_i;
          active_ack_bitmap <= ack_bitmap_i;
          active_ack_credit <= ack_credit_i;
          active_direction <= direction_i;
          active_payload_base <= payload_base_i;
          unique case (rate_select_i)
            2'd0: begin active_chip_cycles <= 8'd32; active_pulse_cycles <= 8'd8; end
            2'd1: begin active_chip_cycles <= 8'd16; active_pulse_cycles <= 8'd8; end
            default: begin active_chip_cycles <= 8'd8; active_pulse_cycles <= 8'd5; end
          endcase
          total_symbols <= PREAMBLE_SYMBOLS +
              (frame_is_ack_i ? ACK_HEADER_BYTES*4 :
               (DATA_HEADER_BYTES + ((payload_length_i > MAX_PAYLOAD_BYTES) ?
                MAX_PAYLOAD_BYTES : payload_length_i) + 4)*4);
          symbol_index <= 16'd0;
          symbol_cycle <= 16'd0;
        end
      end else if (symbol_cycle == active_chip_cycles*4 - 1'b1) begin
        symbol_cycle <= 16'd0;
        if (!active_ack &&
            symbol_index == PREAMBLE_SYMBOLS + DATA_HEADER_BYTES*4 - 1)
          payload_byte_q <= payload_read_data_i;
        else if (!active_ack &&
                 symbol_index >= PREAMBLE_SYMBOLS + DATA_HEADER_BYTES*4 &&
                 frame_byte_index >= DATA_HEADER_BYTES &&
                 frame_byte_index < DATA_HEADER_BYTES + active_payload_length &&
                 symbol_in_byte == 2'd3 &&
                 payload_offset + 1'b1 < active_payload_length)
          payload_byte_q <= payload_read_data_i;
        if (symbol_index == total_symbols - 1'b1) begin
          busy_o <= 1'b0;
          done_pulse_o <= 1'b1;
          frame_count_o <= frame_count_o + 1'b1;
          byte_count_o <= byte_count_o +
              (active_ack ? ACK_HEADER_BYTES : DATA_HEADER_BYTES + active_payload_length + 4);
        end else begin
          symbol_index <= symbol_index + 1'b1;
        end
      end else begin
        symbol_cycle <= symbol_cycle + 1'b1;
      end
    end
  end
endmodule
