`timescale 1ns/1ps

module tfdu_debug_probe #(
  parameter int LANE_COUNT = 4,
  parameter int CLK_HZ = 64000000,
  parameter int STARTUP_US = 500,
  parameter int TXD_STUCK_HIGH_MAX_NS = 80000,
  parameter int STATUS_WORDS = 24
) (
  input  logic clk,
  input  logic rst_n,

  input  logic [LANE_COUNT-1:0] tfdu_mode_cmd,
  input  logic [LANE_COUNT-1:0] tfdu_sd_cmd,
  input  logic [LANE_COUNT-1:0] tfdu_txd_cmd,
  input  logic [LANE_COUNT-1:0] tfdu_rxd_pin,

  input  logic [LANE_COUNT-1:0] lane_enable,
  input  logic [LANE_COUNT-1:0] startup_done,

  input  logic extra_status_words_valid,
  input  logic [8*32-1:0] extra_status_words_flat,

  output logic [STATUS_WORDS*32-1:0] status_words_flat
);
  localparam int STARTUP_WAIT_CYCLES =
      (CLK_HZ / 1000000) * STARTUP_US;
  localparam int TXD_STUCK_HIGH_MAX_CYCLES =
      ((CLK_HZ / 1000000) * TXD_STUCK_HIGH_MAX_NS + 999) / 1000;
  localparam logic [15:0] LANE_COUNT_WORD = LANE_COUNT;

  logic [LANE_COUNT-1:0] rxd_sync_0;
  logic [LANE_COUNT-1:0] rxd_sync_1;
  logic [LANE_COUNT-1:0] rxd_sync_prev;
  logic [LANE_COUNT-1:0] txd_cmd_prev;

  logic [31:0] rxd_active_low_pulse_count [LANE_COUNT];
  logic [31:0] rxd_falling_edge_count [LANE_COUNT];
  logic [31:0] rxd_rising_edge_count [LANE_COUNT];
  logic [31:0] txd_rising_edge_count [LANE_COUNT];
  logic [31:0] txd_high_consecutive_count [LANE_COUNT];
  logic [31:0] txd_high_consecutive_max_cycles [LANE_COUNT];
  logic [31:0] txd_high_total_cycles [LANE_COUNT];
  logic [31:0] startup_wait_counter [LANE_COUNT];
  logic [LANE_COUNT-1:0] txd_stuck_high_violation;
  logic [LANE_COUNT-1:0] duty_window_violation;

  function automatic [31:0] pack_lane_bits(input logic [LANE_COUNT-1:0] value);
    pack_lane_bits = 32'h0;
    for (int i = 0; i < LANE_COUNT; i++) begin
      pack_lane_bits[i] = value[i];
    end
  endfunction

  function automatic [31:0] pack_low16(input logic [31:0] lane0, input logic [31:0] lane1);
    pack_low16 = {lane1[15:0], lane0[15:0]};
  endfunction

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      rxd_sync_0 <= '0;
      rxd_sync_1 <= '0;
      rxd_sync_prev <= '0;
      txd_cmd_prev <= '0;
      txd_stuck_high_violation <= '0;
      duty_window_violation <= '0;
      for (int lane = 0; lane < LANE_COUNT; lane++) begin
        rxd_active_low_pulse_count[lane] <= 32'h0;
        rxd_falling_edge_count[lane] <= 32'h0;
        rxd_rising_edge_count[lane] <= 32'h0;
        txd_rising_edge_count[lane] <= 32'h0;
        txd_high_consecutive_count[lane] <= 32'h0;
        txd_high_consecutive_max_cycles[lane] <= 32'h0;
        txd_high_total_cycles[lane] <= 32'h0;
        startup_wait_counter[lane] <= 32'h0;
      end
    end else begin
      rxd_sync_0 <= tfdu_rxd_pin;
      rxd_sync_1 <= rxd_sync_0;
      rxd_sync_prev <= rxd_sync_1;
      txd_cmd_prev <= tfdu_txd_cmd;

      for (int lane = 0; lane < LANE_COUNT; lane++) begin
        if (!txd_cmd_prev[lane] && tfdu_txd_cmd[lane]) begin
          txd_rising_edge_count[lane] <= txd_rising_edge_count[lane] + 1'b1;
        end

        if (!startup_done[lane] && !tfdu_sd_cmd[lane]) begin
          if (startup_wait_counter[lane] < STARTUP_WAIT_CYCLES) begin
            startup_wait_counter[lane] <= startup_wait_counter[lane] + 1'b1;
          end
        end

        if (tfdu_txd_cmd[lane]) begin
          txd_high_consecutive_count[lane] <= txd_high_consecutive_count[lane] + 1'b1;
          txd_high_total_cycles[lane] <= txd_high_total_cycles[lane] + 1'b1;
          if (txd_high_consecutive_count[lane] >= TXD_STUCK_HIGH_MAX_CYCLES) begin
            txd_stuck_high_violation[lane] <= 1'b1;
          end
          if (txd_high_consecutive_count[lane] >= txd_high_consecutive_max_cycles[lane]) begin
            txd_high_consecutive_max_cycles[lane] <= txd_high_consecutive_count[lane] + 1'b1;
          end
        end else begin
          txd_high_consecutive_count[lane] <= 32'h0;
        end

        if (rxd_sync_prev[lane] && !rxd_sync_1[lane]) begin
          rxd_falling_edge_count[lane] <= rxd_falling_edge_count[lane] + 1'b1;
          rxd_active_low_pulse_count[lane] <= rxd_active_low_pulse_count[lane] + 1'b1;
        end
        if (!rxd_sync_prev[lane] && rxd_sync_1[lane]) begin
          rxd_rising_edge_count[lane] <= rxd_rising_edge_count[lane] + 1'b1;
        end
      end
    end
  end

  always_comb begin
    status_words_flat = '0;
    status_words_flat[0*32 +: 32] = 32'h50344144; // "P4AD"
    status_words_flat[1*32 +: 32] = {LANE_COUNT_WORD, 16'h0001};
    status_words_flat[2*32 +: 32] = pack_lane_bits(tfdu_mode_cmd);
    status_words_flat[3*32 +: 32] = pack_lane_bits(tfdu_sd_cmd);
    status_words_flat[4*32 +: 32] = pack_lane_bits(tfdu_txd_cmd);
    status_words_flat[5*32 +: 32] = pack_lane_bits(rxd_sync_1);
    status_words_flat[6*32 +: 32] = pack_lane_bits(lane_enable);
    status_words_flat[7*32 +: 32] = pack_lane_bits(startup_done);
    status_words_flat[8*32 +: 32] = pack_low16(rxd_active_low_pulse_count[0], rxd_active_low_pulse_count[1]);
    status_words_flat[9*32 +: 32] = pack_low16(rxd_active_low_pulse_count[2], rxd_active_low_pulse_count[3]);
    status_words_flat[10*32 +: 32] = pack_low16(rxd_rising_edge_count[0], rxd_rising_edge_count[1]);
    status_words_flat[11*32 +: 32] = pack_low16(txd_high_consecutive_max_cycles[0], txd_high_consecutive_max_cycles[1]);
    status_words_flat[12*32 +: 32] = pack_low16(txd_high_total_cycles[0], txd_high_total_cycles[1]);
    status_words_flat[13*32 +: 32] = pack_lane_bits(txd_stuck_high_violation);
    status_words_flat[14*32 +: 32] = pack_lane_bits(duty_window_violation);
    status_words_flat[15*32 +: 32] = {
      8'h0,
      txd_rising_edge_count[0][15:0],
      (&tfdu_sd_cmd),
      (&tfdu_sd_cmd) && !(|tfdu_txd_cmd),
      (!(|tfdu_sd_cmd)) && !(|tfdu_txd_cmd) && (&lane_enable) && (&startup_done),
      5'h0
    };
    if (extra_status_words_valid) begin
      for (int word = 0; word < 8; word++) begin
        status_words_flat[(16 + word)*32 +: 32] = extra_status_words_flat[word*32 +: 32];
      end
    end else begin
      status_words_flat[16*32 +: 32] = pack_low16(txd_rising_edge_count[0], txd_rising_edge_count[1]);
      status_words_flat[17*32 +: 32] = pack_low16(txd_rising_edge_count[2], txd_rising_edge_count[3]);
      status_words_flat[18*32 +: 32] = pack_low16(txd_high_consecutive_max_cycles[0], txd_high_consecutive_max_cycles[1]);
      status_words_flat[19*32 +: 32] = pack_low16(txd_high_consecutive_max_cycles[2], txd_high_consecutive_max_cycles[3]);
      status_words_flat[20*32 +: 32] = pack_low16(txd_high_total_cycles[0], txd_high_total_cycles[1]);
      status_words_flat[21*32 +: 32] = pack_low16(txd_high_total_cycles[2], txd_high_total_cycles[3]);
      status_words_flat[22*32 +: 32] = pack_low16(rxd_falling_edge_count[0], rxd_falling_edge_count[1]);
      status_words_flat[23*32 +: 32] = pack_low16(rxd_falling_edge_count[2], rxd_falling_edge_count[3]);
    end
  end
endmodule
