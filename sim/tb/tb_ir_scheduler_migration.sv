`timescale 1ns/1ps
module tb_ir_scheduler_migration;
  logic clk=0; always #5 clk=~clk;
  logic rst_n, clear_counters, state_reset;
  logic [63:0] weights;
  logic [7:0] active_mask, lane_ready, lane_health, mapping_valid;
  logic [7:0] frame_admission, lane_tx_permit, duty_headroom, fault_free;
  logic global_permit, endpoint_armed, tx_kill, path_epoch_valid;
  logic [15:0] receiver_credit, path_epoch, request_cost;
  logic request_valid, request_ready, request_retry;
  logic [5:0] request_entry;
  logic [2:0] request_priority, request_last_lane;
  logic decision_valid, decision_ready, decision_admit;
  logic [5:0] decision_entry;
  logic [2:0] decision_lane;
  logic [15:0] decision_path_epoch;
  logic [3:0] defer_reason, migration_reason;
  logic [255:0] scheduled_frames, scheduled_bytes, retry_counts, migration_counts;
  logic [31:0] maximum_starvation;
  logic entry_valid, entry_acked, retry_pending, scheduler_admit;
  logic [2:0] last_lane, scheduler_lane, migrated_lane;
  logic [7:0] eligible_mask;
  logic migration_allowed, migration_required;
  logic [3:0] migration_gate_reason;
  integer lane_tally[0:7];

  ir_health_weighted_scheduler #(.LANE_COUNT(8), .ENTRY_WIDTH(6), .STARVATION_BOUND(64)) dut (
    .clk, .rst_n, .clear_counters_i(clear_counters), .state_reset_i(state_reset),
    .lane_weights_i(weights),
    .active_lane_mask_i(active_mask), .lane_ready_i(lane_ready), .lane_health_i(lane_health),
    .mapping_valid_i(mapping_valid), .frame_admission_i(frame_admission),
    .lane_tx_permit_i(lane_tx_permit), .duty_headroom_i(duty_headroom),
    .fault_free_i(fault_free), .global_permit_effective_i(global_permit),
    .endpoint_armed_i(endpoint_armed), .tx_kill_active_i(tx_kill),
    .path_epoch_valid_i(path_epoch_valid), .receiver_credit_i(receiver_credit),
    .path_epoch_i(path_epoch), .request_valid_i(request_valid),
    .request_ready_o(request_ready), .request_entry_i(request_entry),
    .request_cost_bytes_i(request_cost), .request_priority_i(request_priority),
    .request_retry_i(request_retry), .request_last_lane_i(request_last_lane),
    .decision_valid_o(decision_valid), .decision_ready_i(decision_ready),
    .decision_admit_o(decision_admit), .decision_entry_o(decision_entry),
    .decision_lane_o(decision_lane), .decision_path_epoch_o(decision_path_epoch),
    .decision_defer_reason_o(defer_reason),
    .decision_migration_reason_o(migration_reason), .scheduled_frames_o(scheduled_frames),
    .scheduled_bytes_o(scheduled_bytes), .retry_count_o(retry_counts),
    .migration_count_o(migration_counts), .maximum_starvation_o(maximum_starvation)
  );
  ir_retry_migration #(.LANE_COUNT(8)) migration_gate (
    .entry_valid_i(entry_valid), .entry_acked_i(entry_acked),
    .retry_pending_i(retry_pending), .last_lane_i(last_lane),
    .eligible_lane_mask_i(eligible_mask), .scheduler_lane_i(scheduler_lane),
    .scheduler_admit_i(scheduler_admit), .migration_allowed_o(migration_allowed),
    .migration_required_o(migration_required), .migrated_lane_o(migrated_lane),
    .migration_reason_o(migration_gate_reason)
  );

  task automatic check_expect(input logic condition, input string message);
    if(!condition) $fatal(1,"SCHED_EXPECT_FAIL: %s",message);
  endtask
  task automatic issue_once(output logic admitted, output logic [2:0] lane,
                            output logic [3:0] reason);
    integer timeout;
    begin
      @(negedge clk); request_valid=1;
      while(!request_ready) @(negedge clk);
      @(posedge clk); #1; request_valid=0;
      timeout=0;
      while(!decision_valid&&timeout<8) begin
        @(posedge clk); #1; timeout=timeout+1;
      end
      check_expect(decision_valid,"scheduler must return a bounded decision");
      admitted=decision_admit; lane=decision_lane; reason=defer_reason;
      @(posedge clk); #1;
    end
  endtask
  task automatic issue_admitted(output logic [2:0] lane);
    logic admitted; logic [3:0] reason; integer attempts;
    begin
      admitted=0; attempts=0;
      while(!admitted && attempts<4) begin
        issue_once(admitted,lane,reason); attempts=attempts+1;
      end
      check_expect(admitted,"eligible request must be admitted after bounded deficit refill");
    end
  endtask

  initial begin
    rst_n=0; clear_counters=0; state_reset=0; weights=64'h0101010101010101;
    active_mask=8'hff; lane_ready=8'hff; lane_health=8'hff; mapping_valid=8'hff;
    frame_admission=8'hff; lane_tx_permit=8'hff; duty_headroom=8'hff; fault_free=8'hff;
    global_permit=1; endpoint_armed=1; tx_kill=0; path_epoch_valid=1;
    receiver_credit=64; path_epoch=16'd12; request_valid=0; request_entry=0;
    request_cost=16'd100; request_priority=0; request_retry=0; request_last_lane=0;
    decision_ready=1; entry_valid=1; entry_acked=0; retry_pending=1; last_lane=0;
    eligible_mask=8'hff; scheduler_lane=3; scheduler_admit=1;
    for(int lane=0;lane<8;lane++) lane_tally[lane]=0;
    repeat(3) @(posedge clk); rst_n=1; @(posedge clk); #1;

    for(int request=0;request<512;request++) begin
      logic [2:0] lane;
      request_entry=request[5:0];
      issue_admitted(lane); lane_tally[lane]=lane_tally[lane]+1;
    end
    for(int lane=0;lane<8;lane++)
      check_expect(lane_tally[lane]>=63 && lane_tally[lane]<=65,
             "equal lanes remain fair within one decision");
    check_expect(maximum_starvation<16,"healthy lane starvation remains explicitly bounded");

    // Reset the decision/deficit state at an object boundary, then prove both
    // unequal-weight directions directly in RTL rather than relying only on
    // the Python reference model.
    @(negedge clk); state_reset=1; clear_counters=1;
    @(posedge clk); #1; state_reset=0; clear_counters=0;
    weights=64'h0101010101010301; active_mask=8'h03;
    for(int lane=0;lane<8;lane++) lane_tally[lane]=0;
    for(int request=0;request<512;request++) begin
      logic [2:0] lane;
      request_entry=request[5:0];
      issue_admitted(lane); lane_tally[lane]=lane_tally[lane]+1;
    end
    $display("SCHED_WEIGHT_1_TO_3_COUNTS=%0d,%0d", lane_tally[0], lane_tally[1]);
    check_expect(lane_tally[1] >= 3*lane_tally[0]-4 &&
                 lane_tally[1] <= 3*lane_tally[0]+4,
                 "1:3 weighted byte-cost service ratio");

    @(negedge clk); state_reset=1; clear_counters=1;
    @(posedge clk); #1; state_reset=0; clear_counters=0;
    weights=64'h0101010101010103;
    for(int lane=0;lane<8;lane++) lane_tally[lane]=0;
    for(int request=0;request<512;request++) begin
      logic [2:0] lane;
      request_entry=request[5:0];
      issue_admitted(lane); lane_tally[lane]=lane_tally[lane]+1;
    end
    $display("SCHED_WEIGHT_3_TO_1_COUNTS=%0d,%0d", lane_tally[0], lane_tally[1]);
    check_expect(lane_tally[0] >= 3*lane_tally[1]-4 &&
                 lane_tally[0] <= 3*lane_tally[1]+4,
                 "3:1 weighted byte-cost service ratio");

    weights=64'h0101010101010101; active_mask=8'hff;

    lane_health[0]=0; duty_headroom[1]=0; mapping_valid[2]=0; lane_tx_permit[3]=0;
    repeat(32) begin
      logic [2:0] lane;
      issue_admitted(lane);
      check_expect(lane>=4,"fault/duty/mapping/permit-ineligible lanes are isolated");
    end
    global_permit=0;
    begin logic admitted; logic [2:0] lane; logic [3:0] reason;
      issue_once(admitted,lane,reason);
      check_expect(!admitted && reason==1,"GLOBAL_PERMIT low fails closed");
    end
    global_permit=1;

    // A retry must use path diversity whenever another eligible lane exists.
    // This prevents a module-local outage from consuming every bounded retry
    // on the same physical path.  The one-lane degraded case must still make
    // progress on its sole remaining lane.
    lane_health=8'hff; duty_headroom=8'hff; mapping_valid=8'hff;
    lane_tx_permit=8'hff; lane_ready=8'hff; frame_admission=8'hff;
    fault_free=8'hff;
    @(negedge clk); state_reset=1; clear_counters=1;
    @(posedge clk); #1; state_reset=0; clear_counters=0;
    active_mask=8'h07; request_retry=1; request_last_lane=3'd1;
    begin logic [2:0] lane;
      issue_admitted(lane);
      check_expect(lane != 3'd1,
                   "retry selects an alternate healthy lane when available");
      check_expect(migration_reason == 4'd1,
                   "alternate retry is explicitly classified as migration");
      check_expect(migration_counts[lane*32 +: 32] == 32'd1,
                   "alternate retry increments its destination migration counter");
    end

    @(negedge clk); state_reset=1; clear_counters=1;
    @(posedge clk); #1; state_reset=0; clear_counters=0;
    active_mask=8'h02; request_retry=1; request_last_lane=3'd1;
    begin logic [2:0] lane;
      issue_admitted(lane);
      check_expect(lane == 3'd1,
                   "single-lane degradation permits retry on the sole lane");
      check_expect(migration_reason == 4'd0 && migration_counts == '0,
                   "sole-lane fallback is not misclassified as migration");
    end
    request_retry=0; active_mask=8'hff;

    #1; check_expect(migration_allowed && migration_required && migrated_lane==3,
               "unacknowledged retry may migrate to healthy scheduler lane");
    entry_acked=1; #1;
    check_expect(!migration_allowed && !migration_required && migration_gate_reason==2,
           "ACKed entry can never migrate");
    entry_acked=0; eligible_mask=0; #1;
    check_expect(migration_gate_reason==3,"all-lanes-unavailable defer reason is explicit");
    $display("P8D_HEALTH_AWARE_WEIGHTED_SCHEDULER_PASS=1");
    $display("P8D_SCHEDULER_FAIRNESS_PASS=1");
    $display("P8D_SCHEDULER_UNEQUAL_WEIGHT_PASS=1");
    $display("P8D_RETRY_ALTERNATE_LANE_PASS=1");
    $display("P8D_RETRY_MIGRATION_ACKED_BLOCK_PASS=1");
    $display("TB_IR_SCHEDULER_MIGRATION_PASS=1");
    $finish;
  end
endmodule
