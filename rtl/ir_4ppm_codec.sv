`timescale 1ns/1ps
module ir_4ppm_codec #(
  parameter int CNT_CHIP_MAX = 7,
  parameter int CNT_PREAMBLE = 16,
  parameter int TX_PULSE_CYCLES = 8,
  parameter int DETECT_START_CYCLES = 0,
  parameter int DETECT_END_CYCLES = CNT_CHIP_MAX
) (
  input  logic       clk,
  input  logic       rst_n,
  input  logic       enable,

  input  logic [1:0] tx_symbol,
  input  logic       tx_symbol_valid,
  output logic       tx_symbol_ready,
  output logic       tx_symbol_done,
  output logic       tx_pulse,

  input  logic       rx_align,
  input  logic       rx_pulse_active,
  output logic [1:0] rx_symbol,
  output logic       rx_symbol_valid,
  output logic       rx_symbol_error,
  output logic [3:0] rx_symbol_chips,
  output logic [31:0] debug_status
);
  localparam int TICK_W = (CNT_CHIP_MAX <= 1) ? 1 : $clog2(CNT_CHIP_MAX + 1);
  localparam int CHIP_CYCLES = CNT_CHIP_MAX + 1;
  localparam int TX_PULSE_CYCLES_CLAMPED =
      (TX_PULSE_CYCLES < 1) ? 1 :
      ((TX_PULSE_CYCLES > CHIP_CYCLES) ? CHIP_CYCLES : TX_PULSE_CYCLES);
  localparam int DETECT_START_INT = (DETECT_START_CYCLES < 0) ? 0 :
      ((DETECT_START_CYCLES > CNT_CHIP_MAX) ? CNT_CHIP_MAX : DETECT_START_CYCLES);
  localparam int DETECT_END_INT = (DETECT_END_CYCLES < DETECT_START_INT) ? DETECT_START_INT :
      ((DETECT_END_CYCLES > CNT_CHIP_MAX) ? CNT_CHIP_MAX : DETECT_END_CYCLES);

  logic tx_busy;
  logic [3:0] tx_chips;
  logic [TICK_W-1:0] tx_tick;
  logic [1:0] tx_chip_idx;

  logic [TICK_W-1:0] rx_tick;
  logic [1:0] rx_chip_idx;
  logic [3:0] rx_capture;
  logic chip_seen;

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
  assign tx_pulse = tx_busy && tx_chips[3 - tx_chip_idx] && (tx_tick < TX_PULSE_CYCLES_CLAMPED[TICK_W-1:0]);
  assign debug_status = {
    tx_busy,
    tx_pulse,
    tx_symbol_ready,
    tx_symbol_done,
    rx_symbol_valid,
    rx_symbol_error,
    tx_chip_idx,
    rx_chip_idx,
    tx_tick,
    rx_tick,
    tx_chips,
    rx_capture
  };

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      tx_busy <= 1'b0;
      tx_chips <= 4'b0000;
      tx_tick <= '0;
      tx_chip_idx <= 2'd0;
      tx_symbol_done <= 1'b0;
    end else begin
      tx_symbol_done <= 1'b0;
      if (!enable) begin
        tx_busy <= 1'b0;
        tx_chips <= 4'b0000;
        tx_tick <= '0;
        tx_chip_idx <= 2'd0;
      end else if (!tx_busy && tx_symbol_valid) begin
        tx_busy <= 1'b1;
        tx_chips <= encode_4ppm(tx_symbol);
        tx_tick <= '0;
        tx_chip_idx <= 2'd0;
      end else if (tx_busy) begin
        if (tx_tick == CNT_CHIP_MAX[TICK_W-1:0]) begin
          tx_tick <= '0;
          if (tx_chip_idx == 2'd3) begin
            tx_chip_idx <= 2'd0;
            tx_busy <= 1'b0;
            tx_symbol_done <= 1'b1;
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
      rx_symbol <= 2'b00;
      rx_symbol_valid <= 1'b0;
      rx_symbol_error <= 1'b0;
      rx_symbol_chips <= 4'b0000;
    end else begin
      rx_symbol_valid <= 1'b0;
      rx_symbol_error <= 1'b0;
      if (!enable || rx_align) begin
        rx_tick <= '0;
        rx_chip_idx <= 2'd0;
        rx_capture <= 4'b0000;
        chip_seen <= 1'b0;
        rx_symbol_chips <= 4'b0000;
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
            rx_symbol_chips <= {rx_capture[3:1], chip_seen};
            if (decode_4ppm({rx_capture[3:1], chip_seen})[2]) begin
              rx_symbol <= decode_4ppm({rx_capture[3:1], chip_seen})[1:0];
              rx_symbol_valid <= 1'b1;
            end else begin
              rx_symbol_error <= 1'b1;
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
