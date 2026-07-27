`timescale 1ns/1ps
module ir_4ppm_codec #(
  parameter int CNT_CHIP_MAX = 7,
  parameter int CNT_PREAMBLE = 16,
  parameter int TX_PULSE_CYCLES = 8,
  parameter int DETECT_START_CYCLES = 0,
  parameter int DETECT_END_CYCLES = CNT_CHIP_MAX,
  // Legacy users retain the serializer-aligned receive grid.  P9 enables
  // first-pulse acquisition because a real TFDU path and the Rxd synchronizer
  // add latency that is not phase-locked to the local serializer start.
  parameter bit RX_ACQUIRE_ON_FIRST_PULSE = 1'b0
) (
  input  logic       clk,
  input  logic       rst_n,
  input  logic       enable,

  input  logic [1:0] tx_symbol,
  input  logic       tx_symbol_valid,
  output logic       tx_symbol_ready,
  output logic       tx_symbol_done,
  input  logic       tx_preamble_valid,
  output logic       tx_preamble_ready,
  output logic       tx_preamble_done,
  output logic       tx_pulse,

  input  logic       rx_align,
  input  logic       rx_pulse_active,
  output logic [1:0] rx_symbol,
  output logic       rx_symbol_valid,
  output logic       rx_symbol_error,
  output logic       rx_preamble_valid,
  output logic [15:0] rx_preamble_count,
  output logic [3:0] rx_symbol_chips,
  output logic [31:0] debug_status
);
  localparam int TICK_W = (CNT_CHIP_MAX <= 1) ? 1 : $clog2(CNT_CHIP_MAX + 1);
  localparam int PREAMBLE_SYMBOLS = (CNT_PREAMBLE < 1) ? 1 : CNT_PREAMBLE;
  localparam logic [15:0] PREAMBLE_SYMBOLS_16 = PREAMBLE_SYMBOLS;
  localparam logic [15:0] PREAMBLE_LAST_16 = PREAMBLE_SYMBOLS - 1;
  localparam int CHIP_CYCLES = CNT_CHIP_MAX + 1;
  localparam int TX_PULSE_CYCLES_CLAMPED =
      (TX_PULSE_CYCLES < 1) ? 1 :
      ((TX_PULSE_CYCLES > CHIP_CYCLES) ? CHIP_CYCLES : TX_PULSE_CYCLES);
  localparam int DETECT_START_INT = (DETECT_START_CYCLES < 0) ? 0 :
      ((DETECT_START_CYCLES > CNT_CHIP_MAX) ? CNT_CHIP_MAX : DETECT_START_CYCLES);
  localparam int DETECT_END_INT = (DETECT_END_CYCLES < DETECT_START_INT) ? DETECT_START_INT :
      ((DETECT_END_CYCLES > CNT_CHIP_MAX) ? CNT_CHIP_MAX : DETECT_END_CYCLES);

  logic tx_busy;
  logic tx_preamble_active;
  logic [15:0] tx_preamble_count;
  logic [3:0] tx_chips;
  logic [TICK_W-1:0] tx_tick;
  logic [1:0] tx_chip_idx;

  logic [TICK_W-1:0] rx_tick;
  logic [1:0] rx_chip_idx;
  logic [3:0] rx_capture;
  logic chip_seen;
  logic rx_phase_acquired;
  logic [3:0] rx_complete_chips;
  logic [2:0] rx_complete_decode;

  function automatic logic [3:0] encode_4ppm(input logic [1:0] d);
    begin
      case (d)
        2'b00: encode_4ppm = 4'b1000;
        2'b01: encode_4ppm = 4'b0100;
        2'b10: encode_4ppm = 4'b0010;
        default: encode_4ppm = 4'b0001;
      endcase
    end
  endfunction

  function automatic logic [2:0] decode_4ppm(input logic [3:0] chips);
    begin
      case (chips)
        4'b1000: decode_4ppm = 3'b100;
        4'b0100: decode_4ppm = 3'b101;
        4'b0010: decode_4ppm = 3'b110;
        4'b0001: decode_4ppm = 3'b111;
        default: decode_4ppm = 3'b000;
      endcase
    end
  endfunction

  assign tx_symbol_ready = enable && !tx_busy;
  assign tx_preamble_ready = enable && !tx_busy;
  assign tx_pulse = tx_busy && tx_chips[3 - tx_chip_idx] && (tx_tick < TX_PULSE_CYCLES_CLAMPED[TICK_W-1:0]);
  assign rx_complete_chips = {rx_capture[3:1], chip_seen};
  assign rx_complete_decode = decode_4ppm(rx_complete_chips);

  always_comb begin
    debug_status = '0;
    debug_status[0] = tx_busy;
    debug_status[1] = tx_pulse;
    debug_status[2] = tx_symbol_ready;
    debug_status[3] = tx_symbol_done;
    debug_status[4] = tx_preamble_active;
    debug_status[5] = tx_preamble_done;
    debug_status[6] = tx_preamble_ready;
    debug_status[7] = rx_symbol_valid;
    debug_status[8] = rx_symbol_error;
    debug_status[9] = rx_preamble_valid;
    debug_status[11:10] = tx_chip_idx;
    debug_status[13:12] = rx_chip_idx;
    debug_status[17:14] = tx_chips;
    debug_status[21:18] = rx_capture;
    debug_status[25:22] = tx_preamble_count[3:0];
    debug_status[29:26] = rx_preamble_count[3:0];
    debug_status[30] = rx_phase_acquired;
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      tx_busy <= 1'b0;
      tx_preamble_active <= 1'b0;
      tx_preamble_count <= '0;
      tx_chips <= 4'b0000;
      tx_tick <= '0;
      tx_chip_idx <= 2'd0;
      tx_symbol_done <= 1'b0;
      tx_preamble_done <= 1'b0;
    end else begin
      tx_symbol_done <= 1'b0;
      tx_preamble_done <= 1'b0;
      if (!enable) begin
        tx_busy <= 1'b0;
        tx_preamble_active <= 1'b0;
        tx_preamble_count <= '0;
        tx_chips <= 4'b0000;
        tx_tick <= '0;
        tx_chip_idx <= 2'd0;
      end else if (!tx_busy && tx_preamble_valid) begin
        tx_busy <= 1'b1;
        tx_preamble_active <= 1'b1;
        tx_preamble_count <= '0;
        tx_chips <= encode_4ppm(2'b00);
        tx_tick <= '0;
        tx_chip_idx <= 2'd0;
      end else if (!tx_busy && tx_symbol_valid) begin
        tx_busy <= 1'b1;
        tx_preamble_active <= 1'b0;
        tx_preamble_count <= '0;
        tx_chips <= encode_4ppm(tx_symbol);
        tx_tick <= '0;
        tx_chip_idx <= 2'd0;
      end else if (tx_busy) begin
        if (tx_tick == CNT_CHIP_MAX[TICK_W-1:0]) begin
          tx_tick <= '0;
          if (tx_chip_idx == 2'd3) begin
            tx_chip_idx <= 2'd0;
            if (tx_preamble_active && (tx_preamble_count != PREAMBLE_LAST_16)) begin
              tx_preamble_count <= tx_preamble_count + 1'b1;
              tx_chips <= encode_4ppm(2'b00);
            end else begin
              tx_busy <= 1'b0;
              tx_preamble_active <= 1'b0;
              tx_preamble_count <= '0;
              if (tx_preamble_active) begin
                tx_preamble_done <= 1'b1;
              end else begin
                tx_symbol_done <= 1'b1;
              end
            end
          end else begin
            tx_chip_idx <= tx_chip_idx + 1'b1;
          end
        end else begin
          tx_tick <= tx_tick + 1'b1;
        end
      end
    end
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      rx_tick <= '0;
      rx_chip_idx <= 2'd0;
      rx_capture <= 4'b0000;
      chip_seen <= 1'b0;
      rx_phase_acquired <= !RX_ACQUIRE_ON_FIRST_PULSE;
      rx_symbol <= 2'b00;
      rx_symbol_valid <= 1'b0;
      rx_symbol_error <= 1'b0;
      rx_preamble_valid <= 1'b0;
      rx_preamble_count <= 16'd0;
      rx_symbol_chips <= 4'b0000;
    end else begin
      rx_symbol_valid <= 1'b0;
      rx_symbol_error <= 1'b0;
      rx_preamble_valid <= 1'b0;
      if (!enable || rx_align) begin
        rx_tick <= '0;
        rx_chip_idx <= 2'd0;
        rx_capture <= 4'b0000;
        chip_seen <= 1'b0;
        rx_phase_acquired <= !RX_ACQUIRE_ON_FIRST_PULSE;
        rx_preamble_count <= 16'd0;
        rx_symbol_chips <= 4'b0000;
      end else if (RX_ACQUIRE_ON_FIRST_PULSE && !rx_phase_acquired) begin
        // The first received pulse is chip 0 of the all-zero P9 preamble.
        // Starting at tick 1 accounts for the acquisition sample itself and
        // keeps every following preamble pulse on the next symbol's tick 0.
        // This removes unknown optical/synchronizer latency without changing
        // the transmitted chip period or accepting a partial frame.
        rx_tick <= '0;
        rx_chip_idx <= 2'd0;
        rx_capture <= 4'b0000;
        chip_seen <= 1'b0;
        rx_preamble_count <= 16'd0;
        rx_symbol_chips <= 4'b0000;
        if (rx_pulse_active) begin
          rx_phase_acquired <= 1'b1;
          rx_tick <= {{(TICK_W-1){1'b0}}, 1'b1};
          chip_seen <= 1'b1;
        end
      end else begin
        if ((rx_tick >= DETECT_START_INT[TICK_W-1:0]) &&
            (rx_tick <= DETECT_END_INT[TICK_W-1:0]) &&
            rx_pulse_active) begin
          chip_seen <= 1'b1;
        end

        if (rx_tick == CNT_CHIP_MAX[TICK_W-1:0]) begin
          rx_capture[3 - rx_chip_idx] <= chip_seen;
          chip_seen <= 1'b0;
          rx_tick <= '0;
          if (rx_chip_idx == 2'd3) begin
            rx_chip_idx <= 2'd0;
            rx_symbol_chips <= rx_complete_chips;
            if (rx_complete_decode[2]) begin
              rx_symbol <= rx_complete_decode[1:0];
              rx_symbol_valid <= 1'b1;
              if (rx_complete_decode[1:0] == 2'b00) begin
                if (rx_preamble_count < PREAMBLE_SYMBOLS_16) begin
                  rx_preamble_count <= rx_preamble_count + 16'd1;
                end
                if (rx_preamble_count == PREAMBLE_LAST_16) begin
                  rx_preamble_valid <= 1'b1;
                end
              end else begin
                rx_preamble_count <= 16'd0;
              end
            end else begin
              rx_symbol_error <= 1'b1;
              rx_preamble_count <= 16'd0;
            end
            rx_capture <= 4'b0000;
          end else begin
            rx_chip_idx <= rx_chip_idx + 1'b1;
          end
        end else begin
          rx_tick <= rx_tick + 1'b1;
        end
      end
    end
  end
endmodule
