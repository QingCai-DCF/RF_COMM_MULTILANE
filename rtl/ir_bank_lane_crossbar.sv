`timescale 1ns/1ps
module ir_bank_lane_crossbar #(
  parameter integer DATA_WIDTH = 16
) (
  input  logic                    mapping_valid,
  input  logic [23:0]             lane_current_bank,
  input  logic [23:0]             lane_candidate_bank,
  input  logic [8*DATA_WIDTH-1:0] bank_current_rx,
  input  logic [8*DATA_WIDTH-1:0] bank_candidate_rx,
  output logic [8*DATA_WIDTH-1:0] lane_current_rx,
  output logic [8*DATA_WIDTH-1:0] lane_candidate_rx,
  output logic [7:0]              lane_current_valid,
  output logic [7:0]              lane_candidate_valid,
  output logic [23:0]             bank_current_owner,
  output logic [23:0]             bank_candidate_owner,
  output logic [7:0]              bank_current_valid,
  output logic [7:0]              bank_candidate_valid,
  output logic [23:0]             bank_tx_owner,
  output logic [7:0]              bank_tx_owner_valid,
  output logic                    crossbar_valid
);
  integer lane;
  integer other;
  integer current_bank;
  integer candidate_bank;
  integer other_current_bank;
  integer other_candidate_bank;
  logic current_unique;
  logic candidate_unique;

  always_comb begin
    current_unique = mapping_valid;
    candidate_unique = mapping_valid;
    for (lane = 0; lane < 8; lane = lane + 1) begin
      current_bank = lane_current_bank[lane*3 +: 3];
      candidate_bank = lane_candidate_bank[lane*3 +: 3];
      if ((current_bank < 0) || (current_bank > 7) || (candidate_bank < 0) || (candidate_bank > 7)) begin
        current_unique = 1'b0;
        candidate_unique = 1'b0;
      end
      for (other = lane + 1; other < 8; other = other + 1) begin
        other_current_bank = lane_current_bank[other*3 +: 3];
        other_candidate_bank = lane_candidate_bank[other*3 +: 3];
        if (current_bank == other_current_bank)
          current_unique = 1'b0;
        if (candidate_bank == other_candidate_bank)
          candidate_unique = 1'b0;
      end
    end

    crossbar_valid = current_unique && candidate_unique;
    lane_current_rx = '0;
    lane_candidate_rx = '0;
    lane_current_valid = '0;
    lane_candidate_valid = '0;
    bank_current_owner = '0;
    bank_candidate_owner = '0;
    bank_current_valid = '0;
    bank_candidate_valid = '0;
    bank_tx_owner = '0;
    bank_tx_owner_valid = '0;
    if (crossbar_valid) begin
      for (lane = 0; lane < 8; lane = lane + 1) begin
        current_bank = lane_current_bank[lane*3 +: 3];
        candidate_bank = lane_candidate_bank[lane*3 +: 3];
        lane_current_rx[lane*DATA_WIDTH +: DATA_WIDTH] = bank_current_rx[current_bank*DATA_WIDTH +: DATA_WIDTH];
        lane_candidate_rx[lane*DATA_WIDTH +: DATA_WIDTH] = bank_candidate_rx[candidate_bank*DATA_WIDTH +: DATA_WIDTH];
        lane_current_valid[lane] = 1'b1;
        lane_candidate_valid[lane] = 1'b1;
        bank_current_owner[current_bank*3 +: 3] = lane[2:0];
        bank_candidate_owner[candidate_bank*3 +: 3] = lane[2:0];
        bank_current_valid[current_bank] = 1'b1;
        bank_candidate_valid[candidate_bank] = 1'b1;
        bank_tx_owner[current_bank*3 +: 3] = lane[2:0];
        bank_tx_owner_valid[current_bank] = 1'b1;
      end
    end
  end
endmodule
