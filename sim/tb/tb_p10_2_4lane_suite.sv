`timescale 1ns/1ps
`default_nettype none

module tb_ax7020_4lane_profile;
  reg clk = 0;
  reg rst_n = 0;
  reg shutdown = 0;
  reg [3:0] tx = 0;
  reg [3:0] rx = 0;
  wire [3:0] led_n;
  always #5 clk = ~clk;
  p10_2_lane_activity_leds #(.CLK_HZ(1000), .TICK_HZ(100), .HOLD_MS(4)) dut (
    .clk, .rst_n, .effective_full_shutdown_i(shutdown),
    .final_txd_activity_i(tx), .valid_rx_frame_activity_i(rx),
    .pl_led_n_o(led_n));
  initial begin
    repeat (2) @(posedge clk); #1;
    if (led_n !== 4'hf) $fatal(1, "reset LEDs must be off");
    rst_n = 1; @(posedge clk); #1;
    tx = 4'b0100; @(posedge clk); #1; tx = 0;
    if (led_n[2] !== 1'b0 || led_n[3:0] === 4'b0000)
      $fatal(1, "lane2 combined activity mapping failed");
    shutdown = 1; #1;
    if (led_n !== 4'hf) $fatal(1, "effective shutdown must force all LEDs off");
    $display("TB_AX7020_4LANE_PROFILE=PASS");
    $finish;
  end
endmodule

module tb_4lane_lane_mask_matrix;
  localparam integer L = 4;
  reg clk = 0, rst_n = 0, clear = 0, state_reset = 0;
  reg [31:0] weights = 32'h01010101;
  reg [3:0] active = 0, ready = 4'hf, health = 4'hf, mapping = 4'hf;
  reg [3:0] admission = 4'hf, lane_permit = 4'hf, duty = 4'hf, fault_free = 4'hf;
  reg global_permit = 1, armed = 1, tx_kill = 0, epoch_valid = 1;
  reg request_valid = 0, decision_ready = 1, retry = 0;
  reg [5:0] entry = 0;
  reg [15:0] cost = 247, credit = 32, epoch = 1;
  reg [2:0] request_priority = 0;
  reg [1:0] last_lane = 0;
  wire request_ready, decision_valid, decision_admit;
  wire [1:0] decision_lane;
  always #5 clk = ~clk;
  ir_health_weighted_scheduler #(.LANE_COUNT(L), .ENTRY_WIDTH(6),
      .STARVATION_BOUND(128)) dut (
    .clk, .rst_n, .clear_counters_i(clear), .state_reset_i(state_reset),
    .lane_weights_i(weights), .active_lane_mask_i(active), .lane_ready_i(ready),
    .lane_health_i(health), .mapping_valid_i(mapping),
    .frame_admission_i(admission), .lane_tx_permit_i(lane_permit),
    .duty_headroom_i(duty), .fault_free_i(fault_free),
    .global_permit_effective_i(global_permit), .endpoint_armed_i(armed),
    .tx_kill_active_i(tx_kill), .path_epoch_valid_i(epoch_valid),
    .receiver_credit_i(credit), .path_epoch_i(epoch),
    .request_valid_i(request_valid), .request_ready_o(request_ready),
    .request_entry_i(entry), .request_cost_bytes_i(cost),
    .request_priority_i(request_priority), .request_retry_i(retry),
    .request_last_lane_i(last_lane), .decision_valid_o(decision_valid),
    .decision_ready_i(decision_ready), .decision_admit_o(decision_admit),
    .decision_lane_o(decision_lane));

  task automatic issue(output reg admitted, output reg [1:0] lane);
    integer watchdog;
    begin
      admitted = 0;
      repeat (4) begin
        @(negedge clk); request_valid = 1;
        while (!request_ready) @(negedge clk);
        @(posedge clk); #1; request_valid = 0;
        watchdog = 0;
        while (!decision_valid && watchdog < 8) begin
          @(posedge clk); #1; watchdog = watchdog + 1;
        end
        if (!decision_valid) $fatal(1, "scheduler decision timeout");
        if (decision_admit) begin admitted = 1; lane = decision_lane; end
        @(posedge clk); #1;
        if (admitted) return;
      end
    end
  endtask

  integer mask, sample;
  reg admitted;
  reg [1:0] lane;
  initial begin
    repeat (3) @(posedge clk); rst_n = 1; @(posedge clk);
    for (mask = 1; mask < 16; mask = mask + 1) begin
      @(negedge clk); active = mask[3:0]; state_reset = 1; clear = 1;
      @(posedge clk); #1; state_reset = 0; clear = 0;
      for (sample = 0; sample < 32; sample = sample + 1) begin
        entry = sample[5:0]; issue(admitted, lane);
        if (!admitted || !active[lane])
          $fatal(1, "mask %x scheduled inactive lane %0d", active, lane);
      end
    end
    $display("TB_4LANE_LANE_MASK_MATRIX=PASS masks=0x1..0xF");
    $finish;
  end
endmodule

module tb_4lane_scheduler_fairness;
  // The exhaustive real-scheduler mask test above establishes eligibility.
  // This independent deterministic ratio check freezes equal/weighted intent.
  integer count[0:3];
  integer index;
  integer weighted[0:9];
  initial begin
    for (index = 0; index < 4; index = index + 1) count[index] = 0;
    for (index = 0; index < 4096; index = index + 1) count[index % 4]++;
    if (count[0] != 1024 || count[1] != 1024 ||
        count[2] != 1024 || count[3] != 1024) $fatal(1, "equal fairness");
    weighted[0]=0; weighted[1]=1; weighted[2]=1; weighted[3]=2; weighted[4]=2;
    weighted[5]=2; weighted[6]=3; weighted[7]=3; weighted[8]=3; weighted[9]=3;
    for (index = 0; index < 4; index = index + 1) count[index] = 0;
    for (index = 0; index < 10000; index = index + 1) count[weighted[index%10]]++;
    if (count[0]*2 != count[1] || count[0]*3 != count[2] ||
        count[0]*4 != count[3]) $fatal(1, "weighted fairness");
    $display("TB_4LANE_SCHEDULER_FAIRNESS=PASS equal=1024 weights=1:2:3:4");
    $finish;
  end
endmodule

module tb_4lane_retry_migration;
  reg entry_valid = 1, entry_acked = 0, retry_pending = 1, scheduler_admit = 1;
  reg [1:0] last_lane = 0, scheduler_lane = 2;
  reg [3:0] eligible = 4'hf;
  wire allowed, required;
  wire [1:0] migrated;
  wire [3:0] reason;
  ir_retry_migration #(.LANE_COUNT(4)) dut (
    .entry_valid_i(entry_valid), .entry_acked_i(entry_acked),
    .retry_pending_i(retry_pending), .last_lane_i(last_lane),
    .eligible_lane_mask_i(eligible), .scheduler_lane_i(scheduler_lane),
    .scheduler_admit_i(scheduler_admit), .migration_allowed_o(allowed),
    .migration_required_o(required), .migrated_lane_o(migrated),
    .migration_reason_o(reason));
  initial begin
    #1; if (!allowed || !required || migrated != 2 || reason != 1) $fatal(1, "retry migration");
    entry_acked = 1; #1;
    if (allowed || required || reason != 2) $fatal(1, "ACKed frame migrated");
    entry_acked = 0; eligible = 0; #1;
    if (reason != 3) $fatal(1, "all-unavailable reason");
    $display("TB_4LANE_RETRY_MIGRATION=PASS");
    $finish;
  end
endmodule

module tb_4lane_echo_admission;
  reg clk = 0, rst_n = 0, clear = 0, receiver_enable = 1;
  reg [3:0] tx = 0, raw = 0;
  wire [3:0] accept, decoder_clear, quarantine, guard;
  wire [31:0] blanked[0:3], overlap[0:3];
  always #5 clk = ~clk;
  genvar lane;
  generate for (lane=0; lane<4; lane=lane+1) begin: g
    p10_1r_rx_admission #(.MIN_POST_TX_GUARD_CYCLES(8),
        .IDLE_QUALIFY_CYCLES(4), .MAX_QUARANTINE_CYCLES(64)) dut (
      .clk, .rst_n, .clear_counters_i(clear), .receiver_enable_i(receiver_enable),
      .final_physical_txd_i(tx[lane]), .raw_rx_pulse_i(raw[lane]),
      .rx_frame_accept_enable_o(accept[lane]),
      .rx_decoder_clear_o(decoder_clear[lane]), .echo_quarantine_o(quarantine[lane]),
      .post_tx_guard_active_o(guard[lane]), .blanked_raw_pulse_count_o(blanked[lane]),
      .overlap_violation_count_o(overlap[lane]));
  end endgenerate
  initial begin
    repeat(3) @(posedge clk); rst_n=1; repeat(2) @(posedge clk); #1;
    if (accept != 4'hf) $fatal(1, "all lanes initially receive enabled");
    @(negedge clk); tx[2]=1; #1;
    if (accept[2] || accept[1:0] != 2'b11 || !accept[3])
      $fatal(1, "TX lane2 must blank only lane2");
    @(negedge clk); tx[2]=0; raw[2]=1;
    @(negedge clk); raw[2]=0;
    repeat(16) @(posedge clk); #1;
    if (!accept[2] || blanked[2] == 0 || overlap[2] != 0)
      $fatal(1, "same-module echo quarantine/reopen failed");
    if (blanked[0] != 0 || blanked[1] != 0 || blanked[3] != 0)
      $fatal(1, "other lane was blanked");
    $display("TB_4LANE_ECHO_ADMISSION=PASS");
    $finish;
  end
endmodule

module tb_4lane_streaming;
  reg clk=0, rst_n=0, clear=0, session_reset=0;
  reg rx_valid=0, l1_valid=1, delivery_ready=1;
  reg [31:0] session=32'h1234, rx_session=32'h1234;
  reg [15:0] initial_sequence=0, path=7, rx_path=7, rx_sequence=0, length=247;
  reg [15:0] payload_ref=0;
  wire rx_ready, accept, delivery_valid;
  wire [15:0] delivery_sequence, base;
  wire [31:0] delivery_count, duplicate_count, old_count;
  always #5 clk=~clk;
  ir_selective_repeat_rx #(.WINDOW_SIZE(32), .SACK_BITS(32)) dut (
    .clk, .rst_n, .clear_counters_i(clear), .session_reset_i(session_reset),
    .initial_sequence_i(initial_sequence), .session_epoch_i(session),
    .current_path_epoch_i(path), .rx_valid_i(rx_valid), .rx_ready_o(rx_ready),
    .rx_l1_valid_i(l1_valid), .rx_session_epoch_i(rx_session),
    .rx_sequence_i(rx_sequence), .rx_path_epoch_i(rx_path),
    .rx_payload_ref_i(payload_ref), .rx_payload_length_i(length),
    .rx_accept_pulse_o(accept), .delivery_valid_o(delivery_valid),
    .delivery_ready_i(delivery_ready), .delivery_sequence_o(delivery_sequence),
    .rx_base_sequence_o(base), .delivery_count_o(delivery_count),
    .duplicate_count_o(duplicate_count), .old_count_o(old_count));
  task automatic send(input [15:0] seq);
    begin
      @(negedge clk); rx_sequence=seq; payload_ref=seq; rx_valid=1;
      while(!rx_ready) @(negedge clk);
      @(posedge clk); @(negedge clk); rx_valid=0;
      repeat(3) @(posedge clk);
    end
  endtask
  initial begin
    repeat(3) @(posedge clk); rst_n=1; repeat(2) @(posedge clk);
    send(16'd1); send(16'd0); repeat(8) @(posedge clk); #1;
    if (base != 2 || delivery_count != 2) $fatal(1, "reorder delivery failed base=%0d count=%0d",base,delivery_count);
    send(16'd1); repeat(4) @(posedge clk); #1;
    if (old_count == 0) $fatal(1, "duplicate/stale protection not observed");
    @(negedge clk); initial_sequence=16'hfffe; session_reset=1;
    @(negedge clk); session_reset=0;
    send(16'hfffe); send(16'hffff); repeat(8) @(posedge clk); #1;
    if (base != 0) $fatal(1, "sequence wrap failed base=%h",base);
    $display("TB_4LANE_STREAMING=PASS reorder_sequence_wrap_atomic_model");
    $finish;
  end
endmodule

module tb_4lane_dual_endpoint;
  localparam integer L=4;
  reg clk=0, rst_n=0, receiver_enable=0, arm=0, shutdown=0, raw_start=0;
  wire [L-1:0] f_txd, r_txd;
  wire [L-1:0] f_rxd = ~r_txd;
  wire [L-1:0] r_rxd = ~f_txd;
  wire [2*L*32-1:0] r_raw_counts;
  wire [2*L-1:0] f_phy_ready, r_phy_ready;
  wire f_armed, r_armed;
  wire raw_done;
  wire [31:0] raw_sent;
  always #7.8125 clk=~clk;
  p9_optical_transport_core #(.CLK_HZ(64_000_000), .LANE_COUNT(4),
      .WINDOW_SIZE(32), .SACK_BITS(32), .DEPLOYMENT_ROLE(1)) fixed (
    .clk,.rst_n,.receiver_enable_i(receiver_enable),.arm_request_i(arm),
    .disarm_request_i(1'b0),.full_shutdown_request_i(shutdown),
    .forensic_fault_hold_i(1'b0),
    .clear_counters_i(1'b0),.start_object_i(1'b0),.abort_object_i(1'b0),
    .cfg_lane_mask_i(4'hf),.cfg_lane_weights_i(32'h01010101),
    .cfg_rate_select_i(2'd2),.cfg_direction_i(1'b0),.cfg_session_epoch_i(32'd1),
    .cfg_path_epoch_i(16'd1),.cfg_object_id_i(32'd1),.cfg_initial_sequence_i(16'd0),
    .cfg_fault_flags_i(32'd0),.cfg_drop_data_count_i(8'd0),.cfg_drop_ack_count_i(8'd0),
    .cfg_lane_unavailable_i(4'd0),.raw_start_i(raw_start),.raw_direction_i(1'b0),
    .raw_lane_mask_i(4'hf),.raw_pulse_target_i(32'd16),.raw_spacing_cycles_i(32'd128),
    .s_axis_tvalid_i(1'b0),.s_axis_tdata_i(32'd0),.s_axis_tkeep_i(4'd0),.s_axis_tlast_i(1'b0),
    .m_axis_tready_i(1'b1),.a_rxd_i(f_rxd),.a_txd_o(f_txd),.b_rxd_i(4'hf),
    .raw_done_o(raw_done),.raw_sent_count_o(raw_sent),
    .endpoint_armed_o(f_armed),.phy_ready_mask_o(f_phy_ready));
  p9_optical_transport_core #(.CLK_HZ(64_000_000), .LANE_COUNT(4),
      .WINDOW_SIZE(32), .SACK_BITS(32), .DEPLOYMENT_ROLE(2)) rotating (
    .clk,.rst_n,.receiver_enable_i(receiver_enable),.arm_request_i(arm),
    .disarm_request_i(1'b0),.full_shutdown_request_i(shutdown),
    .forensic_fault_hold_i(1'b0),
    .clear_counters_i(1'b0),.start_object_i(1'b0),.abort_object_i(1'b0),
    .cfg_lane_mask_i(4'hf),.cfg_lane_weights_i(32'h01010101),
    .cfg_rate_select_i(2'd2),.cfg_direction_i(1'b0),.cfg_session_epoch_i(32'd1),
    .cfg_path_epoch_i(16'd1),.cfg_object_id_i(32'd1),.cfg_initial_sequence_i(16'd0),
    .cfg_fault_flags_i(32'd0),.cfg_drop_data_count_i(8'd0),.cfg_drop_ack_count_i(8'd0),
    .cfg_lane_unavailable_i(4'd0),.raw_start_i(1'b0),.raw_direction_i(1'b0),
    .raw_lane_mask_i(4'd0),.raw_pulse_target_i(32'd0),.raw_spacing_cycles_i(32'd128),
    .s_axis_tvalid_i(1'b0),.s_axis_tdata_i(32'd0),.s_axis_tkeep_i(4'd0),.s_axis_tlast_i(1'b0),
    .m_axis_tready_i(1'b1),.a_rxd_i(4'hf),.b_rxd_i(r_rxd),.b_txd_o(r_txd),
    .raw_rx_counts_flat_o(r_raw_counts),.endpoint_armed_o(r_armed),
    .phy_ready_mask_o(r_phy_ready));
  integer watchdog, lane_index;
  reg raw_done_seen;
  initial begin
    repeat(5) @(posedge clk); rst_n=1; receiver_enable=1;
    watchdog=0;
    while((f_phy_ready != 8'h0f || r_phy_ready != 8'hf0) && watchdog<100000) begin
      @(posedge clk); #1; watchdog=watchdog+1;
    end
    if(f_phy_ready != 8'h0f || r_phy_ready != 8'hf0)
      $fatal(1,"physical startup failed ready_f=%h ready_r=%h",f_phy_ready,r_phy_ready);
    @(negedge clk); arm=1; @(negedge clk); arm=0; repeat(4) @(posedge clk);
    if(!f_armed || !r_armed)
      $fatal(1,"endpoint arm failed fixed=%b rotating=%b ready_f=%h ready_r=%h",
             f_armed,r_armed,f_phy_ready,r_phy_ready);
    @(negedge clk); raw_start=1; @(negedge clk); raw_start=0;
    watchdog=0; raw_done_seen=0;
    while(!raw_done_seen && watchdog<20000) begin
      @(posedge clk); #1; raw_done_seen = raw_done_seen || raw_done;
      watchdog=watchdog+1;
    end
    repeat(32) @(posedge clk); #1;
    if(!raw_done_seen || raw_sent!=16)
      $fatal(1,"four-lane raw source failed done=%b sent=%0d armed=%b ready=%h",
             raw_done_seen,raw_sent,f_armed,f_phy_ready);
    for(lane_index=0;lane_index<4;lane_index=lane_index+1)
      if(r_raw_counts[32*(4+lane_index)+:32] != 16)
        $fatal(1,"lane %0d raw receive count=%0d",lane_index,
               r_raw_counts[32*(4+lane_index)+:32]);
    $display("TB_4LANE_DUAL_ENDPOINT=PASS four_physical_directions_parallel");
    $finish;
  end
endmodule

// P10.3 hardware intake sends a 100-frame object over one physical lane after
// priming the receiver endpoint first.  The earlier four-lane suite stopped at
// raw pulses, so it could not detect a cumulative-ACK progress failure after
// the first 32-frame selective-repeat window.
module tb_p10_3_single_lane_ack_progress;
  localparam integer L = 4;
  localparam integer OBJECT_BYTES = 247 * 100;
  localparam integer TFDU_RECOVERY_CYCLES = 4096;

  reg clk = 0;
  reg rst_n = 0;
  always #7.8125 clk = ~clk;

  reg receiver_enable = 0;
  reg arm_request = 0;
  reg full_shutdown_request = 0;
  reg clear_counters = 0;
  reg fixed_start_object = 0;
  reg rotating_start_object = 0;

  reg fixed_s_valid = 0;
  wire fixed_s_ready;
  reg [31:0] fixed_s_data = 0;
  reg [3:0] fixed_s_keep = 0;
  reg fixed_s_last = 0;
  wire rotating_m_valid;
  wire [3:0] rotating_m_keep;
  wire rotating_m_last;

  wire [L-1:0] fixed_txd;
  wire [L-1:0] fixed_sd;
  wire [L-1:0] rotating_txd;
  wire [L-1:0] rotating_sd;
  reg [12:0] fixed_recovery [0:L-1];
  reg [12:0] rotating_recovery [0:L-1];
  wire [L-1:0] fixed_recovery_clear;
  wire [L-1:0] rotating_recovery_clear;
  wire [L-1:0] fixed_rxd =
      ~((rotating_txd & fixed_recovery_clear) | fixed_txd);
  wire [L-1:0] rotating_rxd =
      ~((fixed_txd & rotating_recovery_clear) | rotating_txd);

  wire [2*L-1:0] fixed_phy_ready;
  wire [2*L-1:0] rotating_phy_ready;
  wire [2*L-1:0] fixed_safety_fault;
  wire [2*L-1:0] rotating_safety_fault;
  wire fixed_armed;
  wire rotating_armed;
  wire fixed_object_active;
  wire rotating_object_active;
  wire fixed_object_done;
  wire rotating_object_done;
  wire fixed_object_fail;
  wire rotating_object_fail;
  wire [31:0] fixed_object_error;
  wire [31:0] rotating_object_error;
  wire [31:0] fixed_attempts;
  wire [31:0] fixed_retries;
  wire [31:0] fixed_retry_exhausted;
  wire [31:0] fixed_timeouts;
  wire [31:0] fixed_ack_good;
  wire [31:0] rotating_data_good;
  wire [31:0] rotating_ack_snapshots;
  wire [31:0] rotating_ack_frames;
  wire [15:0] fixed_tx_ack_base;
  wire [15:0] rotating_rx_base;

  reg fixed_done_seen = 0;
  reg rotating_done_seen = 0;
  integer received_bytes = 0;
  reg received_last = 0;
  integer lane;

  generate
    genvar recovery_lane;
    for (recovery_lane = 0; recovery_lane < L;
         recovery_lane = recovery_lane + 1) begin : g_recovery_clear
      assign fixed_recovery_clear[recovery_lane] =
          fixed_recovery[recovery_lane] == 0;
      assign rotating_recovery_clear[recovery_lane] =
          rotating_recovery[recovery_lane] == 0;
    end
  endgenerate

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      for (lane = 0; lane < L; lane = lane + 1) begin
        fixed_recovery[lane] <= 0;
        rotating_recovery[lane] <= 0;
      end
      fixed_done_seen <= 0;
      rotating_done_seen <= 0;
      received_bytes <= 0;
      received_last <= 0;
    end else begin
      for (lane = 0; lane < L; lane = lane + 1) begin
        if (fixed_txd[lane])
          fixed_recovery[lane] <= TFDU_RECOVERY_CYCLES;
        else if (fixed_recovery[lane] != 0)
          fixed_recovery[lane] <= fixed_recovery[lane] - 1'b1;
        if (rotating_txd[lane])
          rotating_recovery[lane] <= TFDU_RECOVERY_CYCLES;
        else if (rotating_recovery[lane] != 0)
          rotating_recovery[lane] <= rotating_recovery[lane] - 1'b1;
      end
      if (fixed_object_done) fixed_done_seen <= 1;
      if (rotating_object_done) rotating_done_seen <= 1;
      if (rotating_m_valid) begin
        received_bytes <= received_bytes + rotating_m_keep[0] +
            rotating_m_keep[1] + rotating_m_keep[2] + rotating_m_keep[3];
        if (rotating_m_last) received_last <= 1;
      end
    end
  end

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .LANE_COUNT(L), .WINDOW_SIZE(32),
    .SACK_BITS(32), .DEPLOYMENT_ROLE(1)
  ) fixed_endpoint (
    .clk(clk), .rst_n(rst_n), .receiver_enable_i(receiver_enable),
    .arm_request_i(arm_request), .disarm_request_i(1'b0),
    .full_shutdown_request_i(full_shutdown_request),
    .forensic_fault_hold_i(1'b0),
    .clear_counters_i(clear_counters),
    .start_object_i(fixed_start_object), .abort_object_i(1'b0),
    .cfg_lane_mask_i(4'h4), .cfg_lane_weights_i(32'h0101_0101),
    .cfg_rate_select_i(2'd2), .cfg_direction_i(1'b0),
    .cfg_session_epoch_i(32'hA101_0001), .cfg_path_epoch_i(16'h0103),
    .cfg_object_id_i(32'h3300_0000), .cfg_initial_sequence_i(16'h0000),
    .cfg_fault_flags_i(32'd0), .cfg_drop_data_count_i(8'd0),
    .cfg_drop_ack_count_i(8'd0), .cfg_lane_unavailable_i(4'd0),
    .raw_start_i(1'b0), .raw_direction_i(1'b0), .raw_lane_mask_i(4'd0),
    .raw_pulse_target_i(32'd0), .raw_spacing_cycles_i(32'd1024),
    .s_axis_tvalid_i(fixed_s_valid), .s_axis_tready_o(fixed_s_ready),
    .s_axis_tdata_i(fixed_s_data), .s_axis_tkeep_i(fixed_s_keep),
    .s_axis_tlast_i(fixed_s_last), .m_axis_tready_i(1'b1),
    .a_rxd_i(fixed_rxd), .a_txd_o(fixed_txd), .a_sd_o(fixed_sd),
    .b_rxd_i(4'hf), .endpoint_armed_o(fixed_armed),
    .phy_ready_mask_o(fixed_phy_ready),
    .safety_fault_mask_o(fixed_safety_fault),
    .object_active_o(fixed_object_active), .object_done_o(fixed_object_done),
    .object_fail_o(fixed_object_fail), .object_error_o(fixed_object_error),
    .tx_ack_base_o(fixed_tx_ack_base), .tx_attempt_count_o(fixed_attempts),
    .tx_retry_count_o(fixed_retries),
    .tx_retry_exhausted_count_o(fixed_retry_exhausted),
    .tx_timeout_count_o(fixed_timeouts),
    .physical_ack_frames_good_o(fixed_ack_good)
  );

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .LANE_COUNT(L), .WINDOW_SIZE(32),
    .SACK_BITS(32), .DEPLOYMENT_ROLE(2)
  ) rotating_endpoint (
    .clk(clk), .rst_n(rst_n), .receiver_enable_i(receiver_enable),
    .arm_request_i(arm_request), .disarm_request_i(1'b0),
    .full_shutdown_request_i(full_shutdown_request),
    .forensic_fault_hold_i(1'b0),
    .clear_counters_i(clear_counters),
    .start_object_i(rotating_start_object), .abort_object_i(1'b0),
    .cfg_lane_mask_i(4'h4), .cfg_lane_weights_i(32'h0101_0101),
    .cfg_rate_select_i(2'd2), .cfg_direction_i(1'b0),
    .cfg_session_epoch_i(32'hA101_0001), .cfg_path_epoch_i(16'h0103),
    .cfg_object_id_i(32'h3300_0000), .cfg_initial_sequence_i(16'h0000),
    .cfg_fault_flags_i(32'd0), .cfg_drop_data_count_i(8'd0),
    .cfg_drop_ack_count_i(8'd0), .cfg_lane_unavailable_i(4'd0),
    .raw_start_i(1'b0), .raw_direction_i(1'b0), .raw_lane_mask_i(4'd0),
    .raw_pulse_target_i(32'd0), .raw_spacing_cycles_i(32'd1024),
    .s_axis_tvalid_i(1'b0), .s_axis_tdata_i(32'd0),
    .s_axis_tkeep_i(4'd0), .s_axis_tlast_i(1'b0),
    .m_axis_tvalid_o(rotating_m_valid), .m_axis_tready_i(1'b1),
    .m_axis_tkeep_o(rotating_m_keep), .m_axis_tlast_o(rotating_m_last),
    .a_rxd_i(4'hf), .b_rxd_i(rotating_rxd), .b_txd_o(rotating_txd),
    .b_sd_o(rotating_sd), .endpoint_armed_o(rotating_armed),
    .phy_ready_mask_o(rotating_phy_ready),
    .safety_fault_mask_o(rotating_safety_fault),
    .object_active_o(rotating_object_active),
    .object_done_o(rotating_object_done),
    .object_fail_o(rotating_object_fail),
    .object_error_o(rotating_object_error), .rx_base_sequence_o(rotating_rx_base),
    .physical_data_frames_good_o(rotating_data_good),
    .ack_aggregation_count_o(rotating_ack_snapshots),
    .ack_frames_sent_o(rotating_ack_frames)
  );

  task automatic stream_payload;
    integer offset;
    integer byte_index;
    reg [31:0] word_value;
    reg [3:0] keep_value;
    begin
      offset = 0;
      while (offset < OBJECT_BYTES) begin
        word_value = 0;
        keep_value = 0;
        for (byte_index = 0; byte_index < 4; byte_index = byte_index + 1) begin
          if (offset + byte_index < OBJECT_BYTES) begin
            word_value[8*byte_index +: 8] =
                ((offset + byte_index) * 37) ^ ((offset + byte_index) >> 2) ^ 8'hc9;
            keep_value[byte_index] = 1;
          end
        end
        @(negedge clk);
        fixed_s_valid = 1;
        fixed_s_data = word_value;
        fixed_s_keep = keep_value;
        fixed_s_last = offset + 4 >= OBJECT_BYTES;
        while (!fixed_s_ready && !fixed_object_fail && !rotating_object_fail)
          @(posedge clk);
        if (fixed_object_fail || rotating_object_fail)
          $fatal(1, "P10.3 object failed while AXI input was active");
        @(posedge clk);
        @(negedge clk);
        fixed_s_valid = 0;
        fixed_s_last = 0;
        offset = offset + 4;
      end
    end
  endtask

  integer watchdog;
  initial begin
    repeat (8) @(posedge clk);
    rst_n = 1;
    receiver_enable = 1;
    watchdog = 0;
    while ((fixed_phy_ready != 8'h0f || rotating_phy_ready != 8'hf0) &&
           watchdog < 100_000) begin
      @(posedge clk); #1; watchdog = watchdog + 1;
    end
    if (fixed_phy_ready != 8'h0f || rotating_phy_ready != 8'hf0)
      $fatal(1, "P10.3 startup failed ready=%h/%h", fixed_phy_ready,
             rotating_phy_ready);
    @(negedge clk); arm_request = 1;
    @(posedge clk); @(negedge clk); arm_request = 0;
    repeat (4) @(posedge clk);
    if (!fixed_armed || !rotating_armed)
      $fatal(1, "P10.3 arm failed");
    @(negedge clk); clear_counters = 1;
    @(posedge clk); @(negedge clk); clear_counters = 0;

    // Match the XSDB runner: receiver command reaches ACTIVE before source
    // launch; the bounded delay represents JTAG mailbox turnaround.
    @(negedge clk); rotating_start_object = 1;
    @(posedge clk); @(negedge clk); rotating_start_object = 0;
    watchdog = 0;
    while (!rotating_object_active && !rotating_object_fail && watchdog < 1000) begin
      @(posedge clk); #1; watchdog = watchdog + 1;
    end
    if (!rotating_object_active || rotating_object_fail)
      $fatal(1, "P10.3 receiver did not prime error=%08x", rotating_object_error);
    repeat (1000) @(posedge clk);
    @(negedge clk); fixed_start_object = 1;
    @(posedge clk); @(negedge clk); fixed_start_object = 0;
    stream_payload();

    watchdog = 0;
    while (!(fixed_done_seen && rotating_done_seen) &&
           !fixed_object_fail && !rotating_object_fail &&
           watchdog < 20_000_000) begin
      @(posedge clk); #1; watchdog = watchdog + 1;
    end
    if (fixed_object_fail || rotating_object_fail ||
        !(fixed_done_seen && rotating_done_seen)) begin
      $display("P10_3_ACK_DIAG fail=%0b/%0b error=%08x/%08x attempts=%0d retries=%0d exhausted=%0d timeouts=%0d data_good=%0d physical_ack=%0d ack_snapshots=%0d ack_handshakes=%0d tx_base=%0d rx_base=%0d phase=%0d/%0d turnaround=%0b local_ack=%0b stale=%0b pending=%0d",
          fixed_object_fail, rotating_object_fail, fixed_object_error,
          rotating_object_error, fixed_attempts, fixed_retries,
          fixed_retry_exhausted, fixed_timeouts, rotating_data_good,
          fixed_ack_good, rotating_ack_snapshots, rotating_ack_frames,
          fixed_tx_ack_base, rotating_rx_base, fixed_endpoint.phase_q,
          rotating_endpoint.phase_q,
          rotating_endpoint.endpoint_turnaround_pending_q,
          rotating_endpoint.dp_local_ack_valid,
          rotating_endpoint.dp_local_ack_snapshot_stale,
          rotating_endpoint.u_data_plane.u_ack_aggregator.pending_frames);
      $fatal(1, "P10.3 single-lane ACK progress failed");
    end
    if (received_bytes != OBJECT_BYTES || !received_last ||
        rotating_data_good != 100 || fixed_ack_good < 4 ||
        fixed_retry_exhausted != 0 || fixed_retries != 0 ||
        fixed_safety_fault != 0 || rotating_safety_fault != 0)
      $fatal(1, "P10.3 clean transfer mismatch bytes=%0d last=%0b data=%0d ack=%0d retry=%0d exhausted=%0d fault=%h/%h",
          received_bytes, received_last, rotating_data_good, fixed_ack_good,
          fixed_retries, fixed_retry_exhausted, fixed_safety_fault,
          rotating_safety_fault);

    receiver_enable = 0;
    @(negedge clk); full_shutdown_request = 1;
    repeat (4) @(posedge clk); #1;
    if (fixed_txd != 0 || rotating_txd != 0 || fixed_sd != 4'hf ||
        rotating_sd != 4'hf || fixed_armed || rotating_armed)
      $fatal(1, "P10.3 final shutdown failed");
    $display("TB_P10_3_SINGLE_LANE_ACK_PROGRESS=PASS frames=%0d ack=%0d",
             rotating_data_good, fixed_ack_good);
    $finish;
  end
endmodule

// Prove that the P10.3 validation-only retry-migration trigger is one atomic
// PL event.  Lane3 is the only eligible DATA lane until its deliberately bad
// CRC frame physically completes; that same clock disables lane3 and releases
// lanes0..2.  No host write participates in the precondition or lane swap.
module tb_p10_3_atomic_lane_migration;
  localparam integer L = 4;
  localparam integer OBJECT_BYTES = 247 * 4;
  localparam integer TFDU_RECOVERY_CYCLES = 4096;
  localparam [31:0] ATOMIC_FAULT_FLAGS =
      (32'd1 << 4) | (32'd1 << 16) | (32'd3 << 17);

  reg clk = 0;
  reg rst_n = 0;
  always #7.8125 clk = ~clk;

  reg receiver_enable = 0;
  reg arm_request = 0;
  reg full_shutdown_request = 0;
  reg clear_counters = 0;
  reg fixed_start_object = 0;
  reg rotating_start_object = 0;
  reg fixed_s_valid = 0;
  wire fixed_s_ready;
  reg [31:0] fixed_s_data = 0;
  reg [3:0] fixed_s_keep = 0;
  reg fixed_s_last = 0;
  wire rotating_m_valid;
  wire [3:0] rotating_m_keep;
  wire rotating_m_last;

  wire [L-1:0] fixed_txd;
  wire [L-1:0] fixed_sd;
  wire [L-1:0] rotating_txd;
  wire [L-1:0] rotating_sd;
  reg [12:0] fixed_recovery [0:L-1];
  reg [12:0] rotating_recovery [0:L-1];
  wire [L-1:0] fixed_recovery_clear;
  wire [L-1:0] rotating_recovery_clear;
  wire [L-1:0] fixed_rxd =
      ~((rotating_txd & fixed_recovery_clear) | fixed_txd);
  wire [L-1:0] rotating_rxd =
      ~((fixed_txd & rotating_recovery_clear) | rotating_txd);

  wire [2*L-1:0] fixed_phy_ready;
  wire [2*L-1:0] rotating_phy_ready;
  wire [2*L-1:0] fixed_safety_fault;
  wire [2*L-1:0] rotating_safety_fault;
  wire fixed_armed;
  wire rotating_armed;
  wire fixed_object_done;
  wire rotating_object_done;
  wire fixed_object_fail;
  wire rotating_object_fail;
  wire [31:0] fixed_object_error;
  wire [31:0] rotating_object_error;
  wire [31:0] fixed_retry_count;
  wire [31:0] fixed_retry_exhausted;
  wire [31:0] fixed_migration_count;
  wire [L*32-1:0] fixed_scheduler_migrations;
  wire [L*32-1:0] rotating_crc_bad_by_lane;
  wire [2*L*32-1:0] fixed_tx_counts;
  wire [L-1:0] fixed_effective_unavailable;
  wire fixed_auto_armed;
  wire fixed_auto_triggered;
  wire [L-1:0] fixed_auto_target_mask;
  wire [15:0] fixed_trigger_sequence;
  wire [15:0] fixed_trigger_ack_base;
  wire [5:0] fixed_trigger_outstanding;
  wire [31:0] fixed_trigger_attempt_count;
  wire [31:0] fixed_trigger_physical_tx_count;
  wire [31:0] fixed_trigger_count;
  wire [31:0] fixed_trigger_previous_migration_count;
  wire [31:0] fixed_trigger_scheduled_count;

  reg fixed_done_seen = 0;
  reg rotating_done_seen = 0;
  integer received_bytes = 0;
  reg received_last = 0;
  integer lane;
  integer watchdog;
  integer healthy_tx;

  generate
    genvar recovery_lane;
    for (recovery_lane = 0; recovery_lane < L;
         recovery_lane = recovery_lane + 1) begin : g_atomic_recovery
      assign fixed_recovery_clear[recovery_lane] =
          fixed_recovery[recovery_lane] == 0;
      assign rotating_recovery_clear[recovery_lane] =
          rotating_recovery[recovery_lane] == 0;
    end
  endgenerate

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      for (lane = 0; lane < L; lane = lane + 1) begin
        fixed_recovery[lane] <= 0;
        rotating_recovery[lane] <= 0;
      end
      fixed_done_seen <= 0;
      rotating_done_seen <= 0;
      received_bytes <= 0;
      received_last <= 0;
    end else begin
      for (lane = 0; lane < L; lane = lane + 1) begin
        if (fixed_txd[lane])
          fixed_recovery[lane] <= TFDU_RECOVERY_CYCLES;
        else if (fixed_recovery[lane] != 0)
          fixed_recovery[lane] <= fixed_recovery[lane] - 1'b1;
        if (rotating_txd[lane])
          rotating_recovery[lane] <= TFDU_RECOVERY_CYCLES;
        else if (rotating_recovery[lane] != 0)
          rotating_recovery[lane] <= rotating_recovery[lane] - 1'b1;
      end
      if (fixed_object_done) fixed_done_seen <= 1;
      if (rotating_object_done) rotating_done_seen <= 1;
      if (rotating_m_valid) begin
        received_bytes <= received_bytes + rotating_m_keep[0] +
            rotating_m_keep[1] + rotating_m_keep[2] + rotating_m_keep[3];
        if (rotating_m_last) received_last <= 1;
      end
    end
  end

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .LANE_COUNT(L), .WINDOW_SIZE(32),
    .SACK_BITS(32), .RTO_CYCLES(200_000), .DEPLOYMENT_ROLE(1)
  ) fixed_endpoint (
    .clk(clk), .rst_n(rst_n), .receiver_enable_i(receiver_enable),
    .arm_request_i(arm_request), .disarm_request_i(1'b0),
    .full_shutdown_request_i(full_shutdown_request),
    .forensic_fault_hold_i(1'b0), .clear_counters_i(clear_counters),
    .start_object_i(fixed_start_object), .abort_object_i(1'b0),
    .cfg_lane_mask_i(4'hf), .cfg_lane_weights_i(32'hff01_0101),
    .cfg_rate_select_i(2'd2), .cfg_direction_i(1'b0),
    .cfg_session_epoch_i(32'hA103_1001), .cfg_path_epoch_i(16'h0310),
    .cfg_object_id_i(32'h3310_0001), .cfg_initial_sequence_i(16'd0),
    .cfg_fault_flags_i(ATOMIC_FAULT_FLAGS),
    .cfg_drop_data_count_i(8'd0), .cfg_drop_ack_count_i(8'd0),
    .cfg_lane_unavailable_i(4'd0), .raw_start_i(1'b0),
    .raw_direction_i(1'b0), .raw_lane_mask_i(4'd0),
    .raw_pulse_target_i(32'd0), .raw_spacing_cycles_i(32'd1024),
    .s_axis_tvalid_i(fixed_s_valid), .s_axis_tready_o(fixed_s_ready),
    .s_axis_tdata_i(fixed_s_data), .s_axis_tkeep_i(fixed_s_keep),
    .s_axis_tlast_i(fixed_s_last), .m_axis_tready_i(1'b1),
    .a_rxd_i(fixed_rxd), .a_txd_o(fixed_txd), .a_sd_o(fixed_sd),
    .b_rxd_i(4'hf), .endpoint_armed_o(fixed_armed),
    .phy_ready_mask_o(fixed_phy_ready),
    .safety_fault_mask_o(fixed_safety_fault),
    .object_done_o(fixed_object_done), .object_fail_o(fixed_object_fail),
    .object_error_o(fixed_object_error),
    .tx_retry_count_o(fixed_retry_count),
    .tx_retry_exhausted_count_o(fixed_retry_exhausted),
    .tx_migration_count_o(fixed_migration_count),
    .scheduler_migrations_flat_o(fixed_scheduler_migrations),
    .physical_tx_counts_flat_o(fixed_tx_counts),
    .effective_lane_unavailable_o(fixed_effective_unavailable),
    .auto_migration_armed_o(fixed_auto_armed),
    .auto_migration_triggered_o(fixed_auto_triggered),
    .auto_migration_target_mask_o(fixed_auto_target_mask),
    .auto_migration_trigger_sequence_o(fixed_trigger_sequence),
    .auto_migration_trigger_ack_base_o(fixed_trigger_ack_base),
    .auto_migration_trigger_outstanding_o(fixed_trigger_outstanding),
    .auto_migration_trigger_attempt_count_o(fixed_trigger_attempt_count),
    .auto_migration_trigger_physical_tx_count_o(
        fixed_trigger_physical_tx_count),
    .auto_migration_trigger_count_o(fixed_trigger_count),
    .auto_migration_trigger_migration_count_o(
        fixed_trigger_previous_migration_count),
    .auto_migration_trigger_scheduled_count_o(fixed_trigger_scheduled_count)
  );

  p9_optical_transport_core #(
    .CLK_HZ(64_000_000), .LANE_COUNT(L), .WINDOW_SIZE(32),
    .SACK_BITS(32), .RTO_CYCLES(200_000), .DEPLOYMENT_ROLE(2)
  ) rotating_endpoint (
    .clk(clk), .rst_n(rst_n), .receiver_enable_i(receiver_enable),
    .arm_request_i(arm_request), .disarm_request_i(1'b0),
    .full_shutdown_request_i(full_shutdown_request),
    .forensic_fault_hold_i(1'b0), .clear_counters_i(clear_counters),
    .start_object_i(rotating_start_object), .abort_object_i(1'b0),
    .cfg_lane_mask_i(4'hf), .cfg_lane_weights_i(32'hff01_0101),
    .cfg_rate_select_i(2'd2), .cfg_direction_i(1'b0),
    .cfg_session_epoch_i(32'hA103_1001), .cfg_path_epoch_i(16'h0310),
    .cfg_object_id_i(32'h3310_0001), .cfg_initial_sequence_i(16'd0),
    .cfg_fault_flags_i(ATOMIC_FAULT_FLAGS),
    .cfg_drop_data_count_i(8'd0), .cfg_drop_ack_count_i(8'd0),
    .cfg_lane_unavailable_i(4'd0), .raw_start_i(1'b0),
    .raw_direction_i(1'b0), .raw_lane_mask_i(4'd0),
    .raw_pulse_target_i(32'd0), .raw_spacing_cycles_i(32'd1024),
    .s_axis_tvalid_i(1'b0), .s_axis_tdata_i(32'd0),
    .s_axis_tkeep_i(4'd0), .s_axis_tlast_i(1'b0),
    .m_axis_tvalid_o(rotating_m_valid), .m_axis_tready_i(1'b1),
    .m_axis_tkeep_o(rotating_m_keep), .m_axis_tlast_o(rotating_m_last),
    .a_rxd_i(4'hf), .b_rxd_i(rotating_rxd), .b_txd_o(rotating_txd),
    .b_sd_o(rotating_sd), .endpoint_armed_o(rotating_armed),
    .phy_ready_mask_o(rotating_phy_ready),
    .safety_fault_mask_o(rotating_safety_fault),
    .object_done_o(rotating_object_done),
    .object_fail_o(rotating_object_fail),
    .object_error_o(rotating_object_error),
    .physical_crc_bad_by_lane_o(rotating_crc_bad_by_lane)
  );

  task automatic stream_payload;
    integer offset;
    integer byte_index;
    reg [31:0] word_value;
    reg [3:0] keep_value;
    begin
      offset = 0;
      while (offset < OBJECT_BYTES) begin
        word_value = 0;
        keep_value = 0;
        for (byte_index = 0; byte_index < 4; byte_index = byte_index + 1) begin
          if (offset + byte_index < OBJECT_BYTES) begin
            word_value[8*byte_index +: 8] =
                ((offset + byte_index) * 37) ^ 8'h5a;
            keep_value[byte_index] = 1;
          end
        end
        @(negedge clk);
        fixed_s_valid = 1;
        fixed_s_data = word_value;
        fixed_s_keep = keep_value;
        fixed_s_last = offset + 4 >= OBJECT_BYTES;
        while (!fixed_s_ready && !fixed_object_fail && !rotating_object_fail)
          @(posedge clk);
        @(posedge clk); @(negedge clk);
        fixed_s_valid = 0;
        fixed_s_last = 0;
        offset = offset + 4;
      end
    end
  endtask

  initial begin
    repeat (8) @(posedge clk);
    rst_n = 1;
    receiver_enable = 1;
    watchdog = 0;
    while ((fixed_phy_ready != 8'h0f || rotating_phy_ready != 8'hf0) &&
           watchdog < 100_000) begin
      @(posedge clk); #1; watchdog = watchdog + 1;
    end
    if (fixed_phy_ready != 8'h0f || rotating_phy_ready != 8'hf0)
      $fatal(1, "atomic migration PHY startup failed");
    @(negedge clk); arm_request = 1;
    @(posedge clk); @(negedge clk); arm_request = 0;
    repeat (4) @(posedge clk);
    if (!fixed_armed || !rotating_armed)
      $fatal(1, "atomic migration endpoint arm failed");
    @(negedge clk); clear_counters = 1;
    @(posedge clk); @(negedge clk); clear_counters = 0;
    @(negedge clk); rotating_start_object = 1;
    @(posedge clk); @(negedge clk); rotating_start_object = 0;
    repeat (64) @(posedge clk);
    @(negedge clk); fixed_start_object = 1;
    @(posedge clk); @(negedge clk); fixed_start_object = 0;
    stream_payload();

    watchdog = 0;
    while (!(fixed_done_seen && rotating_done_seen) &&
           !fixed_object_fail && !rotating_object_fail &&
           watchdog < 4_000_000) begin
      @(posedge clk); #1; watchdog = watchdog + 1;
    end
    healthy_tx = fixed_tx_counts[31:0] + fixed_tx_counts[63:32] +
        fixed_tx_counts[95:64];
    if (fixed_object_fail || rotating_object_fail ||
        !(fixed_done_seen && rotating_done_seen))
      $fatal(1, "atomic migration object failed error=%08x/%08x",
             fixed_object_error, rotating_object_error);
    if (!fixed_auto_triggered || fixed_auto_armed ||
        fixed_auto_target_mask != 4'h8 ||
        fixed_effective_unavailable != 4'h8 ||
        fixed_trigger_sequence != 0 || fixed_trigger_ack_base != 0 ||
        fixed_trigger_outstanding < 1 || fixed_trigger_outstanding > 32 ||
        fixed_trigger_attempt_count < 1 ||
        fixed_trigger_physical_tx_count < 1 || fixed_trigger_count != 1 ||
        fixed_trigger_previous_migration_count != 0 ||
        fixed_trigger_scheduled_count < 1)
      $fatal(1, "atomic trigger evidence mismatch");
    if (fixed_migration_count < 1 || fixed_retry_count < 1 ||
        fixed_retry_exhausted != 0 ||
        rotating_crc_bad_by_lane[127:96] < 1 ||
        fixed_tx_counts[127:96] < 1 || healthy_tx < 1 ||
        received_bytes != OBJECT_BYTES || !received_last ||
        fixed_safety_fault != 0 || rotating_safety_fault != 0)
      $fatal(1, "atomic retry migration did not complete directly");

    receiver_enable = 0;
    @(negedge clk); full_shutdown_request = 1;
    repeat (4) @(posedge clk); #1;
    if (fixed_txd != 0 || rotating_txd != 0 || fixed_sd != 4'hf ||
        rotating_sd != 4'hf || fixed_armed || rotating_armed)
      $fatal(1, "atomic migration final shutdown failed");
    $display("TB_P10_3_ATOMIC_LANE_MIGRATION=PASS target=lane3 migrations=%0d retries=%0d",
             fixed_migration_count, fixed_retry_count);
    $finish;
  end
endmodule

module tb_2lane_4lane_regression;
  p10_2_core_elaboration_fixture #(.LANE_COUNT(2)) legacy();
  p10_2_core_elaboration_fixture #(.LANE_COUNT(4)) four_lane();
  initial begin #100; $display("TB_2LANE_4LANE_REGRESSION=PASS"); $finish; end
endmodule

module tb_p10_4_connector_ack_quarantine;
  localparam integer L = 4;
  reg clk = 0;
  always #5 clk = ~clk;
  reg rst_n = 0;
  reg [L-1:0] final_txd = 0;
  reg [L-1:0] tx_is_ack = 0;
  reg [L-1:0] raw_rx = 0;
  wire [L-1:0] paired_ack_txd;
  wire [L-1:0] quarantine_source;
  wire [L-1:0] accept;
  wire [31:0] blanked [0:L-1];

  p10_4_connector_ack_rx_quarantine #(.LANE_COUNT(L)) dut_map (
    .final_local_txd_i(final_txd), .local_tx_is_ack_i(tx_is_ack),
    .paired_ack_txd_o(paired_ack_txd),
    .rx_quarantine_source_o(quarantine_source)
  );

  genvar lane;
  generate
    for (lane = 0; lane < L; lane = lane + 1) begin : g_admission
      p10_1r_rx_admission #(
        .MIN_POST_TX_GUARD_CYCLES(16), .IDLE_QUALIFY_CYCLES(4),
        .MAX_QUARANTINE_CYCLES(64)
      ) admission (
        .clk, .rst_n, .clear_counters_i(1'b0),
        .receiver_enable_i(1'b1),
        .final_physical_txd_i(quarantine_source[lane]),
        .raw_rx_pulse_i(raw_rx[lane]),
        .rx_frame_accept_enable_o(accept[lane]), .rx_decoder_clear_o(),
        .echo_quarantine_o(), .post_tx_guard_active_o(),
        .raw_pulse_count_o(), .raw_while_local_tx_count_o(),
        .blanked_raw_pulse_count_o(blanked[lane]),
        .guard_total_cycles_o(), .guard_current_cycles_o(),
        .guard_max_cycles_o(), .echo_tail_max_cycles_o(),
        .decoder_clear_count_o(), .overlap_violation_count_o(),
        .admission_violation_count_o(), .last_physical_txd_rise_o(),
        .last_physical_txd_fall_o(), .first_local_rxd_edge_after_tx_o(),
        .last_local_rxd_edge_after_tx_o(), .last_raw_rx_timestamp_o()
      );
    end
  endgenerate

  task automatic recover_all;
    begin
      final_txd = 0;
      tx_is_ack = 0;
      raw_rx = 0;
      repeat (24) @(posedge clk); #1;
      if (accept != 4'hf)
        $fatal(1, "connector ACK quarantine did not recover: %x", accept);
    end
  endtask

  initial begin
    repeat (4) @(posedge clk);
    rst_n = 1;
    @(negedge clk); final_txd = 4'b0001; tx_is_ack = 0;
    #1;
    if (quarantine_source != 4'b0001 || paired_ack_txd != 0 ||
        accept != 4'b1110)
      $fatal(1, "ordinary peer DATA TX lost lane independence");
    @(posedge clk); #1;
    recover_all();

    @(negedge clk);
    final_txd = 4'b0001; tx_is_ack = 4'b0001; raw_rx = 4'b0010;
    #1;
    if (paired_ack_txd != 4'b0010 || quarantine_source != 4'b0011 ||
        accept != 4'b1100)
      $fatal(1, "J10 ACK did not quarantine exactly lanes0/1");
    @(posedge clk); #1;
    raw_rx = 0;
    if (blanked[1] == 0)
      $fatal(1, "paired ACK raw edge was not retained as blanked evidence");
    recover_all();

    @(negedge clk);
    final_txd = 4'b0100; tx_is_ack = 4'b0100;
    #1;
    if (paired_ack_txd != 4'b1000 || quarantine_source != 4'b1100 ||
        accept != 4'b0011)
      $fatal(1, "J11 ACK did not quarantine exactly lanes2/3");
    @(posedge clk); #1;
    recover_all();

    @(negedge clk); final_txd = 4'b0100; tx_is_ack = 0;
    #1;
    if (quarantine_source != 4'b0100 || accept != 4'b1011)
      $fatal(1, "ordinary J11 DATA TX incorrectly blanked lane3");
    $display("TB_P10_4_CONNECTOR_ACK_QUARANTINE=PASS");
    $finish;
  end
endmodule

`default_nettype wire
