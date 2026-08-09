`timescale 1ns/1ps

// Generic P9 physical frame receiver.  It consumes symbols only from the
// active-low-Rxd-normalized P6/P8C decoder, validates header/payload CRCs, and
// writes DATA payload bytes into a lane-local temporary buffer.  A frame event
// is emitted only after the complete optical frame has been observed.
module p9_4ppm_frame_rx #(
  parameter int MAX_PAYLOAD_BYTES = 247,
  parameter int LANE_COUNT = 2
) (
  input  logic        clk,
  input  logic        rst_n,
  input  logic        enable_i,
  input  logic        align_i,
  input  logic [1:0]  symbol_i,
  input  logic        symbol_valid_i,
  input  logic        symbol_error_i,
  input  logic        preamble_valid_i,
  output logic        payload_write_pulse_o,
  output logic [7:0]  payload_write_index_o,
  output logic [7:0]  payload_write_data_o,
  output logic        frame_valid_o,
  output logic        frame_is_ack_o,
  output logic        frame_crc_valid_o,
  output logic [31:0] session_epoch_o,
  output logic [15:0] path_epoch_o,
  output logic [15:0] sequence_o,
  output logic [15:0] payload_length_o,
  output logic [7:0]  flags_o,
  output logic [7:0]  lane_id_o,
  output logic [5:0]  source_node_id_o,
  output logic [31:0] object_id_o,
  output logic [31:0] fragment_offset_o,
  output logic [15:0] ack_base_o,
  output logic [31:0] ack_bitmap_o,
  output logic [15:0] ack_credit_o,
  output logic        direction_o,
  output logic        vnext_o,
  output logic [15:0] role_epoch_o,
  output logic        piggyback_ack_valid_o,
  output logic        piggyback_ack_direction_o,
  output logic [31:0] piggyback_ack_session_o,
  output logic [15:0] piggyback_ack_base_o,
  output logic [31:0] piggyback_ack_bitmap_o,
  output logic [15:0] piggyback_ack_credit_o,
  output wire  [31:0] frame_good_count_o,
  output wire  [31:0] frame_bad_count_o,
  output wire  [31:0] crc_bad_count_o,
  output wire  [31:0] preamble_count_o,
  output wire  [31:0] symbol_error_count_o
);
  // The largest P9 object (64 MiB) produces fewer than 2^20 DATA/ACK frames
  // at the fixed 247-byte L1 payload.  Twenty-bit physical counters therefore
  // retain exact values for every authorized P9 campaign while
  // avoiding six unnecessarily wide 32-bit incrementers across the two
  // receive paths on the resource-limited XC7Z010.  The AXI register contract
  // remains 32-bit through explicit zero extension.
  localparam int PHYSICAL_COUNTER_WIDTH = 20;
  localparam int DATA_HEADER_BYTES = 24;
  localparam int ACK_HEADER_BYTES = 20;
  localparam int VNEXT_DATA_HEADER_BYTES = 40;
  localparam int VNEXT_ACK_HEADER_BYTES = 22;

  initial begin
    if (LANE_COUNT != 2 && LANE_COUNT != 4 && LANE_COUNT != 8)
      $error("LANE_COUNT must be 2, 4, or 8");
  end
  typedef enum logic [1:0] {RX_WAIT, RX_COLLECT, RX_VALIDATE} state_t;
  state_t state;
  logic [7:0] header [0:39];
  logic [15:0] byte_index;
  logic [1:0] symbol_index;
  logic [7:0] current_byte;
  logic frame_type_known;
  logic active_ack;
  logic active_vnext;
  logic malformed;
  logic [15:0] header_crc;
  logic [31:0] payload_crc;
  logic [31:0] seen_payload_crc;
  logic [15:0] observed_payload_length;
  logic [PHYSICAL_COUNTER_WIDTH-1:0] frame_good_count_q;
  logic [PHYSICAL_COUNTER_WIDTH-1:0] frame_bad_count_q;
  logic [PHYSICAL_COUNTER_WIDTH-1:0] crc_bad_count_q;
  logic [PHYSICAL_COUNTER_WIDTH-1:0] preamble_count_q;
  logic [PHYSICAL_COUNTER_WIDTH-1:0] symbol_error_count_q;

  assign frame_good_count_o = {{(32-PHYSICAL_COUNTER_WIDTH){1'b0}},
                               frame_good_count_q};
  assign frame_bad_count_o = {{(32-PHYSICAL_COUNTER_WIDTH){1'b0}},
                              frame_bad_count_q};
  assign crc_bad_count_o = {{(32-PHYSICAL_COUNTER_WIDTH){1'b0}},
                            crc_bad_count_q};
  assign preamble_count_o = {{(32-PHYSICAL_COUNTER_WIDTH){1'b0}},
                             preamble_count_q};
  assign symbol_error_count_o = {{(32-PHYSICAL_COUNTER_WIDTH){1'b0}},
                                 symbol_error_count_q};

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

  function automatic logic [31:0] crc32_next_byte(
    input logic [7:0] data, input logic [31:0] crc_in
  );
    logic [31:0] c;
    begin
      c = crc_in;
      for (int idx = 0; idx < 8; idx++)
        c = (c[0] ^ data[idx]) ? ((c >> 1) ^ 32'hEDB8_8320) : (c >> 1);
      crc32_next_byte = c;
    end
  endfunction

  // Synchronous reset is deliberate: payload index/write controls directly
  // drive inferred receive BRAM ports and must never be asynchronously reset.
  always_ff @(posedge clk) begin
    logic [7:0] completed_byte;
    logic header_valid;
    logic payload_valid;
    logic [15:0] data_payload_index;
    logic [15:0] data_trailer_index;
    if (!rst_n) begin
      state <= RX_WAIT;
      byte_index <= 16'd0;
      symbol_index <= 2'd0;
      current_byte <= 8'd0;
      frame_type_known <= 1'b0;
      active_ack <= 1'b0;
      active_vnext <= 1'b0;
      malformed <= 1'b0;
      header_crc <= 16'hFFFF;
      payload_crc <= 32'hFFFF_FFFF;
      seen_payload_crc <= 32'd0;
      observed_payload_length <= 16'd0;
      payload_write_pulse_o <= 1'b0;
      payload_write_index_o <= 8'd0;
      payload_write_data_o <= 8'd0;
      frame_valid_o <= 1'b0;
      frame_is_ack_o <= 1'b0;
      frame_crc_valid_o <= 1'b0;
      session_epoch_o <= 32'd0;
      path_epoch_o <= 16'd0;
      sequence_o <= 16'd0;
      payload_length_o <= 16'd0;
      flags_o <= 8'd0;
      lane_id_o <= 8'd0;
      source_node_id_o <= 6'd0;
      object_id_o <= 32'd0;
      fragment_offset_o <= 32'd0;
      ack_base_o <= 16'd0;
      ack_bitmap_o <= 32'd0;
      ack_credit_o <= 16'd0;
      direction_o <= 1'b0;
      vnext_o <= 1'b0;
      role_epoch_o <= 16'd0;
      piggyback_ack_valid_o <= 1'b0;
      piggyback_ack_direction_o <= 1'b0;
      piggyback_ack_session_o <= 32'd0;
      piggyback_ack_base_o <= 16'd0;
      piggyback_ack_bitmap_o <= 32'd0;
      piggyback_ack_credit_o <= 16'd0;
      frame_good_count_q <= '0;
      frame_bad_count_q <= '0;
      crc_bad_count_q <= '0;
      preamble_count_q <= '0;
      symbol_error_count_q <= '0;
      for (int idx = 0; idx < 40; idx++) header[idx] <= 8'd0;
    end else begin
      payload_write_pulse_o <= 1'b0;
      frame_valid_o <= 1'b0;
      frame_crc_valid_o <= 1'b0;
      completed_byte = current_byte;
      header_valid = 1'b0;
      payload_valid = 1'b0;
      data_payload_index = byte_index -
          (active_vnext ? VNEXT_DATA_HEADER_BYTES : DATA_HEADER_BYTES);
      data_trailer_index = byte_index -
          ((active_vnext ? VNEXT_DATA_HEADER_BYTES : DATA_HEADER_BYTES) +
           observed_payload_length);

      if (!enable_i || align_i) begin
        state <= RX_WAIT;
        byte_index <= 16'd0;
        symbol_index <= 2'd0;
        current_byte <= 8'd0;
        frame_type_known <= 1'b0;
      end else begin
        if (symbol_error_i) begin
          symbol_error_count_q <= symbol_error_count_q + 1'b1;
          if (state == RX_COLLECT) malformed <= 1'b1;
        end
        unique case (state)
          RX_WAIT: begin
            if (preamble_valid_i) begin
              preamble_count_q <= preamble_count_q + 1'b1;
              state <= RX_COLLECT;
              byte_index <= 16'd0;
              symbol_index <= 2'd0;
              current_byte <= 8'd0;
              frame_type_known <= 1'b0;
              active_ack <= 1'b0;
              active_vnext <= 1'b0;
              malformed <= 1'b0;
              header_crc <= 16'hFFFF;
              payload_crc <= 32'hFFFF_FFFF;
              seen_payload_crc <= 32'd0;
              observed_payload_length <= 16'd0;
              for (int idx = 0; idx < 40; idx++) header[idx] <= 8'd0;
            end
          end
          RX_COLLECT: begin
            if (symbol_valid_i) begin
              completed_byte = current_byte;
              completed_byte[2*symbol_index +: 2] = symbol_i;
              current_byte <= completed_byte;
              if (symbol_index == 2'd3) begin
                current_byte <= 8'd0;
                symbol_index <= 2'd0;
                if (byte_index < 40) header[byte_index] <= completed_byte;
                if (byte_index == 1) begin
                  frame_type_known <=
                      (header[0] == 8'hA5 &&
                       (completed_byte == 8'h31 || completed_byte == 8'h35)) ||
                      (header[0] == 8'hAD &&
                       (completed_byte == 8'h32 || completed_byte == 8'h35));
                  active_ack <= completed_byte == 8'h32 ||
                      (completed_byte == 8'h35 && header[0] == 8'hAD);
                  active_vnext <= completed_byte == 8'h35;
                  if (!((header[0] == 8'hA5 &&
                         (completed_byte == 8'h31 || completed_byte == 8'h35)) ||
                        (header[0] == 8'hAD &&
                         (completed_byte == 8'h32 || completed_byte == 8'h35))))
                    malformed <= 1'b1;
                end
                if ((!active_ack && byte_index <
                     (active_vnext ? 38 : 22)) ||
                    (active_ack && byte_index <
                     (active_vnext ? 20 : 18)) ||
                    (!frame_type_known && byte_index < 2))
                  header_crc <= crc16_next_byte(completed_byte, header_crc);
                if (!active_ack && byte_index == 11) begin
                  observed_payload_length <= {completed_byte, header[10]};
                  if ({completed_byte, header[10]} > MAX_PAYLOAD_BYTES)
                    malformed <= 1'b1;
                end
                if (!active_ack && byte_index >=
                    (active_vnext ? VNEXT_DATA_HEADER_BYTES : DATA_HEADER_BYTES) &&
                    data_payload_index < observed_payload_length) begin
                  payload_write_pulse_o <= 1'b1;
                  payload_write_index_o <= data_payload_index[7:0];
                  payload_write_data_o <= completed_byte;
                  payload_crc <= crc32_next_byte(completed_byte, payload_crc);
                end else if (!active_ack && data_trailer_index < 4 &&
                             byte_index >=
                             (active_vnext ? VNEXT_DATA_HEADER_BYTES :
                                             DATA_HEADER_BYTES) +
                             observed_payload_length) begin
                  seen_payload_crc[8*data_trailer_index +: 8] <= completed_byte;
                end
                if ((active_ack && byte_index ==
                     (active_vnext ? VNEXT_ACK_HEADER_BYTES-1 :
                                     ACK_HEADER_BYTES-1)) ||
                    (!active_ack && byte_index ==
                     (active_vnext ? VNEXT_DATA_HEADER_BYTES+3 :
                                     DATA_HEADER_BYTES+3) +
                     observed_payload_length)) begin
                  state <= RX_VALIDATE;
                end else begin
                  byte_index <= byte_index + 1'b1;
                end
              end else begin
                symbol_index <= symbol_index + 1'b1;
              end
            end
          end
          RX_VALIDATE: begin
            if (active_ack) begin
              header_valid = header[0] == 8'hAD &&
                  header[1] == (active_vnext ? 8'h35 : 8'h32) &&
                  (active_vnext ?
                   ({header[21], header[20]} == header_crc) :
                   ({header[19], header[18]} == header_crc)) &&
                  header[10] == 8'd32;
              payload_valid = 1'b1;
            end else begin
              header_valid = header[0] == 8'hA5 &&
                  header[1] == (active_vnext ? 8'h35 : 8'h31) &&
                  (active_vnext ?
                   ({header[39], header[38]} == header_crc) :
                   ({header[23], header[22]} == header_crc)) &&
                  observed_payload_length <= MAX_PAYLOAD_BYTES;
              payload_valid = seen_payload_crc == ~payload_crc;
            end
            frame_valid_o <= 1'b1;
            frame_is_ack_o <= active_ack;
            frame_crc_valid_o <= header_valid && payload_valid && !malformed;
            if (header_valid && payload_valid && !malformed) begin
              frame_good_count_q <= frame_good_count_q + 1'b1;
            end else begin
              frame_bad_count_q <= frame_bad_count_q + 1'b1;
              if (!header_valid || !payload_valid)
                crc_bad_count_q <= crc_bad_count_q + 1'b1;
            end
            session_epoch_o <= {header[5], header[4], header[3], header[2]};
            path_epoch_o <= {header[7], header[6]};
            vnext_o <= active_vnext;
            if (active_ack) begin
              sequence_o <= 16'd0;
              payload_length_o <= 16'd0;
              flags_o <= 8'd0;
              if (LANE_COUNT == 2) begin
                lane_id_o <= {7'd0, header[11][1]};
                source_node_id_o <= header[11][7:2];
              end else if (LANE_COUNT == 4) begin
                lane_id_o <= {6'd0, header[11][2:1]};
                source_node_id_o <= {1'b0, header[11][7:3]};
              end else begin
                lane_id_o <= {5'd0, header[11][3:1]};
                source_node_id_o <= {2'b00, header[11][7:4]};
              end
              object_id_o <= 32'd0;
              fragment_offset_o <= 32'd0;
              ack_base_o <= {header[9], header[8]};
              direction_o <= header[11][0];
              role_epoch_o <= active_vnext ? {header[19], header[18]} : 16'd0;
              ack_credit_o <= {header[13], header[12]};
              ack_bitmap_o <= {header[17], header[16], header[15], header[14]};
              piggyback_ack_valid_o <= 1'b0;
              piggyback_ack_direction_o <= 1'b0;
              piggyback_ack_session_o <= 32'd0;
              piggyback_ack_base_o <= 16'd0;
              piggyback_ack_bitmap_o <= 32'd0;
              piggyback_ack_credit_o <= 16'd0;
            end else begin
              sequence_o <= {header[9], header[8]};
              payload_length_o <= {header[11], header[10]};
              flags_o <= header[12];
              if (LANE_COUNT <= 4) begin
                lane_id_o <= {6'd0, header[13][1:0]};
                source_node_id_o <= header[13][7:2];
              end else begin
                lane_id_o <= {5'd0, header[13][2:0]};
                source_node_id_o <= {1'b0, header[13][7:3]};
              end
              object_id_o <= {header[17], header[16], header[15], header[14]};
              fragment_offset_o <= {header[21], header[20], header[19], header[18]};
              ack_base_o <= 16'd0;
              ack_bitmap_o <= 32'd0;
              ack_credit_o <= 16'd0;
              direction_o <= active_vnext ? header[22][0] : 1'b0;
              role_epoch_o <= active_vnext ? {header[24], header[23]} : 16'd0;
              piggyback_ack_valid_o <= active_vnext && header[22][1];
              piggyback_ack_direction_o <= active_vnext && header[22][2];
              piggyback_ack_session_o <= active_vnext ?
                  {header[28], header[27], header[26], header[25]} : 32'd0;
              piggyback_ack_base_o <= active_vnext ?
                  {header[30], header[29]} : 16'd0;
              piggyback_ack_bitmap_o <= active_vnext ?
                  {header[34], header[33], header[32], header[31]} : 32'd0;
              piggyback_ack_credit_o <= active_vnext ?
                  {header[36], header[35]} : 16'd0;
            end
            state <= RX_WAIT;
          end
          default: state <= RX_WAIT;
        endcase
      end
    end
  end
endmodule
