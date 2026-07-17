`timescale 1ns/1ps
module tb_p8c_endpoint_safety;
  import tfdu_safety_pkg::*;
  logic clk = 1'b0;
  always #5 clk = ~clk;

  logic rst_n;
  logic global_permit;
  logic arm_request;
  logic disarm_request;
  logic full_shutdown;
  logic fault_clear_request;
  logic history_invalidate;
  logic mapping_valid;
  logic [1:0] receive_enable;
  logic [1:0] selected;
  logic [1:0] one_hot_valid;
  logic [1:0] bank_fault;
  logic [1:0] lane_permit;
  logic [1:0] path_valid;
  logic [1:0] frame_admitted;
  logic [1:0] waveform;
  logic [1:0] rxd;
  logic [1:0] txd;
  logic [1:0] sd;
  logic [1:0] rx_active;
  logic [1:0] startup_done;
  logic raw_safe;
  logic permit_sync;
  logic sync_valid;
  logic effective;
  logic armed;
  logic arm_accept;
  logic arm_reject;
  logic [4:0] arm_reject_reason;
  logic tx_kill;
  logic [1:0] effective_mask;
  logic [1:0] duty_fault;
  logic [1:0] stuck_fault;
  logic endpoint_fatal;
  logic partial_block;
  logic [31:0] rise_count;
  logic [31:0] fall_count;
  logic [31:0] drop_frame_count;
  logic [31:0] rearm_count;
  logic [31:0] fall_count_before_frame_drop;
  logic [31:0] drop_count_before_frame_drop;
  logic [4:0] last_drop_reason;
  logic [4:0] last_kill_reason;
  logic clear_accept;
  logic [63:0] rx_counts;
  logic [63:0] rolling_counts;
  logic [1:0] history_valid;
  logic [1:0] cooldown;
  logic [31:0] rolling_after_permit_drop;
  logic [31:0] rolling_before_lane_toggle;
  logic [31:0] rolling_before_path_fault;

  ir_tfdu_safety_endpoint #(
    .PHYSICAL_MODULE_COUNT(2),
    .CLOCK_HZ(1_000_000),
    .STARTUP_US(1),
    .WINDOW_US(100),
    .HARD_PERCENT_STRICT_LT(20),
    .TARGET_PERCENT_MAX(18),
    .MAX_CONTINUOUS_HIGH_US(1),
    .ASSERT_FILTER_CYCLES(4)
  ) dut (
    .clk, .rst_n,
    .global_permit_i(global_permit),
    .endpoint_arm_request_i(arm_request),
    .endpoint_disarm_request_i(disarm_request),
    .full_shutdown_request_i(full_shutdown),
    .safety_fault_clear_request_i(fault_clear_request),
    .telemetry_clear_i(1'b0),
    .history_invalidate_i(history_invalidate),
    .endpoint_fatal_fault_i(1'b0),
    .mapping_valid_i(mapping_valid),
    .receive_enable_i(receive_enable),
    .physical_module_selected_i(selected),
    .bank_one_hot_valid_i(one_hot_valid),
    .bank_fault_i(bank_fault),
    .lane_tx_permit_i(lane_permit),
    .path_epoch_valid_i(path_valid),
    .frame_admitted_i(frame_admitted),
    .txd_waveform_i(waveform),
    .rxd_i(rxd),
    .physical_txd_out_o(txd),
    .physical_sd_o(sd),
    .physical_mode_o(),
    .rx_active_o(rx_active),
    .startup_done_o(startup_done),
    .global_permit_raw_safe_o(raw_safe),
    .global_permit_sync_o(permit_sync),
    .global_permit_sync_valid_o(sync_valid),
    .global_permit_effective_o(effective),
    .endpoint_armed_o(armed),
    .arm_accept_pulse_o(arm_accept),
    .arm_reject_pulse_o(arm_reject),
    .arm_reject_reason_o(arm_reject_reason),
    .tx_kill_active_o(tx_kill),
    .effective_tx_enable_mask_o(effective_mask),
    .duty_hard_fault_mask_o(duty_fault),
    .stuck_high_fault_mask_o(stuck_fault),
    .endpoint_fatal_fault_o(endpoint_fatal),
    .partial_frame_abort_block_o(partial_block),
    .global_permit_rise_count_o(rise_count),
    .global_permit_fall_count_o(fall_count),
    .global_permit_drop_during_frame_count_o(drop_frame_count),
    .global_permit_rearm_count_o(rearm_count),
    .last_global_permit_drop_reason_o(last_drop_reason),
    .last_tx_kill_reason_o(last_kill_reason),
    .safety_fault_clear_accept_pulse_o(clear_accept),
    .rx_pulse_count_flat_o(rx_counts),
    .rolling_high_cycles_flat_o(rolling_counts),
    .rolling_high_cycles_max_seen_flat_o(),
    .duty_headroom_cycles_flat_o(),
    .duty_target_throttle_count_flat_o(),
    .duty_hard_fault_count_flat_o(),
    .continuous_high_cycles_flat_o(),
    .longest_high_cycles_seen_flat_o(),
    .stuck_high_fault_count_flat_o(),
    .stuck_high_kill_count_flat_o(),
    .cooldown_remaining_flat_o(),
    .charge_count_flat_o(),
    .duty_history_valid_mask_o(history_valid),
    .cooldown_active_mask_o(cooldown),
    .duty_target_throttle_mask_o()
  );

  task automatic check_expect(input logic condition, input string message);
    if (!condition) begin
      $fatal(1, "P8C_ENDPOINT_EXPECT_FAIL: %s", message);
    end
  endtask

  task automatic tick(input integer count);
    repeat (count) @(posedge clk);
    #1;
  endtask

  task automatic pulse_arm;
    begin
      arm_request = 1'b1;
      tick(1);
      arm_request = 1'b0;
      tick(1);
    end
  endtask

  task automatic stabilize_permit_high;
    integer guard;
    begin
      global_permit = 1'b1;
      guard = 0;
      while (!sync_valid && guard < 16) begin
        tick(1);
        guard = guard + 1;
      end
      check_expect(sync_valid, "permit high must synchronize and filter");
    end
  endtask

  initial begin
    rst_n = 1'b0;
    global_permit = 1'b0;
    arm_request = 1'b0;
    disarm_request = 1'b0;
    full_shutdown = 1'b0;
    fault_clear_request = 1'b0;
    history_invalidate = 1'b0;
    mapping_valid = 1'b1;
    receive_enable = 2'b11;
    selected = 2'b01;
    one_hot_valid = 2'b11;
    bank_fault = 2'b00;
    lane_permit = 2'b11;
    path_valid = 2'b11;
    frame_admitted = 2'b00;
    waveform = 2'b00;
    rxd = 2'b11;
    tick(3);
    check_expect(txd == 2'b00 && !armed && !raw_safe,
                 "reset and power-up default the permit path low");
    rst_n = 1'b1;
    tick(105);
    check_expect(history_valid == 2'b11 && startup_done == 2'b11,
                 "both physical histories and RX startup complete");

    // Permit low is hard TX-off but does not force SD high or disable RX.
    waveform = 2'b01;
    frame_admitted = 2'b01;
    tick(2);
    check_expect(txd == 2'b00 && sd == 2'b00 && !armed,
                 "permit low leaves receive-only mode while all TX is off");
    rxd[0] = 1'b0;
    tick(4);
    check_expect(rx_active[0] && rx_counts[31:0] == 1,
                 "active-low RX remains observable with permit low");
    rxd[0] = 1'b1;
    frame_admitted = 2'b00;
    waveform = 2'b00;

    global_permit = 1'bx;
    #1;
    check_expect(!raw_safe && txd == 2'b00, "X permit fails low");
    global_permit = 1'bz;
    #1;
    check_expect(!raw_safe && txd == 2'b00, "Z permit fails low");
    global_permit = 1'b0;
    tick(1);

    global_permit = 1'b1;
    tick(2);
    check_expect(!sync_valid && !armed && txd == 2'b00,
                 "permit pulse shorter than assertion filter cannot enable TX");
    global_permit = 1'b0;
    #1;
    check_expect(!raw_safe && txd == 2'b00, "permit bounce deasserts final kill immediately");
    tick(1);

    stabilize_permit_high();
    frame_admitted = 2'b01;
    waveform = 2'b01;
    tick(2);
    check_expect(txd == 2'b00 && !armed, "filtered permit high never auto-arms");
    frame_admitted = 2'b00;
    waveform = 2'b00;
    pulse_arm();
    check_expect(armed && effective, "explicit arm accepted after stable permit");

    frame_admitted = 2'b01;
    waveform = 2'b01;
    tick(1);
    check_expect(txd[0], "fresh admitted frame reaches selected physical module");
    fall_count_before_frame_drop = fall_count;
    drop_count_before_frame_drop = drop_frame_count;
    // Raw drop between clocks kills in the same delta cycle.
    global_permit = 1'b0;
    #1;
    check_expect(txd == 2'b00 && !armed, "raw-low asynchronous final kill and arm clear");
    tick(1);
    check_expect(partial_block &&
                 drop_frame_count == drop_count_before_frame_drop + 1 &&
                 fall_count == fall_count_before_frame_drop + 1,
                 "mid-frame permit drop latches partial-frame block and counters");
    rolling_after_permit_drop = rolling_counts[31:0];
    check_expect(rolling_after_permit_drop > 0,
                 "permit drop conservatively retains the commanded physical charge");

    stabilize_permit_high();
    check_expect(rolling_counts[31:0] == rolling_after_permit_drop,
                 "permit drop and filtered reassert do not clear physical duty history");
    arm_request = 1'b1;
    tick(1);
    check_expect(!armed && arm_reject && arm_reject_reason != 0,
                 "rearm is rejected while interrupted frame remains active");
    arm_request = 1'b0;
    tick(1);
    frame_admitted = 2'b00;
    waveform = 2'b00;
    tick(2);
    check_expect(!partial_block, "partial block clears only after old frame becomes inactive");
    pulse_arm();
    check_expect(armed, "explicit rearm accepted at a fresh frame boundary");
    frame_admitted = 2'b01;
    waveform = 2'b01;
    tick(1);
    check_expect(txd[0], "new frame transmits after explicit rearm");
    frame_admitted = 2'b00;
    waveform = 2'b00;
    tick(2);

    rolling_before_lane_toggle = rolling_counts[31:0];
    lane_permit[0] = 1'b0;
    tick(2);
    lane_permit[0] = 1'b1;
    tick(2);
    check_expect(rolling_counts[31:0] == rolling_before_lane_toggle,
                 "lane disable and enable preserve physical duty history");
    pulse_arm();
    check_expect(armed, "lane re-enable still requires and accepts explicit rearm");

    // A raw-low transition during a preamble/Txd-low interval still aborts
    // the frame even though no HIGH charge is present in that instant.
    frame_admitted = 2'b01;
    waveform = 2'b00;
    tick(1);
    drop_count_before_frame_drop = drop_frame_count;
    global_permit = 1'b0;
    #1;
    check_expect(txd == 2'b00 && !armed,
                 "permit low during preamble/Txd-low kills and clears arm");
    tick(1);
    check_expect(partial_block && drop_frame_count == drop_count_before_frame_drop + 1,
                 "permit low during preamble/Txd-low records a frame abort");
    frame_admitted = 2'b00;
    tick(2);
    stabilize_permit_high();
    check_expect(!armed && txd == 2'b00, "preamble drop cannot auto-resume");
    pulse_arm();

    // Repeat after a HIGH symbol followed by a LOW symbol inside one frame.
    frame_admitted = 2'b01;
    waveform = 2'b01;
    tick(1);
    waveform = 2'b00;
    tick(1);
    check_expect(txd == 2'b00, "in-frame LOW interval reached before permit injection");
    drop_count_before_frame_drop = drop_frame_count;
    global_permit = 1'b0;
    #1;
    tick(1);
    check_expect(partial_block && drop_frame_count == drop_count_before_frame_drop + 1,
                 "permit drop during Txd-low inside a frame is not ignored");
    frame_admitted = 2'b00;
    tick(2);
    stabilize_permit_high();
    pulse_arm();

    // Illegal one-hot and stale path independently revoke arm and kill.
    one_hot_valid = 2'b00;
    frame_admitted = 2'b01;
    waveform = 2'b01;
    tick(1);
    check_expect(txd == 2'b00 && !armed && last_kill_reason == TX_KILL_ILLEGAL_ONE_HOT,
                 "illegal one-hot kills selected TX with stable reason");
    one_hot_valid = 2'b11;
    frame_admitted = 2'b00;
    waveform = 2'b00;
    tick(1);
    pulse_arm();
    check_expect(armed, "arm restored after one-hot validity returns");
    path_valid = 2'b00;
    rolling_before_path_fault = rolling_counts[31:0];
    frame_admitted = 2'b01;
    waveform = 2'b01;
    tick(1);
    check_expect(txd == 2'b00 && !armed &&
                 last_kill_reason == TX_KILL_STALE_OR_INVALID_PATH_EPOCH,
                 "invalid path epoch kills selected TX with stable reason");
    path_valid = 2'b11;
    frame_admitted = 2'b00;
    waveform = 2'b00;
    tick(2);
    check_expect(rolling_counts[31:0] == rolling_before_path_fault,
                 "path epoch invalidation cannot clear physical duty history");

    pulse_arm();
    frame_admitted = 2'b01;
    waveform = 2'b01;
    tick(1);
    bank_fault[0] = 1'b1;
    tick(1);
    check_expect(txd == 2'b00 && !armed,
                 "bank fault asserted mid-high kills on the next safety clock");
    frame_admitted = 2'b00;
    waveform = 2'b00;
    bank_fault[0] = 1'b0;
    tick(2);

    selected = 2'b00;
    arm_request = 1'b1;
    tick(1);
    check_expect(!armed && txd == 2'b00 &&
                 arm_reject_reason == TX_KILL_INVALID_SELECTED_MODULE,
                 "no selected module rejects arm with stable reason");
    arm_request = 1'b0;
    tick(1);
    selected = 2'b0x;
    pulse_arm();
    check_expect(!armed && txd == 2'b00, "unknown selected module fails closed");
    selected = 2'b11;
    one_hot_valid = 2'b00;
    arm_request = 1'b1;
    tick(1);
    check_expect(!armed && txd == 2'b00 &&
                 arm_reject_reason == TX_KILL_ILLEGAL_ONE_HOT,
                 "multiple selected modules without one-hot validity fail closed");
    arm_request = 1'b0;
    tick(1);
    one_hot_valid = 2'b11;
    selected = 2'b01;
    tick(1);

    // Continuous-high request trips module fault, kills, and prevents automatic recovery.
    pulse_arm();
    frame_admitted = 2'b01;
    waveform = 2'b01;
    tick(3);
    check_expect(stuck_fault[0] && txd == 2'b00,
                 "MAX+1 continuous request latches stuck-high fault and kills");
    fault_clear_request = 1'b1;
    tick(1);
    fault_clear_request = 1'b0;
    check_expect(!clear_accept, "fault clear is rejected while raw permit is high");
    global_permit = 1'b0;
    waveform = 2'b00;
    frame_admitted = 2'b00;
    tick(2);
    stabilize_permit_high();
    pulse_arm();
    check_expect(!armed && stuck_fault[0] && txd == 2'b00,
                 "permit reassert after a fault cannot arm without valid clear");
    global_permit = 1'b0;
    tick(2);
    fault_clear_request = 1'b1;
    tick(1);
    fault_clear_request = 1'b0;
    tick(2);
    check_expect(!stuck_fault[0] && cooldown[0] && !history_valid[0],
                 "controlled low-permit fault clear starts safety cooldown");

    stabilize_permit_high();
    pulse_arm();
    check_expect(!armed && txd == 2'b00, "reassert after clear cannot bypass cooldown");
    global_permit = 1'b0;
    tick(101);
    stabilize_permit_high();
    pulse_arm();
    check_expect(armed, "explicit arm is accepted only after the full cooldown");

    full_shutdown = 1'b1;
    tick(1);
    check_expect(sd == 2'b11 && txd == 2'b00, "full shutdown asserts SD and holds Txd low");
    full_shutdown = 1'b0;

    $display("P8C_SINGLE_GLOBAL_PERMIT_PASS=1");
    $display("P8C_PERMIT_ASYNC_DROP_FINAL_KILL_PASS=1");
    $display("P8C_EXPLICIT_REARM_NO_PARTIAL_RESUME_PASS=1");
    $display("P8C_RECEIVE_ONLY_PERMIT_LOW_PASS=1");
    $display("P8C_ONE_HOT_PATH_EPOCH_KILL_PASS=1");
    $display("P8C_PERMIT_VECTOR_MATRIX_PASS=1");
    $display("P8C_FAULT_DROP_MID_HIGH_PASS=1");
    $display("P8C_HISTORY_PERMIT_LANE_PATH_PRESERVED_PASS=1");
    $display("P8C_KILL_REASON_PRIORITY_PASS=1");
    $display("TB_P8C_ENDPOINT_SAFETY_PASS=1");
    $finish;
  end
endmodule
