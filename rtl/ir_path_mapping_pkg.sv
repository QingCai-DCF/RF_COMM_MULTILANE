`timescale 1ns/1ps
package ir_path_mapping_pkg;
  localparam logic [1:0] DIRECTION_UNKNOWN = 2'd0;
  localparam logic [1:0] DIRECTION_STOPPED = 2'd1;
  localparam logic [1:0] DIRECTION_FORWARD = 2'd2;
  localparam logic [1:0] DIRECTION_REVERSE = 2'd3;

  function automatic logic [4:0] current_fixed_index(
    input logic [4:0] m0,
    input integer lane
  );
    integer value;
    begin
      value = m0 + 4 * lane;
      current_fixed_index = value[4:0];
    end
  endfunction

  function automatic logic [4:0] candidate_fixed_index(
    input logic [4:0] m0,
    input integer lane,
    input logic [1:0] direction
  );
    logic [4:0] current_value;
    begin
      current_value = current_fixed_index(m0, lane);
      case (direction)
        DIRECTION_FORWARD: candidate_fixed_index = current_value + 5'd1;
        DIRECTION_REVERSE: candidate_fixed_index = current_value - 5'd1;
        default: candidate_fixed_index = current_value;
      endcase
    end
  endfunction

  function automatic logic [2:0] fixed_bank(input logic [4:0] fixed_index);
    fixed_bank = fixed_index[4:2];
  endfunction

  function automatic logic [1:0] fixed_slot(input logic [4:0] fixed_index);
    fixed_slot = fixed_index[1:0];
  endfunction

  function automatic logic mapping_is_permutation(input logic [39:0] fixed_flat);
    integer i;
    integer j;
    logic [4:0] a;
    logic [4:0] b;
    logic [2:0] bank_a;
    logic [2:0] bank_b;
    begin
      mapping_is_permutation = 1'b1;
      for (i = 0; i < 8; i = i + 1) begin
        a = fixed_flat[i*5 +: 5];
        bank_a = fixed_bank(a);
        for (j = i + 1; j < 8; j = j + 1) begin
          b = fixed_flat[j*5 +: 5];
          bank_b = fixed_bank(b);
          if ((a == b) || (bank_a == bank_b))
            mapping_is_permutation = 1'b0;
        end
      end
    end
  endfunction
endpackage
