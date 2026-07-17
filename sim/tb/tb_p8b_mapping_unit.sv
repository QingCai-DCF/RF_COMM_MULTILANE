`timescale 1ns/1ps

module tb_p8b_mapping_unit;
  import ir_path_mapping_pkg::*;

  logic clk = 1'b0;
  logic rst_n = 1'b0;
  always #5 clk = ~clk;

  logic [4:0] phase_m0;
  logic phase_valid;
  logic [1:0] direction;
  logic direction_valid;
  logic prepare_request;
  logic commit_request;
  logic frame_boundary;
  logic no_fatal_mapping_fault;
  logic prepare_ready;
  logic prepare_reject;
  logic shadow_valid;
  logic shadow_context_match;
  logic mapping_checks_pass;
  logic [39:0] shadow_current_fixed;
  logic [39:0] shadow_candidate_fixed;
  logic [23:0] shadow_current_bank;
  logic [23:0] shadow_candidate_bank;
  logic [15:0] shadow_current_slot;
  logic [15:0] shadow_candidate_slot;
  logic active_valid;
  logic [39:0] active_current_fixed;
  logic [39:0] active_candidate_fixed;
  logic [23:0] active_current_bank;
  logic [23:0] active_candidate_bank;
  logic [15:0] active_current_slot;
  logic [15:0] active_candidate_slot;
  logic commit_event;
  logic commit_accept;
  logic commit_reject;
  logic [2:0] commit_reject_reason;
  logic [3:0] path_epoch;
  logic [3:0] readback_epoch;
  logic [3:0] frame_epoch;
  logic [3:0] ack_epoch;
  logic [3:0] status_epoch;
  logic readback_epoch_current;
  logic frame_epoch_current;
  logic ack_epoch_current;
  logic status_epoch_current;

  logic [127:0] bank_current_rx;
  logic [127:0] bank_candidate_rx;
  logic [127:0] lane_current_rx;
  logic [127:0] lane_candidate_rx;
  logic [7:0] lane_current_valid;
  logic [7:0] lane_candidate_valid;
  logic [23:0] bank_current_owner;
  logic [23:0] bank_candidate_owner;
  logic [7:0] bank_current_valid;
  logic [7:0] bank_candidate_valid;
  logic [23:0] bank_tx_owner;
  logic [7:0] bank_tx_owner_valid;
  logic crossbar_valid;

  integer m0_i;
  integer dir_i;
  integer lane_i;
  integer bank_i;
  integer old_epoch;
  logic [39:0] old_active;
  logic [39:0] expected_shadow;

  ir_path_mapping_engine u_mapping (
    .clk(clk), .rst_n(rst_n), .phase_m0(phase_m0), .phase_valid(phase_valid),
    .direction(direction), .direction_valid(direction_valid), .prepare_request(prepare_request),
    .commit_event(commit_event), .prepare_ready(prepare_ready), .prepare_reject(prepare_reject),
    .shadow_valid(shadow_valid), .shadow_context_match(shadow_context_match),
    .mapping_checks_pass(mapping_checks_pass), .shadow_current_fixed(shadow_current_fixed),
    .shadow_candidate_fixed(shadow_candidate_fixed), .shadow_current_bank(shadow_current_bank),
    .shadow_candidate_bank(shadow_candidate_bank), .shadow_current_slot(shadow_current_slot),
    .shadow_candidate_slot(shadow_candidate_slot), .active_valid(active_valid),
    .active_current_fixed(active_current_fixed), .active_candidate_fixed(active_candidate_fixed),
    .active_current_bank(active_current_bank), .active_candidate_bank(active_candidate_bank),
    .active_current_slot(active_current_slot), .active_candidate_slot(active_candidate_slot)
  );

  ir_path_epoch_commit #(.EPOCH_WIDTH(4)) u_epoch (
    .clk(clk), .rst_n(rst_n), .commit_request(commit_request), .phase_valid(phase_valid),
    .shadow_valid(shadow_valid), .mapping_checks_pass(mapping_checks_pass),
    .quiet_or_frame_boundary(frame_boundary), .no_fatal_mapping_fault(no_fatal_mapping_fault),
    .readback_epoch(readback_epoch), .frame_epoch(frame_epoch), .ack_epoch(ack_epoch),
    .status_epoch(status_epoch), .commit_event(commit_event), .commit_accept(commit_accept),
    .commit_reject(commit_reject), .commit_reject_reason(commit_reject_reason),
    .path_epoch(path_epoch), .readback_epoch_current(readback_epoch_current),
    .frame_epoch_current(frame_epoch_current), .ack_epoch_current(ack_epoch_current),
    .status_epoch_current(status_epoch_current)
  );

  ir_bank_lane_crossbar #(.DATA_WIDTH(16)) u_crossbar (
    .mapping_valid(active_valid), .lane_current_bank(active_current_bank),
    .lane_candidate_bank(active_candidate_bank), .bank_current_rx(bank_current_rx),
    .bank_candidate_rx(bank_candidate_rx), .lane_current_rx(lane_current_rx),
    .lane_candidate_rx(lane_candidate_rx), .lane_current_valid(lane_current_valid),
    .lane_candidate_valid(lane_candidate_valid), .bank_current_owner(bank_current_owner),
    .bank_candidate_owner(bank_candidate_owner), .bank_current_valid(bank_current_valid),
    .bank_candidate_valid(bank_candidate_valid), .bank_tx_owner(bank_tx_owner),
    .bank_tx_owner_valid(bank_tx_owner_valid), .crossbar_valid(crossbar_valid)
  );

  task automatic check(input logic condition, input string message);
    if (!condition) begin
      $display("P8B_ASSERT_FAIL=%s", message);
      $fatal(1);
    end
  endtask

  task automatic do_prepare(input integer requested_m0, input logic [1:0] requested_direction);
    begin
      @(negedge clk);
      phase_m0 = requested_m0[4:0];
      direction = requested_direction;
      phase_valid = 1'b1;
      direction_valid = 1'b1;
      prepare_request = 1'b1;
      @(posedge clk); #1;
      check(prepare_ready && shadow_valid && mapping_checks_pass, "valid prepare must become ready");
      @(negedge clk);
      prepare_request = 1'b0;
    end
  endtask

  task automatic do_commit;
    begin
      old_epoch = path_epoch;
      old_active = active_current_fixed;
      expected_shadow = shadow_current_fixed;
      @(negedge clk);
      commit_request = 1'b1;
      #1;
      check(commit_event, "accepted request must expose commit event before edge");
      check(active_current_fixed == old_active, "active mapping changed before atomic edge");
      @(posedge clk); #1;
      check(commit_accept, "commit accept pulse missing");
      check(path_epoch == ((old_epoch + 1) & 15), "epoch did not increment exactly once");
      check(active_current_fixed == expected_shadow, "active mapping did not swap atomically");
      check(active_valid && !shadow_valid, "active/shadow validity wrong after commit");
      repeat (2) begin
        @(posedge clk); #1;
        check(path_epoch == ((old_epoch + 1) & 15), "stretched request double-incremented epoch");
        check(!commit_accept, "stretched request emitted duplicate accept");
      end
      @(negedge clk);
      commit_request = 1'b0;
      @(posedge clk); #1;
    end
  endtask

  initial begin
    phase_m0 = 0;
    phase_valid = 0;
    direction = DIRECTION_UNKNOWN;
    direction_valid = 0;
    prepare_request = 0;
    commit_request = 0;
    frame_boundary = 1;
    no_fatal_mapping_fault = 1;
    readback_epoch = 0;
    frame_epoch = 0;
    ack_epoch = 0;
    status_epoch = 0;
    bank_current_rx = '0;
    bank_candidate_rx = '0;
    for (bank_i = 0; bank_i < 8; bank_i = bank_i + 1) begin
      bank_current_rx[bank_i*16 +: 16] = 16'h1000 + bank_i;
      bank_candidate_rx[bank_i*16 +: 16] = 16'h2000 + bank_i;
    end

    repeat (3) @(posedge clk);
    rst_n = 1;
    @(posedge clk); #1;
    check(path_epoch == 0 && !active_valid, "reset state not deterministic");

    check(candidate_fixed_index(5'd3, 0, DIRECTION_FORWARD) == 5'd4, "q3 forward slot wrap");
    check(candidate_fixed_index(5'd31, 0, DIRECTION_FORWARD) == 5'd0, "s7 forward wrap");
    check(candidate_fixed_index(5'd0, 0, DIRECTION_REVERSE) == 5'd31, "s0 reverse wrap");
    check(candidate_fixed_index(5'd4, 0, DIRECTION_REVERSE) == 5'd3, "q0 reverse slot wrap");

    for (m0_i = 0; m0_i < 32; m0_i = m0_i + 1) begin
      for (dir_i = 0; dir_i < 2; dir_i = dir_i + 1) begin
        do_prepare(m0_i, (dir_i == 0) ? DIRECTION_FORWARD : DIRECTION_REVERSE);
        check(mapping_is_permutation(shadow_current_fixed), "current mapping not permutation");
        check(mapping_is_permutation(shadow_candidate_fixed), "candidate mapping not permutation");
        for (lane_i = 0; lane_i < 8; lane_i = lane_i + 1) begin
          check(shadow_current_fixed[lane_i*5 +: 5] == current_fixed_index(m0_i[4:0], lane_i), "current formula mismatch");
          check(shadow_candidate_fixed[lane_i*5 +: 5] == candidate_fixed_index(m0_i[4:0], lane_i, direction), "candidate formula mismatch");
          check(shadow_current_bank[lane_i*3 +: 3] == ((m0_i / 4 + lane_i) & 7), "current bank formula mismatch");
          check(shadow_current_slot[lane_i*2 +: 2] == (m0_i & 3), "current slot formula mismatch");
        end
        do_commit();
        #1;
        check(crossbar_valid, "crossbar invalid for a permutation");
        check(lane_current_valid == 8'hff && lane_candidate_valid == 8'hff, "lane validity incomplete");
        check(bank_current_valid == 8'hff && bank_candidate_valid == 8'hff, "bank ownership incomplete");
        check(bank_tx_owner_valid == 8'hff, "current TX owner missing");
        for (lane_i = 0; lane_i < 8; lane_i = lane_i + 1) begin
          check(lane_current_rx[lane_i*16 +: 16] == 16'h1000 + active_current_bank[lane_i*3 +: 3], "current data mux mismatch");
          check(lane_candidate_rx[lane_i*16 +: 16] == 16'h2000 + active_candidate_bank[lane_i*3 +: 3], "candidate data mux mismatch");
          check(bank_current_owner[active_current_bank[lane_i*3 +: 3]*3 +: 3] == lane_i[2:0], "current inverse owner mismatch");
          check(bank_candidate_owner[active_candidate_bank[lane_i*3 +: 3]*3 +: 3] == lane_i[2:0], "candidate inverse owner mismatch");
          $display("P8B_CROSSCHECK,%0d,%0d,%0d,%0d,%0d,%0d,%0d", m0_i, direction,
            bank_current_owner[active_current_bank[lane_i*3 +: 3]*3 +: 3],
            active_current_fixed[lane_i*5 +: 5], active_candidate_fixed[lane_i*5 +: 5],
            active_candidate_bank[lane_i*3 +: 3], active_candidate_slot[lane_i*2 +: 2]);
        end
      end
    end

    readback_epoch = path_epoch;
    frame_epoch = path_epoch;
    ack_epoch = path_epoch;
    status_epoch = path_epoch;
    #1;
    check(readback_epoch_current && frame_epoch_current && ack_epoch_current && status_epoch_current, "current metadata rejected");
    readback_epoch = path_epoch - 1'b1;
    frame_epoch = path_epoch - 1'b1;
    ack_epoch = path_epoch - 1'b1;
    status_epoch = path_epoch - 1'b1;
    #1;
    check(!readback_epoch_current && !frame_epoch_current && !ack_epoch_current && !status_epoch_current, "stale metadata accepted");

    old_epoch = path_epoch;
    @(negedge clk);
    phase_valid = 0;
    prepare_request = 1;
    @(posedge clk); #1;
    check(prepare_reject && !shadow_valid, "invalid prepare did not fail closed");
    @(negedge clk);
    prepare_request = 0;
    commit_request = 1;
    @(posedge clk); #1;
    check(commit_reject && path_epoch == old_epoch, "invalid commit changed epoch");
    @(negedge clk);
    commit_request = 0;
    phase_valid = 1;

    // Reset asserted during a pending request aborts both mapping and epoch deterministically.
    do_prepare(7, DIRECTION_FORWARD);
    @(negedge clk);
    commit_request = 1;
    rst_n = 0;
    @(posedge clk); #1;
    check(path_epoch == 0 && !active_valid && !shadow_valid, "reset during commit did not abort");
    @(negedge clk);
    commit_request = 0;
    rst_n = 1;

    $display("P8B_HDL_MAPPING_UNIT_PASS=1");
    $display("P8B_HDL_CROSSBAR_DATA_PASS=1");
    $display("P8B_HDL_FORWARD_REVERSE_WRAP_PASS=1");
    $display("P8B_HDL_PATH_EPOCH_ATOMICITY_PASS=1");
    $display("TB_P8B_MAPPING_UNIT_PASS=1");
    $finish;
  end
endmodule
