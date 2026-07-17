`timescale 1ns/1ps
module ir_path_mapping_engine (
  input  logic        clk,
  input  logic        rst_n,
  input  logic [4:0]  phase_m0,
  input  logic        phase_valid,
  input  logic [1:0]  direction,
  input  logic        direction_valid,
  input  logic        prepare_request,
  input  logic        commit_event,
  output logic        prepare_ready,
  output logic        prepare_reject,
  output logic        shadow_valid,
  output logic        shadow_context_match,
  output logic        mapping_checks_pass,
  output logic [39:0] shadow_current_fixed,
  output logic [39:0] shadow_candidate_fixed,
  output logic [23:0] shadow_current_bank,
  output logic [23:0] shadow_candidate_bank,
  output logic [15:0] shadow_current_slot,
  output logic [15:0] shadow_candidate_slot,
  output logic        active_valid,
  output logic [39:0] active_current_fixed,
  output logic [39:0] active_candidate_fixed,
  output logic [23:0] active_current_bank,
  output logic [23:0] active_candidate_bank,
  output logic [15:0] active_current_slot,
  output logic [15:0] active_candidate_slot
);
  import ir_path_mapping_pkg::*;

  logic [4:0] shadow_m0;
  logic [1:0] shadow_direction;
  logic [39:0] computed_current_fixed;
  logic [39:0] computed_candidate_fixed;
  logic [23:0] computed_current_bank;
  logic [23:0] computed_candidate_bank;
  logic [15:0] computed_current_slot;
  logic [15:0] computed_candidate_slot;
  logic computed_valid;
  integer lane;
  logic [4:0] current_index;
  logic [4:0] candidate_index;

  always_comb begin
    computed_current_fixed = '0;
    computed_candidate_fixed = '0;
    computed_current_bank = '0;
    computed_candidate_bank = '0;
    computed_current_slot = '0;
    computed_candidate_slot = '0;
    for (lane = 0; lane < 8; lane = lane + 1) begin
      current_index = current_fixed_index(phase_m0, lane);
      candidate_index = candidate_fixed_index(phase_m0, lane, direction);
      computed_current_fixed[lane*5 +: 5] = current_index;
      computed_candidate_fixed[lane*5 +: 5] = candidate_index;
      computed_current_bank[lane*3 +: 3] = fixed_bank(current_index);
      computed_candidate_bank[lane*3 +: 3] = fixed_bank(candidate_index);
      computed_current_slot[lane*2 +: 2] = fixed_slot(current_index);
      computed_candidate_slot[lane*2 +: 2] = fixed_slot(candidate_index);
    end
    computed_valid = phase_valid && direction_valid &&
      ((direction == DIRECTION_FORWARD) || (direction == DIRECTION_REVERSE)) &&
      mapping_is_permutation(computed_current_fixed) &&
      mapping_is_permutation(computed_candidate_fixed);
  end

  always_comb begin
    shadow_context_match = shadow_valid && phase_valid && direction_valid &&
      (shadow_m0 == phase_m0) && (shadow_direction == direction);
    mapping_checks_pass = shadow_context_match &&
      mapping_is_permutation(shadow_current_fixed) &&
      mapping_is_permutation(shadow_candidate_fixed);
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      prepare_ready <= 1'b0;
      prepare_reject <= 1'b0;
      shadow_valid <= 1'b0;
      shadow_m0 <= '0;
      shadow_direction <= DIRECTION_UNKNOWN;
      shadow_current_fixed <= '0;
      shadow_candidate_fixed <= '0;
      shadow_current_bank <= '0;
      shadow_candidate_bank <= '0;
      shadow_current_slot <= '0;
      shadow_candidate_slot <= '0;
      active_valid <= 1'b0;
      active_current_fixed <= '0;
      active_candidate_fixed <= '0;
      active_current_bank <= '0;
      active_candidate_bank <= '0;
      active_current_slot <= '0;
      active_candidate_slot <= '0;
    end else begin
      prepare_ready <= 1'b0;
      prepare_reject <= 1'b0;
      if (prepare_request) begin
        if (computed_valid) begin
          shadow_m0 <= phase_m0;
          shadow_direction <= direction;
          shadow_current_fixed <= computed_current_fixed;
          shadow_candidate_fixed <= computed_candidate_fixed;
          shadow_current_bank <= computed_current_bank;
          shadow_candidate_bank <= computed_candidate_bank;
          shadow_current_slot <= computed_current_slot;
          shadow_candidate_slot <= computed_candidate_slot;
          shadow_valid <= 1'b1;
          prepare_ready <= 1'b1;
        end else begin
          shadow_valid <= 1'b0;
          prepare_reject <= 1'b1;
        end
      end else if (shadow_valid && !shadow_context_match) begin
        shadow_valid <= 1'b0;
      end

      if (commit_event && mapping_checks_pass) begin
        active_current_fixed <= shadow_current_fixed;
        active_candidate_fixed <= shadow_candidate_fixed;
        active_current_bank <= shadow_current_bank;
        active_candidate_bank <= shadow_candidate_bank;
        active_current_slot <= shadow_current_slot;
        active_candidate_slot <= shadow_candidate_slot;
        active_valid <= 1'b1;
        shadow_valid <= 1'b0;
      end
    end
  end
endmodule
