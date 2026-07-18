`timescale 1ns/1ps
`default_nettype none
`include "generated/tfdu_safety_config.svh"

// Exact per-physical-module clock-aligned sliding-window accountant. The
// history RAM advances every clock, including while permit is low, disarmed,
// or SD is high. It is never cleared by those state changes.
module ir_tfdu_exact_duty_accountant #(
  parameter integer CLOCK_HZ = `TFDU_SAFETY_CANONICAL_CLOCK_HZ,
  parameter integer WINDOW_US = `TFDU_SAFETY_ROLLING_WINDOW_US,
  parameter integer HARD_PERCENT_STRICT_LT = `TFDU_SAFETY_HARD_PERCENT_STRICT_LT,
  parameter integer TARGET_PERCENT_MAX = `TFDU_SAFETY_TARGET_PERCENT_MAX
) (
  input  wire         clk,
  input  wire         rst_n,
  input  wire         history_invalidate_i,
  input  wire         safety_fault_clear_i,
  input  wire         telemetry_clear_i,
  input  wire         charge_i,
  input  wire         target_request_i,
  output wire         target_admit_next_o,
  output wire         hard_violation_next_o,
  output reg  [31:0]  rolling_high_cycles_o,
  output reg  [31:0]  rolling_high_cycles_max_seen_o,
  output wire [31:0]  rolling_window_cycles_o,
  output wire [31:0]  hard_limit_cycles_o,
  output wire [31:0]  target_limit_cycles_o,
  output wire [31:0]  duty_headroom_cycles_o,
  output wire         duty_target_throttle_o,
  output reg  [31:0]  duty_target_throttle_count_o,
  output reg          duty_hard_fault_o,
  output reg  [31:0]  duty_hard_fault_count_o,
  output reg          duty_history_valid_o,
  output wire         duty_recovery_cooldown_active_o,
  output wire [31:0]  duty_recovery_cooldown_remaining_o,
  output reg  [31:0]  actual_or_conservative_charge_count_o
);
  localparam longint unsigned WINDOW_PRODUCT = CLOCK_HZ * WINDOW_US;
  localparam integer WINDOW_CYCLES = WINDOW_PRODUCT / 1_000_000;
  localparam longint unsigned HARD_NUMERATOR = WINDOW_CYCLES * HARD_PERCENT_STRICT_LT;
  localparam integer HARD_MAX_HIGH_CYCLES = (HARD_NUMERATOR - 1) / 100;
  localparam longint unsigned TARGET_NUMERATOR = WINDOW_CYCLES * TARGET_PERCENT_MAX;
  localparam integer TARGET_MAX_HIGH_CYCLES = TARGET_NUMERATOR / 100;
  localparam integer PTR_W = (WINDOW_CYCLES <= 1) ? 1 : $clog2(WINDOW_CYCLES);

  // One synchronous prefetch plus one write port maps to block RAM on Xilinx.
  (* ram_style = "block" *) reg history_mem [0:WINDOW_CYCLES-1];
  reg [PTR_W-1:0] history_ptr_q;
  reg             outgoing_bit_q;
  reg [31:0]      cooldown_cycles_q;
  wire [PTR_W-1:0] next_history_ptr;
  wire             history_write_bit;
  wire [32:0] rolling_without_outgoing;
  wire [32:0] rolling_next;

  assign next_history_ptr =
      (history_ptr_q == WINDOW_CYCLES-1) ? {PTR_W{1'b0}} : history_ptr_q + 1'b1;
  // The history RAM has an unconditional write and read on every clock.  Its
  // enable and output-register reset pins therefore cannot be driven from an
  // asynchronously asserted endpoint reset.  During reset/invalidation the
  // write data is zero and the full-window cooldown makes any stale read value
  // unobservable before accounting is re-enabled.
  assign history_write_bit = rst_n && duty_history_valid_o &&
      !history_invalidate_i && !safety_fault_clear_i && charge_i;
  assign rolling_without_outgoing = {1'b0, rolling_high_cycles_o} - outgoing_bit_q;
  assign rolling_next = rolling_without_outgoing + charge_i;
  assign target_admit_next_o = duty_history_valid_o && !duty_hard_fault_o &&
      (rolling_next < TARGET_MAX_HIGH_CYCLES);
  assign hard_violation_next_o = duty_history_valid_o &&
      (rolling_next > HARD_MAX_HIGH_CYCLES);
  assign duty_target_throttle_o = target_request_i && duty_history_valid_o &&
      !duty_hard_fault_o && !target_admit_next_o;
  assign rolling_window_cycles_o = WINDOW_CYCLES;
  assign hard_limit_cycles_o = HARD_MAX_HIGH_CYCLES;
  assign target_limit_cycles_o = TARGET_MAX_HIGH_CYCLES;
  assign duty_headroom_cycles_o =
      (rolling_high_cycles_o < TARGET_MAX_HIGH_CYCLES) ?
      (TARGET_MAX_HIGH_CYCLES - rolling_high_cycles_o) : 32'd0;
  assign duty_recovery_cooldown_active_o = !duty_history_valid_o;
  assign duty_recovery_cooldown_remaining_o =
      duty_history_valid_o ? 32'd0 : (WINDOW_CYCLES - cooldown_cycles_q);

  initial begin
    if (WINDOW_PRODUCT == 0 || (WINDOW_PRODUCT % 1_000_000) != 0)
      $fatal(1, "P8C WINDOW_CYCLES conversion must be exact and nonzero");
    if (TARGET_PERCENT_MAX <= 0 || TARGET_PERCENT_MAX >= HARD_PERCENT_STRICT_LT)
      $fatal(1, "P8C target percentage must be below strict hard percentage");
    if ((HARD_MAX_HIGH_CYCLES * 100) >= (WINDOW_CYCLES * HARD_PERCENT_STRICT_LT))
      $fatal(1, "P8C strict hard limit integer calculation failed");
    if ((TARGET_MAX_HIGH_CYCLES * 100) > (WINDOW_CYCLES * TARGET_PERCENT_MAX))
      $fatal(1, "P8C target integer calculation failed");
  end

  // Keep the RAM port unconditional and purely synchronous so Vivado can
  // infer block RAM without reset/enable control pins sourced by async-reset
  // logic.  No reset is required on outgoing_bit_q: while the memory is being
  // zero-filled, duty_history_valid_o is false and all accounting outputs are
  // held at their safe cooldown values.
  always @(posedge clk) begin
    history_mem[history_ptr_q] <= history_write_bit;
    outgoing_bit_q <= history_mem[next_history_ptr];
  end

  // Accountant state uses a synchronous reset; the surrounding physical
  // wrapper and endpoint own the asynchronous Txd fail-low path.
  always @(posedge clk) begin
    if (!rst_n) begin
      history_ptr_q <= {PTR_W{1'b0}};
      cooldown_cycles_q <= 32'd0;
      rolling_high_cycles_o <= 32'd0;
      rolling_high_cycles_max_seen_o <= 32'd0;
      duty_target_throttle_count_o <= 32'd0;
      duty_hard_fault_o <= 1'b0;
      duty_hard_fault_count_o <= 32'd0;
      duty_history_valid_o <= 1'b0;
      actual_or_conservative_charge_count_o <= 32'd0;
    end else if (history_invalidate_i || safety_fault_clear_i) begin
      // Forgetting history is permitted only together with a complete TX-low
      // window. The physical safety wrapper forces charge_i/output low while
      // this refill is active.
      history_ptr_q <= {PTR_W{1'b0}};
      cooldown_cycles_q <= 32'd0;
      rolling_high_cycles_o <= 32'd0;
      duty_history_valid_o <= 1'b0;
      if (safety_fault_clear_i)
        duty_hard_fault_o <= 1'b0;
    end else if (!duty_history_valid_o) begin
      rolling_high_cycles_o <= 32'd0;
      if (cooldown_cycles_q == WINDOW_CYCLES-1) begin
        history_ptr_q <= {PTR_W{1'b0}};
        cooldown_cycles_q <= WINDOW_CYCLES;
        duty_history_valid_o <= 1'b1;
      end else begin
        history_ptr_q <= next_history_ptr;
        cooldown_cycles_q <= cooldown_cycles_q + 1'b1;
      end
    end else begin
      history_ptr_q <= next_history_ptr;
      rolling_high_cycles_o <= rolling_next[31:0];

      if (rolling_next > rolling_high_cycles_max_seen_o)
        rolling_high_cycles_max_seen_o <= rolling_next[31:0];
      if (charge_i)
        actual_or_conservative_charge_count_o <= actual_or_conservative_charge_count_o + 1'b1;
      if (duty_target_throttle_o)
        duty_target_throttle_count_o <= duty_target_throttle_count_o + 1'b1;
      if (hard_violation_next_o && !duty_hard_fault_o) begin
        duty_hard_fault_o <= 1'b1;
        duty_hard_fault_count_o <= duty_hard_fault_count_o + 1'b1;
      end
    end

    if (telemetry_clear_i) begin
      rolling_high_cycles_max_seen_o <= rolling_high_cycles_o;
      duty_target_throttle_count_o <= 32'd0;
      actual_or_conservative_charge_count_o <= 32'd0;
      // Sticky safety faults and their event counts intentionally survive.
    end
  end
endmodule

`default_nettype wire
