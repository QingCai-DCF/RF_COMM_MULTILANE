`timescale 1ns/1ps

// Runtime-selectable receive-only wrapper around the P6/P8C-proven 4PPM
// decoder.  Exactly one fixed-timing decoder is enabled at a time; changing
// rate forces alignment so no partial symbol can cross a profile boundary.
module p9_rate_4ppm_rx (
  input  logic        clk,
  input  logic        rst_n,
  input  logic        enable_i,
  input  logic [1:0]  rate_select_i, // 0=1 Mbit/s, 1=2 Mbit/s, 2=4 Mbit/s
  input  logic        align_i,
  input  logic        rx_pulse_active_i,
  output logic [1:0]  symbol_o,
  output logic        symbol_valid_o,
  output logic        symbol_error_o,
  output logic        preamble_valid_o,
  output logic [15:0] preamble_count_o,
  output logic [3:0]  symbol_chips_o
);
  logic [1:0] symbol [0:2];
  logic symbol_valid [0:2];
  logic symbol_error [0:2];
  logic preamble_valid [0:2];
  logic [15:0] preamble_count [0:2];
  logic [3:0] symbol_chips [0:2];
  logic [1:0] selected_rate;

  assign selected_rate = (rate_select_i > 2) ? 2'd2 : rate_select_i;

  ir_4ppm_codec #(
    .CNT_CHIP_MAX(31), .CNT_PREAMBLE(16), .TX_PULSE_CYCLES(8),
    .DETECT_START_CYCLES(0), .DETECT_END_CYCLES(31),
    .RX_ACQUIRE_ON_FIRST_PULSE(1'b1)
  ) u_rx_1mbps (
    .clk, .rst_n, .enable(enable_i && selected_rate == 2'd0),
    .tx_symbol(2'b00), .tx_symbol_valid(1'b0), .tx_symbol_ready(),
    .tx_symbol_done(), .tx_preamble_valid(1'b0), .tx_preamble_ready(),
    .tx_preamble_done(), .tx_pulse(),
    .rx_align(align_i || selected_rate != 2'd0),
    .rx_pulse_active(rx_pulse_active_i), .rx_symbol(symbol[0]),
    .rx_symbol_valid(symbol_valid[0]), .rx_symbol_error(symbol_error[0]),
    .rx_preamble_valid(preamble_valid[0]), .rx_preamble_count(preamble_count[0]),
    .rx_symbol_chips(symbol_chips[0]), .debug_status()
  );

  ir_4ppm_codec #(
    .CNT_CHIP_MAX(15), .CNT_PREAMBLE(16), .TX_PULSE_CYCLES(8),
    .DETECT_START_CYCLES(0), .DETECT_END_CYCLES(15),
    .RX_ACQUIRE_ON_FIRST_PULSE(1'b1)
  ) u_rx_2mbps (
    .clk, .rst_n, .enable(enable_i && selected_rate == 2'd1),
    .tx_symbol(2'b00), .tx_symbol_valid(1'b0), .tx_symbol_ready(),
    .tx_symbol_done(), .tx_preamble_valid(1'b0), .tx_preamble_ready(),
    .tx_preamble_done(), .tx_pulse(),
    .rx_align(align_i || selected_rate != 2'd1),
    .rx_pulse_active(rx_pulse_active_i), .rx_symbol(symbol[1]),
    .rx_symbol_valid(symbol_valid[1]), .rx_symbol_error(symbol_error[1]),
    .rx_preamble_valid(preamble_valid[1]), .rx_preamble_count(preamble_count[1]),
    .rx_symbol_chips(symbol_chips[1]), .debug_status()
  );

  ir_4ppm_codec #(
    .CNT_CHIP_MAX(7), .CNT_PREAMBLE(16), .TX_PULSE_CYCLES(8),
    // Sample the centre of each 125 ns FIR chip.  The two-cycle aperture
    // accepts the TFDU6102 100..140 ns Rxd pulse-width range plus its 20 ns
    // leading-edge jitter without counting a stretched neighbouring tail.
    .DETECT_START_CYCLES(3), .DETECT_END_CYCLES(4),
    .RX_ACQUIRE_ON_FIRST_PULSE(1'b1)
  ) u_rx_4mbps (
    .clk, .rst_n, .enable(enable_i && selected_rate == 2'd2),
    .tx_symbol(2'b00), .tx_symbol_valid(1'b0), .tx_symbol_ready(),
    .tx_symbol_done(), .tx_preamble_valid(1'b0), .tx_preamble_ready(),
    .tx_preamble_done(), .tx_pulse(),
    .rx_align(align_i || selected_rate != 2'd2),
    .rx_pulse_active(rx_pulse_active_i), .rx_symbol(symbol[2]),
    .rx_symbol_valid(symbol_valid[2]), .rx_symbol_error(symbol_error[2]),
    .rx_preamble_valid(preamble_valid[2]), .rx_preamble_count(preamble_count[2]),
    .rx_symbol_chips(symbol_chips[2]), .debug_status()
  );

  always_comb begin
    symbol_o = symbol[selected_rate];
    symbol_valid_o = symbol_valid[selected_rate];
    symbol_error_o = symbol_error[selected_rate];
    preamble_valid_o = preamble_valid[selected_rate];
    preamble_count_o = preamble_count[selected_rate];
    symbol_chips_o = symbol_chips[selected_rate];
  end
endmodule
