`timescale 1ns/1ps
module ir_phase_validity_guard (
  input  logic        clk,
  input  logic        rst_n,
  input  logic        phase_valid,
  input  logic        speed_valid,
  input  logic [9:0]  speed_abs_rpm,
  input  logic        direction_valid,
  input  logic [1:0]  direction,
  input  logic [15:0] phase_data_age_us,
  input  logic [31:0] phase_uncertainty_mdeg,
  input  logic [15:0] prepare_latency_us,
  input  logic [15:0] commit_latency_us,
  input  logic [15:0] max_phase_data_age_us,
  input  logic [31:0] uncertainty_budget_mdeg,
  input  logic        encoder_fault,
  input  logic        mapping_readback_match,
  input  logic        epoch_match,
  input  logic        mapping_fresh,
  output logic [31:0] phase_age_motion_mdeg,
  output logic [31:0] prepare_motion_mdeg,
  output logic [31:0] commit_motion_mdeg,
  output logic [31:0] total_effective_phase_uncertainty_mdeg,
  output logic        phase_contract_valid,
  output logic        reversal_detected,
  output logic        acquisition,
  output logic        tx_admission_allowed
);
  import ir_path_mapping_pkg::*;
  logic locked;
  logic [1:0] last_motion_direction;
  logic moving_direction_valid;
  logic stopped_direction_valid;
  logic base_valid;

  always_comb begin
    phase_age_motion_mdeg = (phase_data_age_us * 32'd36 + 32'd9) / 32'd10;
    prepare_motion_mdeg = (prepare_latency_us * 32'd36 + 32'd9) / 32'd10;
    commit_motion_mdeg = (commit_latency_us * 32'd36 + 32'd9) / 32'd10;
    total_effective_phase_uncertainty_mdeg = phase_uncertainty_mdeg +
      phase_age_motion_mdeg + prepare_motion_mdeg + commit_motion_mdeg;
    moving_direction_valid = direction_valid &&
      ((direction == DIRECTION_FORWARD) || (direction == DIRECTION_REVERSE));
    stopped_direction_valid = direction_valid && (direction == DIRECTION_STOPPED);
    reversal_detected = moving_direction_valid &&
      ((last_motion_direction == DIRECTION_FORWARD && direction == DIRECTION_REVERSE) ||
       (last_motion_direction == DIRECTION_REVERSE && direction == DIRECTION_FORWARD));
    base_valid = phase_valid && speed_valid && !encoder_fault && mapping_readback_match &&
      epoch_match && (phase_data_age_us <= max_phase_data_age_us) &&
      (total_effective_phase_uncertainty_mdeg <= uncertainty_budget_mdeg) &&
      (((speed_abs_rpm == 0) && stopped_direction_valid) ||
       ((speed_abs_rpm != 0) && moving_direction_valid));
    phase_contract_valid = base_valid && !reversal_detected;
    acquisition = !locked;
    tx_admission_allowed = locked && phase_contract_valid && mapping_fresh;
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      locked <= 1'b0;
      last_motion_direction <= DIRECTION_UNKNOWN;
    end else begin
      if (moving_direction_valid)
        last_motion_direction <= direction;
      if (!phase_contract_valid || !mapping_fresh)
        locked <= 1'b0;
      else
        locked <= 1'b1;
    end
  end
endmodule
