`timescale 1ns/1ps
`default_nettype none

// P10.1R per-module receive admission.  This block is a monitor/gate only:
// it has no path to GLOBAL_PERMIT, SD, Mode, Txd, the scheduler, or flow
// control.  Quarantine is triggered by the actual final physical Txd level,
// after every safety gate, rather than by a requested/scheduled transmission.
//
// The 64 MHz default is selected from the four-module hardware calibration
// run p10_1r_20260801T190357Z_38f83531_080a35e6_18287e66.  That run observed
// no post-TX raw edge in 1,000 samples on each module; 4,096 cycles therefore
// provide the frozen deterministic 64 us margin.  The separate 256-cycle idle
// qualification remains mandatory before admission reopens.
module p10_1r_rx_admission #(
  parameter integer MIN_POST_TX_GUARD_CYCLES = 4_096,
  parameter integer IDLE_QUALIFY_CYCLES = 256,
  parameter integer MAX_QUARANTINE_CYCLES = 131_072
) (
  input  wire        clk,
  input  wire        rst_n,
  input  wire        clear_counters_i,
  input  wire        receiver_enable_i,
  input  wire        final_physical_txd_i,
  input  wire        raw_rx_pulse_i,

  output wire        rx_frame_accept_enable_o,
  output wire        rx_decoder_clear_o,
  output wire        echo_quarantine_o,
  output wire        post_tx_guard_active_o,
  output reg  [31:0] raw_pulse_count_o,
  output reg  [31:0] raw_while_local_tx_count_o,
  output reg  [31:0] blanked_raw_pulse_count_o,
  output reg  [31:0] guard_total_cycles_o,
  output reg  [31:0] guard_current_cycles_o,
  output reg  [31:0] guard_max_cycles_o,
  output reg  [31:0] echo_tail_max_cycles_o,
  output reg  [31:0] decoder_clear_count_o,
  output reg  [31:0] overlap_violation_count_o,
  output reg  [31:0] admission_violation_count_o,
  output reg  [31:0] last_physical_txd_rise_o,
  output reg  [31:0] last_physical_txd_fall_o,
  output reg  [31:0] first_local_rxd_edge_after_tx_o,
  output reg  [31:0] last_local_rxd_edge_after_tx_o,
  output reg  [31:0] last_raw_rx_timestamp_o
);
  reg quarantine_q;
  reg fail_closed_q;
  reg raw_rx_d_q;
  reg final_txd_d_q;
  reg decoder_clear_d_q;
  reg saw_post_tx_raw_q;
  reg [31:0] timestamp_q;
  reg [31:0] elapsed_q;
  reg [31:0] idle_q;

  // Telemetry counters are diagnostic evidence and must never alias a long
  // run to zero. Timestamps intentionally wrap modulo 2^32; every monotonic
  // count and duration instead saturates.
  function automatic [31:0] sat_inc32(input [31:0] value);
    begin
      sat_inc32 = (&value) ? value : value + 32'd1;
    end
  endfunction

  wire raw_rise = raw_rx_pulse_i && !raw_rx_d_q;
  wire [31:0] elapsed_next_saturated = sat_inc32(elapsed_q);
  wire [31:0] idle_next_saturated = sat_inc32(idle_q);
  // The direct final-Txd term makes overlap structurally impossible even on
  // the first cycle of a newly observed physical pulse.
  assign rx_frame_accept_enable_o = receiver_enable_i && !quarantine_q &&
      !fail_closed_q && !final_physical_txd_i;
  assign rx_decoder_clear_o = !rx_frame_accept_enable_o;
  assign echo_quarantine_o = quarantine_q || fail_closed_q ||
      final_physical_txd_i;
  assign post_tx_guard_active_o = echo_quarantine_o;

  initial begin
    if (MIN_POST_TX_GUARD_CYCLES < 1)
      $error("MIN_POST_TX_GUARD_CYCLES must be positive");
    if (IDLE_QUALIFY_CYCLES < 1)
      $error("IDLE_QUALIFY_CYCLES must be positive");
    if (MAX_QUARANTINE_CYCLES <=
        MIN_POST_TX_GUARD_CYCLES + IDLE_QUALIFY_CYCLES)
      $error("MAX_QUARANTINE_CYCLES must exceed guard plus idle qualification");
  end

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      quarantine_q <= 1'b0;
      fail_closed_q <= 1'b0;
      raw_rx_d_q <= 1'b0;
      final_txd_d_q <= 1'b0;
      decoder_clear_d_q <= 1'b1;
      saw_post_tx_raw_q <= 1'b0;
      timestamp_q <= 32'd0;
      elapsed_q <= 32'd0;
      idle_q <= 32'd0;
      raw_pulse_count_o <= 32'd0;
      raw_while_local_tx_count_o <= 32'd0;
      blanked_raw_pulse_count_o <= 32'd0;
      guard_total_cycles_o <= 32'd0;
      guard_current_cycles_o <= 32'd0;
      guard_max_cycles_o <= 32'd0;
      echo_tail_max_cycles_o <= 32'd0;
      decoder_clear_count_o <= 32'd0;
      overlap_violation_count_o <= 32'd0;
      admission_violation_count_o <= 32'd0;
      last_physical_txd_rise_o <= 32'd0;
      last_physical_txd_fall_o <= 32'd0;
      first_local_rxd_edge_after_tx_o <= 32'd0;
      last_local_rxd_edge_after_tx_o <= 32'd0;
      last_raw_rx_timestamp_o <= 32'd0;
    end else begin
      timestamp_q <= timestamp_q + 1'b1;
      raw_rx_d_q <= raw_rx_pulse_i;
      final_txd_d_q <= final_physical_txd_i;
      decoder_clear_d_q <= rx_decoder_clear_o;

      if (clear_counters_i) begin
        raw_pulse_count_o <= 32'd0;
        raw_while_local_tx_count_o <= 32'd0;
        blanked_raw_pulse_count_o <= 32'd0;
        guard_total_cycles_o <= 32'd0;
        guard_max_cycles_o <= 32'd0;
        echo_tail_max_cycles_o <= 32'd0;
        decoder_clear_count_o <= 32'd0;
        overlap_violation_count_o <= 32'd0;
        admission_violation_count_o <= 32'd0;
        last_physical_txd_rise_o <= 32'd0;
        last_physical_txd_fall_o <= 32'd0;
        first_local_rxd_edge_after_tx_o <= 32'd0;
        last_local_rxd_edge_after_tx_o <= 32'd0;
        last_raw_rx_timestamp_o <= 32'd0;
      end

      if (final_physical_txd_i && !final_txd_d_q) begin
        last_physical_txd_rise_o <= timestamp_q;
        saw_post_tx_raw_q <= 1'b0;
      end
      if (!final_physical_txd_i && final_txd_d_q)
        last_physical_txd_fall_o <= timestamp_q;

      if (raw_rise) begin
        raw_pulse_count_o <= clear_counters_i ? 32'd1 :
            sat_inc32(raw_pulse_count_o);
        last_raw_rx_timestamp_o <= timestamp_q;
        if ((quarantine_q || fail_closed_q) && !final_physical_txd_i) begin
          if (!saw_post_tx_raw_q)
            first_local_rxd_edge_after_tx_o <= timestamp_q;
          last_local_rxd_edge_after_tx_o <= timestamp_q;
          saw_post_tx_raw_q <= 1'b1;
        end
        if (final_physical_txd_i)
          raw_while_local_tx_count_o <= clear_counters_i ? 32'd1 :
              sat_inc32(raw_while_local_tx_count_o);
        if (!rx_frame_accept_enable_o)
          blanked_raw_pulse_count_o <= clear_counters_i ? 32'd1 :
              sat_inc32(blanked_raw_pulse_count_o);
      end

      if (rx_decoder_clear_o && !decoder_clear_d_q)
        decoder_clear_count_o <= clear_counters_i ? 32'd1 :
            sat_inc32(decoder_clear_count_o);

      // This assertion counter should remain zero by construction.  Keeping
      // it observable makes the hardware gate a direct check, not an
      // inference from accepted-frame counts.
      if (final_physical_txd_i && rx_frame_accept_enable_o)
        overlap_violation_count_o <= clear_counters_i ? 32'd1 :
            sat_inc32(overlap_violation_count_o);

      if (!receiver_enable_i) begin
        quarantine_q <= 1'b0;
        fail_closed_q <= 1'b0;
        elapsed_q <= 32'd0;
        idle_q <= 32'd0;
        guard_current_cycles_o <= 32'd0;
      end else if (final_physical_txd_i) begin
        quarantine_q <= 1'b1;
        elapsed_q <= 32'd0;
        idle_q <= 32'd0;
        guard_current_cycles_o <= 32'd0;
      end else if (quarantine_q || fail_closed_q) begin
        guard_total_cycles_o <= clear_counters_i ? 32'd1 :
            sat_inc32(guard_total_cycles_o);
        elapsed_q <= elapsed_next_saturated;
        guard_current_cycles_o <= elapsed_next_saturated;
        if (elapsed_next_saturated > guard_max_cycles_o)
          guard_max_cycles_o <= elapsed_next_saturated;

        if (raw_rise) begin
          idle_q <= 32'd0;
          if (elapsed_next_saturated > echo_tail_max_cycles_o)
            echo_tail_max_cycles_o <= elapsed_next_saturated;
        end else begin
          idle_q <= idle_next_saturated;
        end

        if (!fail_closed_q && !raw_rise &&
            elapsed_next_saturated >= MIN_POST_TX_GUARD_CYCLES &&
            idle_next_saturated >= IDLE_QUALIFY_CYCLES) begin
          quarantine_q <= 1'b0;
          elapsed_q <= 32'd0;
          idle_q <= 32'd0;
          guard_current_cycles_o <= 32'd0;
        end else if (!fail_closed_q &&
                     elapsed_next_saturated >= MAX_QUARANTINE_CYCLES) begin
          fail_closed_q <= 1'b1;
          admission_violation_count_o <= clear_counters_i ? 32'd1 :
              sat_inc32(admission_violation_count_o);
        end
      end else begin
        elapsed_q <= 32'd0;
        idle_q <= 32'd0;
        guard_current_cycles_o <= 32'd0;
      end
    end
  end
endmodule

`default_nettype wire
