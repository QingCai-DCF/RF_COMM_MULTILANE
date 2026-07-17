`timescale 1ns/1ps
module tb_p8c_full_scale;
  logic clk = 1'b0;
  always #1 clk = ~clk;
  logic rst_n, global_permit, arm_request;
  logic [7:0] frame_admitted, waveform, txd, startup_done;
  logic [7:0] history_valid, cooldown, target_throttle, hard_fault, stuck_fault;
  logic armed, sync_valid;
  logic [255:0] rolling, rolling_max, continuous;
  integer cycle;
  integer simultaneous_eight_events;
  integer legal_pulse_requested_cycles;
  integer legal_pulse_admitted_cycles;

  ir_tfdu_safety_endpoint #(
    .PHYSICAL_MODULE_COUNT(8), .CLOCK_HZ(64_000_000),
    .STARTUP_US(500), .WINDOW_US(1000),
    .HARD_PERCENT_STRICT_LT(20), .TARGET_PERCENT_MAX(18),
    .MAX_CONTINUOUS_HIGH_US(1), .ASSERT_FILTER_CYCLES(4)
  ) dut (
    .clk, .rst_n, .global_permit_i(global_permit),
    .endpoint_arm_request_i(arm_request), .endpoint_disarm_request_i(1'b0),
    .full_shutdown_request_i(1'b0), .safety_fault_clear_request_i(1'b0),
    .telemetry_clear_i(1'b0), .history_invalidate_i(1'b0),
    .endpoint_fatal_fault_i(1'b0), .mapping_valid_i(1'b1),
    .receive_enable_i(8'hff), .physical_module_selected_i(8'hff),
    .bank_one_hot_valid_i(8'hff), .bank_fault_i(8'h00),
    .lane_tx_permit_i(8'hff), .path_epoch_valid_i(8'hff),
    .frame_admitted_i(frame_admitted), .txd_waveform_i(waveform),
    .rxd_i(8'hff), .physical_txd_out_o(txd), .physical_sd_o(),
    .physical_mode_o(), .rx_active_o(), .startup_done_o(startup_done),
    .global_permit_raw_safe_o(), .global_permit_sync_o(),
    .global_permit_sync_valid_o(sync_valid), .global_permit_effective_o(),
    .endpoint_armed_o(armed), .arm_accept_pulse_o(), .arm_reject_pulse_o(),
    .arm_reject_reason_o(), .tx_kill_active_o(), .effective_tx_enable_mask_o(),
    .duty_hard_fault_mask_o(hard_fault), .stuck_high_fault_mask_o(stuck_fault),
    .endpoint_fatal_fault_o(), .partial_frame_abort_block_o(),
    .global_permit_rise_count_o(), .global_permit_fall_count_o(),
    .global_permit_drop_during_frame_count_o(), .global_permit_rearm_count_o(),
    .last_global_permit_drop_reason_o(), .last_tx_kill_reason_o(),
    .safety_fault_clear_accept_pulse_o(), .rx_pulse_count_flat_o(),
    .rolling_high_cycles_flat_o(rolling),
    .rolling_high_cycles_max_seen_flat_o(rolling_max),
    .duty_headroom_cycles_flat_o(), .duty_target_throttle_count_flat_o(),
    .duty_hard_fault_count_flat_o(), .continuous_high_cycles_flat_o(continuous),
    .longest_high_cycles_seen_flat_o(), .stuck_high_fault_count_flat_o(),
    .stuck_high_kill_count_flat_o(), .cooldown_remaining_flat_o(),
    .charge_count_flat_o(), .duty_history_valid_mask_o(history_valid),
    .cooldown_active_mask_o(cooldown), .duty_target_throttle_mask_o(target_throttle)
  );

  task automatic check_expect(input logic condition, input string message);
    if (!condition) $fatal(1, "P8C_FULL_EXPECT_FAIL: %s", message);
  endtask
  task automatic tick(input integer count);
    repeat (count) begin @(posedge clk); #0.1; end
  endtask

  initial begin
    rst_n=1'b0; global_permit=1'b0; arm_request=1'b0;
    frame_admitted=0; waveform=0; simultaneous_eight_events=0;
    legal_pulse_requested_cycles=0; legal_pulse_admitted_cycles=0;
    tick(3); rst_n=1'b1; tick(64_005);
    check_expect(startup_done==8'hff, "canonical 32000-cycle startup complete");
    check_expect(history_valid==8'hff && cooldown==0,
      "canonical 64000-cycle history cooldown complete");
    global_permit=1'b1; tick(8); check_expect(sync_valid, "permit assertion filter complete");
    arm_request=1'b1; tick(1); arm_request=1'b0; tick(1);
    check_expect(armed, "full-scale endpoint explicitly armed");

    // Long legal 4PPM-like traffic uses 16-cycle (0.25 us) pulses at a
    // 12.5-percent duty. Normal target shaping must not truncate them.
    for (cycle=0; cycle<64_000; cycle=cycle+1) begin
      @(negedge clk);
      if ((cycle % 128)<16) begin
        frame_admitted=8'hff;
        waveform=8'hff;
        legal_pulse_requested_cycles=legal_pulse_requested_cycles+1;
      end else begin
        frame_admitted=0;
        waveform=0;
      end
      @(posedge clk); #0.1;
      if (txd==8'hff)
        legal_pulse_admitted_cycles=legal_pulse_admitted_cycles+1;
      check_expect(hard_fault==0 && stuck_fault==0,
                   "legal 4PPM-like pulse train remains fault-free");
    end
    frame_admitted=0; waveform=0; tick(2);
    check_expect(legal_pulse_admitted_cycles==legal_pulse_requested_cycles,
                 "normal duty target does not truncate a legal 4PPM-like pulse train");

    for (cycle=0; cycle<150_000; cycle=cycle+1) begin
      @(negedge clk);
      if ((cycle % 5)==0) begin frame_admitted=8'hff; waveform=8'hff; end
      else begin frame_admitted=0; waveform=0; end
      @(posedge clk); #0.1;
      if (txd==8'hff) simultaneous_eight_events=simultaneous_eight_events+1;
      for (integer module_index=0; module_index<8; module_index=module_index+1) begin
        check_expect(rolling[module_index*32 +: 32] <= 32'd11520,
          "per-module target policy never exceeds 18 percent");
        check_expect(rolling[module_index*32 +: 32] * 100 < 64_000 * 20,
          "strict arbitrary-alignment hard property");
        check_expect(continuous[module_index*32 +: 32] <= 64,
          "continuous-high count never exceeds canonical 1 us");
      end
      check_expect(hard_fault==0 && stuck_fault==0,
        "target shaper prevents full-scale hard/stuck fault");
    end
    frame_admitted=0; waveform=0; tick(2);
    check_expect(simultaneous_eight_events>1000, "eight-path simultaneous requests exercised");
    for (integer final_index=0; final_index<8; final_index=final_index+1)
      check_expect(rolling_max[final_index*32 +: 32] == 32'd11520,
        "each physical module reached but did not exceed 18 percent target");
    $display("P8C_FULL_SCALE_64MHZ_64000_WINDOW_PASS=1");
    $display("P8C_FULL_SCALE_MULTIPLE_WINDOW_WRAPS_PASS=1");
    $display("P8C_FULL_SCALE_SIMULTANEOUS_8_PASS=1");
    $display("P8C_LONG_PERIODIC_4PPM_LIKE_PASS=1");
    $display("TB_P8C_FULL_SCALE_PASS=1");
    $finish;
  end
endmodule
