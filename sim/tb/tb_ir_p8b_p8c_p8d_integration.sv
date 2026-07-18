`timescale 1ns/1ps
module tb_ir_p8b_p8c_p8d_integration;
  logic clk=0;always #5 clk=~clk;
  logic rst_n;
  logic [4:0] phase_m0;
  logic phase_valid;
  logic [1:0] direction;
  logic prepare_request,commit_event,prepare_ready,prepare_reject,shadow_valid;
  logic shadow_context_match,mapping_checks_pass,active_valid;
  logic [39:0] active_current_fixed;
  logic [23:0] active_current_bank;
  logic global_permit,arm_request,arm_accept,arm_reject;
  logic [7:0] startup_done,duty_history_valid,duty_fault,stuck_fault,duty_throttle;
  logic [7:0] physical_txd;
  logic permit_effective,endpoint_armed,tx_kill;
  logic tx_allocate_valid,tx_allocate_ready,tx_allocate_pulse;
  logic [15:0] tx_allocated_sequence;
  logic physical_attempt_valid,physical_attempt_ready;
  logic [5:0] physical_attempt_entry;
  logic [15:0] physical_attempt_sequence;
  logic [2:0] physical_attempt_lane;
  logic physical_attempt_retry;
  logic peer_ack_valid;
  logic [15:0] peer_ack_base;
  logic [6:0] peer_ack_width;
  logic [6:0] outstanding;
  integer attempts;
  logic [15:0] last_sequence;
  logic last_retry;

  ir_path_mapping_engine mapping (
    .clk,.rst_n,.phase_m0,.phase_valid,.direction,.direction_valid(1'b1),
    .prepare_request,.commit_event,.prepare_ready,.prepare_reject,.shadow_valid,
    .shadow_context_match,.mapping_checks_pass,.shadow_current_fixed(),
    .shadow_candidate_fixed(),.shadow_current_bank(),.shadow_candidate_bank(),
    .shadow_current_slot(),.shadow_candidate_slot(),.active_valid,
    .active_current_fixed,.active_candidate_fixed(),.active_current_bank,
    .active_candidate_bank(),.active_current_slot(),.active_candidate_slot()
  );

  ir_tfdu_safety_endpoint #(
    .PHYSICAL_MODULE_COUNT(8),.CLOCK_HZ(1000000),.STARTUP_US(2),
    .WINDOW_US(10),.MAX_CONTINUOUS_HIGH_US(1),.ASSERT_FILTER_CYCLES(2)
  ) safety (
    .clk,.rst_n,.global_permit_i(global_permit),.endpoint_arm_request_i(arm_request),
    .endpoint_disarm_request_i(1'b0),.full_shutdown_request_i(1'b0),
    .safety_fault_clear_request_i(1'b0),.telemetry_clear_i(1'b0),
    .history_invalidate_i(1'b0),.endpoint_fatal_fault_i(1'b0),
    .mapping_valid_i(active_valid),.receive_enable_i(8'hff),
    .physical_module_selected_i(8'hff),.bank_one_hot_valid_i(8'hff),
    .bank_fault_i(8'h00),.lane_tx_permit_i(8'hff),.path_epoch_valid_i(8'hff),
    .frame_admitted_i(8'h00),.txd_waveform_i(8'h00),.rxd_i(8'hff),
    .physical_txd_out_o(physical_txd),.physical_sd_o(),.physical_mode_o(),
    .rx_active_o(),.startup_done_o(startup_done),.global_permit_raw_safe_o(),
    .global_permit_sync_o(),.global_permit_sync_valid_o(),
    .global_permit_effective_o(permit_effective),.endpoint_armed_o(endpoint_armed),
    .arm_accept_pulse_o(arm_accept),.arm_reject_pulse_o(arm_reject),
    .arm_reject_reason_o(),.tx_kill_active_o(tx_kill),.effective_tx_enable_mask_o(),
    .duty_hard_fault_mask_o(duty_fault),.stuck_high_fault_mask_o(stuck_fault),
    .endpoint_fatal_fault_o(),.partial_frame_abort_block_o(),
    .global_permit_rise_count_o(),.global_permit_fall_count_o(),
    .global_permit_drop_during_frame_count_o(),.global_permit_rearm_count_o(),
    .last_global_permit_drop_reason_o(),.last_tx_kill_reason_o(),
    .safety_fault_clear_accept_pulse_o(),.rx_pulse_count_flat_o(),
    .rolling_high_cycles_flat_o(),.rolling_high_cycles_max_seen_flat_o(),
    .duty_headroom_cycles_flat_o(),.duty_target_throttle_count_flat_o(),
    .duty_hard_fault_count_flat_o(),.continuous_high_cycles_flat_o(),
    .longest_high_cycles_seen_flat_o(),.stuck_high_fault_count_flat_o(),
    .stuck_high_kill_count_flat_o(),.cooldown_remaining_flat_o(),.charge_count_flat_o(),
    .duty_history_valid_mask_o(duty_history_valid),.cooldown_active_mask_o(),
    .duty_target_throttle_mask_o(duty_throttle)
  );

  ir_data_plane_top #(.LANE_COUNT(8),.WINDOW_SIZE(64),.SACK_BITS(64),
                      .MAX_RETRY(3),.RTO_CYCLES(16)) data_plane (
    .clk,.rst_n,.clear_counters_i(1'b0),.session_reset_i(1'b0),.abort_all_i(1'b0),
    .session_epoch_i(32'h88),.path_epoch_i(16'd1),.path_epoch_valid_i(active_valid&&phase_valid),
    .lane_weights_i(64'h0101010101010101),.active_lane_mask_i(8'hff),
    .lane_ready_i(8'hff),.lane_health_i(~(duty_fault|stuck_fault)),
    .mapping_valid_i({8{active_valid&&phase_valid}}),.frame_admission_i(8'hff),
    .lane_tx_permit_i(8'hff),.duty_headroom_i(startup_done&duty_history_valid&~duty_throttle),
    .fault_free_i(~(duty_fault|stuck_fault)),.global_permit_effective_i(permit_effective),
    .endpoint_armed_i(endpoint_armed),.tx_kill_active_i(tx_kill),
    .peer_receiver_credit_i(16'd64),.tx_allocate_valid_i(tx_allocate_valid),
    .tx_allocate_ready_o(tx_allocate_ready),.tx_allocate_payload_ref_i(16'h55),
    .tx_allocate_payload_length_i(16'd128),.tx_allocate_descriptor_i(16'h77),
    .tx_allocate_priority_i(3'd1),.tx_allocate_pulse_o(tx_allocate_pulse),
    .tx_allocated_sequence_o(tx_allocated_sequence),
    .physical_attempt_valid_o(physical_attempt_valid),
    .physical_attempt_ready_i(physical_attempt_ready),
    .physical_attempt_entry_o(physical_attempt_entry),
    .physical_attempt_sequence_o(physical_attempt_sequence),
    .physical_attempt_payload_ref_o(),.physical_attempt_payload_length_o(),
    .physical_attempt_descriptor_o(),.physical_attempt_lane_o(physical_attempt_lane),
    .physical_attempt_path_epoch_o(),.physical_attempt_is_retry_o(physical_attempt_retry),
    .peer_ack_valid_i(peer_ack_valid),.peer_ack_session_epoch_i(32'h88),
    .peer_ack_base_i(peer_ack_base),.peer_ack_bitmap_i(64'd0),
    .peer_ack_width_i(peer_ack_width),.rx_frame_valid_i(1'b0),.rx_frame_ready_o(),
    .rx_l1_valid_i(1'b1),.rx_session_epoch_i(32'h88),.rx_sequence_i(16'd0),
    .rx_path_epoch_i(16'd1),.rx_payload_ref_i(16'd0),.rx_payload_length_i(16'd0),
    .rx_delivery_valid_o(),.rx_delivery_ready_i(1'b1),.rx_delivery_sequence_o(),
    .rx_delivery_payload_ref_o(),.rx_delivery_payload_length_o(),
    .ack_control_event_i(1'b0),.ack_direction_boundary_i(1'b0),
    .ack_explicit_request_i(1'b0),.local_ack_valid_o(),.local_ack_ready_i(1'b1),
    .local_ack_session_epoch_o(),.local_ack_base_o(),.local_ack_bitmap_o(),
    .local_ack_width_o(),.local_ack_receiver_credit_o(),.tx_next_sequence_o(),
    .tx_ack_base_o(),.tx_outstanding_count_o(outstanding)
  );

  task automatic check_expect(input logic condition,input string message);
    if(!condition)$fatal(1,"P8BCD_INTEGRATION_EXPECT_FAIL: %s",message);
  endtask
  task automatic allocate;
    begin
      @(negedge clk);tx_allocate_valid=1;while(!tx_allocate_ready)@(negedge clk);
      @(posedge clk);#1;tx_allocate_valid=0;check_expect(tx_allocate_pulse,"entry allocated");
    end
  endtask
  task automatic ack(input logic [15:0] base);
    begin @(negedge clk);peer_ack_base=base;peer_ack_valid=1;
      @(posedge clk);#1;peer_ack_valid=0;end
  endtask
  task automatic wait_attempt(input integer target);
    integer timeout;
    begin timeout=0;while(attempts<target&&timeout<300)begin @(posedge clk);timeout=timeout+1;end
      check_expect(attempts>=target,"attempt admitted in bounded time");end
  endtask
  task automatic wait_outstanding(input integer target);
    integer timeout;
    begin timeout=0;while(outstanding!=target&&timeout<260)begin
      @(posedge clk);#1;timeout=timeout+1;end
      check_expect(outstanding==target,"bounded ACK reclaim completes");end
  endtask
  task automatic arm_endpoint;
    begin
      repeat(8)@(posedge clk);arm_request=1;@(posedge clk);#1;arm_request=0;
      check_expect(arm_accept&&endpoint_armed&&permit_effective,"explicit arm succeeds after filter");
    end
  endtask

  always @(posedge clk) begin
    if(!rst_n)attempts=0;
    else if(physical_attempt_valid&&physical_attempt_ready)begin
      attempts=attempts+1;last_sequence=physical_attempt_sequence;last_retry=physical_attempt_retry;
    end
  end

  initial begin
    rst_n=0;phase_m0=0;phase_valid=1;direction=2'b10;prepare_request=0;commit_event=0;
    global_permit=0;arm_request=0;tx_allocate_valid=0;physical_attempt_ready=1;
    peer_ack_valid=0;peer_ack_base=0;peer_ack_width=7'd64;attempts=0;
    repeat(4)@(posedge clk);rst_n=1;@(posedge clk);#1;
    prepare_request=1;@(posedge clk);#1;prepare_request=0;
    check_expect(prepare_ready&&shadow_valid&&mapping_checks_pass,"P8B mapping prepares valid permutation");
    commit_event=1;@(posedge clk);#1;commit_event=0;
    check_expect(active_valid,"P8B mapping commits atomically");
    repeat(16)@(posedge clk);global_permit=1;arm_endpoint();

    allocate();wait_attempt(1);check_expect(last_sequence==0&&!last_retry,"P8D initial attempt uses P8B/P8C admission");
    global_permit=0;repeat(24)@(posedge clk);#1;
    check_expect(attempts==1&&outstanding==1&&!endpoint_armed,
                 "P8C permit drop preserves unacked P8D ownership and kills retries");
    global_permit=1;arm_endpoint();wait_attempt(2);
    check_expect(last_sequence==0&&last_retry,"retry restarts whole frame after explicit re-arm");
    ack(1);wait_outstanding(0);check_expect(outstanding==0,"ACKed frame never retries or migrates again");

    phase_valid=0;allocate();repeat(20)@(posedge clk);#1;
    check_expect(attempts==2&&outstanding==1,"P8B invalid mapping blocks physical attempt");
    phase_valid=1;wait_attempt(3);check_expect(last_sequence==1,"mapping recovery admits queued global entry");
    ack(2);wait_outstanding(0);check_expect(outstanding==0&&physical_txd==0,"no data-plane control can bypass final Txd kill");
    $display("P8D_P8B_MAPPING_GATE_INTEGRATION_PASS=1");
    $display("P8D_P8C_SINGLE_PERMIT_FINAL_KILL_INTEGRATION_PASS=1");
    $display("P8D_PARTIAL_FRAME_NOT_RESUMED_PASS=1");
    $display("TB_IR_P8B_P8C_P8D_INTEGRATION_PASS=1");
    $finish;
  end
endmodule
