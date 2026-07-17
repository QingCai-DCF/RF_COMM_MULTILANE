`timescale 1ns/1ps
module tb_p8c_profile_matrix;
  import ir_path_mapping_pkg::*;

  logic clk = 1'b0;
  always #5 clk = ~clk;
  logic rst_n;

  logic permit2, arm2;
  logic [7:0] sel2, frame2, wave2;
  logic [1:0] tx2, selected_phys2, hist2, hard2, stuck2;
  logic [63:0] rolling2;
  logic armed2;

  logic permit8, arm8;
  logic [7:0] sel8, frame8, wave8;
  logic [7:0] tx8, selected_phys8, hist8, hard8, stuck8;
  logic [255:0] rolling8;
  logic armed8;

  logic permit32, arm32;
  logic [7:0] sel32, frame32, wave32;
  logic [31:0] tx32, selected_phys32, hist32, hard32, stuck32;
  logic [1023:0] rolling32;
  logic armed32, collision32;

  logic [4:0] phase_m0;
  logic [1:0] direction;
  logic phase_valid, direction_valid, prepare_request, commit_request;
  logic quiet_boundary;
  logic prepare_ready, prepare_reject, shadow_valid, shadow_context_match, mapping_checks_pass;
  logic [39:0] shadow_current_fixed, shadow_candidate_fixed;
  logic [23:0] shadow_current_bank, shadow_candidate_bank;
  logic [15:0] shadow_current_slot, shadow_candidate_slot;
  logic active_valid;
  logic [39:0] active_current_fixed, active_candidate_fixed;
  logic [23:0] active_current_bank, active_candidate_bank;
  logic [15:0] active_current_slot, active_candidate_slot;
  logic commit_event, commit_accept, commit_reject;
  logic [2:0] commit_reject_reason;
  logic [3:0] path_epoch;
  logic [31:0] logical_epoch32;

  ir_path_mapping_engine p8b_mapping (
    .clk, .rst_n, .phase_m0, .phase_valid, .direction, .direction_valid,
    .prepare_request, .commit_event, .prepare_ready, .prepare_reject,
    .shadow_valid, .shadow_context_match, .mapping_checks_pass,
    .shadow_current_fixed, .shadow_candidate_fixed, .shadow_current_bank,
    .shadow_candidate_bank, .shadow_current_slot, .shadow_candidate_slot,
    .active_valid, .active_current_fixed, .active_candidate_fixed,
    .active_current_bank, .active_candidate_bank, .active_current_slot,
    .active_candidate_slot
  );

  ir_path_epoch_commit #(.EPOCH_WIDTH(4)) p8b_epoch (
    .clk, .rst_n, .commit_request, .phase_valid, .shadow_valid,
    .mapping_checks_pass, .quiet_or_frame_boundary(quiet_boundary),
    .no_fatal_mapping_fault(1'b1), .readback_epoch(path_epoch),
    .frame_epoch(path_epoch), .ack_epoch(path_epoch), .status_epoch(path_epoch),
    .commit_event, .commit_accept, .commit_reject, .commit_reject_reason,
    .path_epoch, .readback_epoch_current(), .frame_epoch_current(),
    .ack_epoch_current(), .status_epoch_current()
  );

  ir_p8c_safety_integration #(
    .PHYSICAL_MODULE_COUNT(2), .FIXED_ENDPOINT(0),
    .CLOCK_HZ(1_000_000), .STARTUP_US(1), .WINDOW_US(100),
    .MAX_CONTINUOUS_HIGH_US(1)
  ) profile2 (
    .clk, .rst_n, .global_permit_i(permit2), .endpoint_arm_request_i(arm2),
    .endpoint_disarm_request_i(1'b0), .full_shutdown_request_i(1'b0),
    .safety_fault_clear_request_i(1'b0), .history_invalidate_i(1'b0),
    .active_mapping_valid_i(1'b1), .active_current_fixed_i('0),
    .active_current_bank_i('0), .active_path_epoch_i(32'd1),
    .logical_path_epoch_i(32'd1), .logical_selected_i(sel2),
    .logical_lane_tx_permit_i(8'hff), .logical_frame_admitted_i(frame2),
    .logical_txd_waveform_i(wave2), .receive_enable_i(2'b11),
    .bank_fault_i(2'b00), .rxd_i(2'b11), .physical_txd_out_o(tx2),
    .physical_sd_o(), .rx_active_o(), .physical_module_selected_o(selected_phys2),
    .global_permit_raw_safe_o(), .global_permit_sync_valid_o(),
    .endpoint_armed_o(armed2), .mapping_collision_o(),
    .duty_history_valid_mask_o(hist2), .rolling_high_cycles_flat_o(rolling2),
    .duty_hard_fault_mask_o(hard2), .stuck_high_fault_mask_o(stuck2)
  );

  ir_p8c_safety_integration #(
    .PHYSICAL_MODULE_COUNT(8), .FIXED_ENDPOINT(0),
    .CLOCK_HZ(1_000_000), .STARTUP_US(1), .WINDOW_US(100),
    .MAX_CONTINUOUS_HIGH_US(1)
  ) profile8 (
    .clk, .rst_n, .global_permit_i(permit8), .endpoint_arm_request_i(arm8),
    .endpoint_disarm_request_i(1'b0), .full_shutdown_request_i(1'b0),
    .safety_fault_clear_request_i(1'b0), .history_invalidate_i(1'b0),
    .active_mapping_valid_i(1'b1), .active_current_fixed_i('0),
    .active_current_bank_i('0), .active_path_epoch_i(32'd1),
    .logical_path_epoch_i(32'd1), .logical_selected_i(sel8),
    .logical_lane_tx_permit_i(8'hff), .logical_frame_admitted_i(frame8),
    .logical_txd_waveform_i(wave8), .receive_enable_i(8'hff),
    .bank_fault_i(8'h00), .rxd_i(8'hff), .physical_txd_out_o(tx8),
    .physical_sd_o(), .rx_active_o(), .physical_module_selected_o(selected_phys8),
    .global_permit_raw_safe_o(), .global_permit_sync_valid_o(),
    .endpoint_armed_o(armed8), .mapping_collision_o(),
    .duty_history_valid_mask_o(hist8), .rolling_high_cycles_flat_o(rolling8),
    .duty_hard_fault_mask_o(hard8), .stuck_high_fault_mask_o(stuck8)
  );

  ir_p8c_safety_integration #(
    .PHYSICAL_MODULE_COUNT(32), .FIXED_ENDPOINT(1),
    .CLOCK_HZ(1_000_000), .STARTUP_US(1), .WINDOW_US(100),
    .MAX_CONTINUOUS_HIGH_US(1)
  ) profile32 (
    .clk, .rst_n, .global_permit_i(permit32), .endpoint_arm_request_i(arm32),
    .endpoint_disarm_request_i(1'b0), .full_shutdown_request_i(1'b0),
    .safety_fault_clear_request_i(1'b0), .history_invalidate_i(1'b0),
    .active_mapping_valid_i(active_valid), .active_current_fixed_i(active_current_fixed),
    .active_current_bank_i(active_current_bank), .active_path_epoch_i({28'd0,path_epoch}),
    .logical_path_epoch_i(logical_epoch32), .logical_selected_i(sel32),
    .logical_lane_tx_permit_i(8'hff), .logical_frame_admitted_i(frame32),
    .logical_txd_waveform_i(wave32), .receive_enable_i(32'hffff_ffff),
    .bank_fault_i(32'h0), .rxd_i(32'hffff_ffff), .physical_txd_out_o(tx32),
    .physical_sd_o(), .rx_active_o(), .physical_module_selected_o(selected_phys32),
    .global_permit_raw_safe_o(), .global_permit_sync_valid_o(),
    .endpoint_armed_o(armed32), .mapping_collision_o(collision32),
    .duty_history_valid_mask_o(hist32), .rolling_high_cycles_flat_o(rolling32),
    .duty_hard_fault_mask_o(hard32), .stuck_high_fault_mask_o(stuck32)
  );

  task automatic check_expect(input logic condition, input string message);
    if (!condition) $fatal(1, "P8C_PROFILE_EXPECT_FAIL: %s", message);
  endtask
  task automatic tick(input integer count);
    repeat (count) begin @(posedge clk); #1; end
  endtask
  task automatic do_mapping_commit(input integer m0, input logic [1:0] dir);
    begin
      @(negedge clk); phase_m0=m0[4:0]; direction=dir; phase_valid=1'b1;
      direction_valid=1'b1; prepare_request=1'b1;
      @(posedge clk); #1; check_expect(prepare_ready && mapping_checks_pass, "P8B prepare");
      @(negedge clk); prepare_request=1'b0; commit_request=1'b1;
      @(posedge clk); #1; check_expect(commit_accept && active_valid, "P8B atomic commit");
      @(negedge clk); commit_request=1'b0; logical_epoch32={28'd0,path_epoch};
      @(posedge clk); #1;
    end
  endtask
  task automatic pulse_arms;
    begin arm2=1'b1; arm8=1'b1; arm32=1'b1; tick(1);
      arm2=1'b0; arm8=1'b0; arm32=1'b0; tick(1); end
  endtask
  task automatic pulse_profiles(input logic [7:0] mask);
    integer requested;
    begin
      sel2=mask; sel8=mask; sel32=mask;
      frame2=mask; frame8=mask; frame32=mask;
      wave2=mask; wave8=mask; wave32=mask;
      tick(1);
      requested = $countones(mask);
      if (requested <= 2) check_expect($countones(tx2)==requested, "2-module simultaneous mask");
      check_expect($countones(tx8)==requested, "8-module simultaneous mask");
      check_expect($countones(tx32)==requested, "32-module fixed simultaneous mask");
      frame2='0; frame8='0; frame32='0; wave2='0; wave8='0; wave32='0;
      tick(2);
    end
  endtask

  logic [31:0] module0_before;
  logic [3:0] epoch_before_illegal_commit;
  initial begin
    rst_n=1'b0; permit2=1'b0; permit8=1'b0; permit32=1'b0;
    arm2=1'b0; arm8=1'b0; arm32=1'b0;
    sel2=8'h01; sel8=8'h01; sel32=8'h01;
    frame2='0; frame8='0; frame32='0; wave2='0; wave8='0; wave32='0;
    phase_m0=0; direction=DIRECTION_FORWARD; phase_valid=1'b0; direction_valid=1'b0;
    prepare_request=1'b0; commit_request=1'b0; quiet_boundary=1'b1; logical_epoch32=0;
    tick(3); rst_n=1'b1; tick(1);
    do_mapping_commit(0, DIRECTION_FORWARD);
    tick(105);
    check_expect(&hist2 && &hist8 && &hist32, "all profile histories complete full cooldown");
    permit2=1'b1; permit8=1'b1; permit32=1'b1; tick(8);
    pulse_arms();
    check_expect(armed2 && armed8 && armed32, "all profiles explicitly armed");

    pulse_profiles(8'h01);
    check_expect(rolling2[31:0] == 1 && rolling2[63:32] == 0,
      "2-module histories are independent physical identities");
    check_expect(rolling32[31:0] == 1 && rolling32[63:32] == 0,
      "fixed physical module zero charged while module one stayed zero");
    pulse_profiles(8'h03);
    pulse_profiles(8'h0f);
    pulse_profiles(8'hff);

    // A stale path epoch must fail closed before any physical output.
    sel32=8'h01; logical_epoch32=32'hffff_ffff; frame32=8'h01; wave32=8'h01;
    tick(1); check_expect(tx32==0 && !armed32, "stale epoch kills and disarms fixed endpoint");
    frame32=0; wave32=0; logical_epoch32={28'd0,path_epoch}; tick(2);
    arm32=1'b1; tick(1); arm32=1'b0; tick(1); check_expect(armed32, "fresh epoch rearms");

    // Commit to the next physical slot, charge it, then return: module 0 history persists.
    module0_before=rolling32[31:0];
    do_mapping_commit(1, DIRECTION_FORWARD); tick(2);
    arm32=1'b1; tick(1); arm32=1'b0; tick(1);
    frame32=8'h01; wave32=8'h01; tick(1); frame32=0; wave32=0; tick(2);
    check_expect(rolling32[63:32] > 0, "mapping change charges physical module one");
    do_mapping_commit(0, DIRECTION_FORWARD); tick(2);
    check_expect(rolling32[31:0] == module0_before,
      "module zero duty history survives path commit and A-B-A mapping");

    // Exercise both mapping wrap directions at idle with the canonical P8B engine.
    do_mapping_commit(31, DIRECTION_FORWARD);
    check_expect(active_current_fixed[4:0]==5'd31 && active_candidate_fixed[4:0]==5'd0,
      "forward q3-to-q0 wrap");
    do_mapping_commit(0, DIRECTION_REVERSE);
    check_expect(active_current_fixed[4:0]==5'd0 && active_candidate_fixed[4:0]==5'd31,
      "reverse q0-to-q3 wrap");

    // Prepare a valid new mapping, then prove a commit request inside an
    // active frame is rejected without changing the active epoch or mapping.
    @(negedge clk); phase_m0=5'd2; direction=DIRECTION_FORWARD;
    phase_valid=1'b1; direction_valid=1'b1; prepare_request=1'b1;
    @(posedge clk); #1; check_expect(prepare_ready && mapping_checks_pass,
      "prepare before illegal in-frame commit");
    epoch_before_illegal_commit=path_epoch;
    @(negedge clk); prepare_request=1'b0; quiet_boundary=1'b0;
    frame32=8'h01; wave32=8'h00; commit_request=1'b1;
    @(posedge clk); #1;
    check_expect(commit_reject && !commit_accept && commit_reject_reason==3'd4 &&
                 path_epoch==epoch_before_illegal_commit,
      "illegal commit request during frame is rejected atomically");
    @(negedge clk); commit_request=1'b0; quiet_boundary=1'b1;
    frame32=0; wave32=0;
    @(posedge clk); #1;

    // The same prepared mapping may commit at idle while raw permit drops;
    // mapping state advances, but no physical Txd can remain asserted.
    @(negedge clk); permit32=1'b0; commit_request=1'b1;
    @(posedge clk); #1;
    check_expect(commit_accept && path_epoch==epoch_before_illegal_commit+1'b1 && tx32==0,
      "permit drop during an accepted path commit keeps all physical TX low");
    @(negedge clk); commit_request=1'b0; logical_epoch32={28'd0,path_epoch};
    @(posedge clk); #1;
    permit32=1'b1; tick(8);
    arm32=1'b1; tick(1); arm32=1'b0; tick(1);
    check_expect(armed32, "fixed endpoint explicitly rearms after permit-drop path commit");

    // One raw permit drop kills every currently requested path in each endpoint.
    logical_epoch32={28'd0,path_epoch}; sel2=8'h03; sel8=8'hff; sel32=8'hff;
    arm2=1'b1; arm8=1'b1; arm32=1'b1; tick(1); arm2=0; arm8=0; arm32=0; tick(1);
    frame2=8'h03; wave2=8'h03; frame8=8'hff; wave8=8'hff; frame32=8'hff; wave32=8'hff;
    tick(1); permit2=0; permit8=0; permit32=0; #1;
    check_expect(tx2==0 && tx8==0 && tx32==0, "endpoint-wide raw permit drop kills all outputs");

    check_expect(hard2==0 && hard8==0 && hard32==0, "no hard duty fault in legal profile traffic");
    check_expect(stuck2==0 && stuck8==0 && stuck32==0, "no stuck fault in one-cycle traffic");
    check_expect(!collision32, "canonical P8B mapping has no collision");

    // A deliberately overlong request faults only its owning physical module.
    frame2=0; frame8=0; frame32=0; wave2=0; wave8=0; wave32=0; tick(2);
    permit8=1'b1; tick(8); arm8=1'b1; tick(1); arm8=1'b0; tick(1);
    sel8=8'h01; frame8=8'h01; wave8=8'h01; tick(3);
    check_expect(stuck8==8'h01 && hard8==0,
      "overlong request faults only the selected rotating physical module");
    check_expect(stuck2==0 && stuck32==0,
      "fault isolation does not contaminate other endpoint profiles");
    $display("P8C_Z7010_2LANE_PROFILE_PASS=1");
    $display("P8C_Z7020_ROTATING_8LANE_MODEL_PASS=1");
    $display("P8C_Z7020_FIXED_32MODULE_MODEL_PASS=1");
    $display("P8C_P8B_MAPPING_INTEGRATION_PASS=1");
    $display("P8C_PHYSICAL_MODULE_IDENTITY_PASS=1");
    $display("P8C_ILLEGAL_COMMIT_DURING_FRAME_PASS=1");
    $display("P8C_PERMIT_DROP_DURING_PATH_COMMIT_PASS=1");
    $display("P8C_INDEPENDENT_FAULT_ISOLATION_PASS=1");
    $display("TB_P8C_PROFILE_MATRIX_PASS=1");
    $finish;
  end
endmodule
