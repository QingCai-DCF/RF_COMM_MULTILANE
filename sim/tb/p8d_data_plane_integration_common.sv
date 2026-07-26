`timescale 1ns/1ps
module p8d_data_plane_integration_common #(
  parameter int LANE_COUNT=8,
  parameter int WINDOW_SIZE=64,
  parameter int SACK_BITS=64
);
  localparam int LANE_WIDTH=$clog2(LANE_COUNT);
  logic clk=0; always #5 clk=~clk;
  logic rst_n,clear_counters,session_reset,abort_all;
  logic [31:0] session_epoch;
  logic [15:0] path_epoch;
  logic path_epoch_valid;
  logic [LANE_COUNT*8-1:0] lane_weights;
  logic [LANE_COUNT-1:0] active_lane_mask,lane_ready,lane_health,mapping_valid;
  logic [LANE_COUNT-1:0] frame_admission,lane_tx_permit,duty_headroom,fault_free;
  logic global_permit_effective,endpoint_armed,tx_kill_active;
  logic [15:0] peer_receiver_credit;
  logic tx_allocate_valid,tx_allocate_ready,tx_allocate_pulse;
  logic [15:0] tx_allocate_payload_ref,tx_allocate_payload_length;
  logic [15:0] tx_allocate_descriptor,tx_allocated_sequence;
  logic [2:0] tx_allocate_priority;
  logic physical_attempt_valid,physical_attempt_ready;
  logic [$clog2(WINDOW_SIZE)-1:0] physical_attempt_entry;
  logic [15:0] physical_attempt_sequence,physical_attempt_payload_ref;
  logic [15:0] physical_attempt_payload_length,physical_attempt_descriptor;
  logic [LANE_WIDTH-1:0] physical_attempt_lane;
  logic [15:0] physical_attempt_path_epoch;
  logic physical_attempt_is_retry;
  logic peer_ack_valid;
  logic [31:0] peer_ack_session_epoch;
  logic [15:0] peer_ack_base;
  logic [SACK_BITS-1:0] peer_ack_bitmap;
  logic [$clog2(SACK_BITS):0] peer_ack_width;
  logic rx_frame_valid,rx_frame_ready,rx_l1_valid;
  logic [31:0] rx_session_epoch;
  logic [15:0] rx_sequence,rx_path_epoch,rx_payload_ref,rx_payload_length;
  logic rx_delivery_valid,rx_delivery_ready;
  logic [15:0] rx_delivery_sequence,rx_delivery_payload_ref,rx_delivery_payload_length;
  logic ack_control_event,ack_direction_boundary,ack_explicit_request;
  logic local_ack_valid,local_ack_ready;
  logic [31:0] local_ack_session_epoch;
  logic [15:0] local_ack_base,local_ack_receiver_credit;
  logic [SACK_BITS-1:0] local_ack_bitmap;
  logic [$clog2(SACK_BITS):0] local_ack_width;
  logic [15:0] tx_next_sequence,tx_ack_base;
  logic [$clog2(WINDOW_SIZE+1)-1:0] tx_outstanding_count;
  logic [31:0] tx_migration_count,rx_duplicate_count;
  logic [3:0] scheduler_last_defer_reason;
  integer physical_attempts;
  integer delivered;
  integer attempt_before;
  logic [LANE_WIDTH-1:0] last_attempt_lane;
  logic [15:0] last_attempt_sequence;

  ir_data_plane_top #(
    .LANE_COUNT(LANE_COUNT),.WINDOW_SIZE(WINDOW_SIZE),.SACK_BITS(SACK_BITS),
    .MAX_RETRY(3),.RTO_CYCLES(16)
  ) dut (
    .clk,.rst_n,.clear_counters_i(clear_counters),.session_reset_i(session_reset),
    .initial_sequence_i(16'd0),
    .abort_all_i(abort_all),.session_epoch_i(session_epoch),.path_epoch_i(path_epoch),
    .path_epoch_valid_i(path_epoch_valid),.lane_weights_i(lane_weights),
    .active_lane_mask_i(active_lane_mask),.lane_ready_i(lane_ready),
    .lane_health_i(lane_health),.mapping_valid_i(mapping_valid),
    .frame_admission_i(frame_admission),.lane_tx_permit_i(lane_tx_permit),
    .duty_headroom_i(duty_headroom),.fault_free_i(fault_free),
    .global_permit_effective_i(global_permit_effective),.endpoint_armed_i(endpoint_armed),
    .tx_kill_active_i(tx_kill_active),.peer_receiver_credit_i(peer_receiver_credit),
    .tx_allocate_valid_i(tx_allocate_valid),.tx_allocate_ready_o(tx_allocate_ready),
    .tx_allocate_payload_ref_i(tx_allocate_payload_ref),
    .tx_allocate_payload_length_i(tx_allocate_payload_length),
    .tx_allocate_descriptor_i(tx_allocate_descriptor),
    .tx_allocate_priority_i(tx_allocate_priority),.tx_allocate_pulse_o(tx_allocate_pulse),
    .tx_allocated_sequence_o(tx_allocated_sequence),
    .physical_attempt_valid_o(physical_attempt_valid),
    .physical_attempt_ready_i(physical_attempt_ready),
    .physical_attempt_entry_o(physical_attempt_entry),
    .physical_attempt_sequence_o(physical_attempt_sequence),
    .physical_attempt_payload_ref_o(physical_attempt_payload_ref),
    .physical_attempt_payload_length_o(physical_attempt_payload_length),
    .physical_attempt_descriptor_o(physical_attempt_descriptor),
    .physical_attempt_lane_o(physical_attempt_lane),
    .physical_attempt_path_epoch_o(physical_attempt_path_epoch),
    .physical_attempt_is_retry_o(physical_attempt_is_retry),
    .peer_ack_valid_i(peer_ack_valid),.peer_ack_session_epoch_i(peer_ack_session_epoch),
    .peer_ack_base_i(peer_ack_base),.peer_ack_bitmap_i(peer_ack_bitmap),
    .peer_ack_width_i(peer_ack_width),.rx_frame_valid_i(rx_frame_valid),
    .rx_frame_ready_o(rx_frame_ready),.rx_l1_valid_i(rx_l1_valid),
    .rx_session_epoch_i(rx_session_epoch),.rx_sequence_i(rx_sequence),
    .rx_path_epoch_i(rx_path_epoch),.rx_payload_ref_i(rx_payload_ref),
    .rx_payload_length_i(rx_payload_length),.rx_delivery_valid_o(rx_delivery_valid),
    .rx_delivery_ready_i(rx_delivery_ready),.rx_delivery_sequence_o(rx_delivery_sequence),
    .rx_delivery_payload_ref_o(rx_delivery_payload_ref),
    .rx_delivery_payload_length_o(rx_delivery_payload_length),
    .ack_control_event_i(ack_control_event),
    .ack_direction_boundary_i(ack_direction_boundary),
    .ack_explicit_request_i(ack_explicit_request),.local_ack_valid_o(local_ack_valid),
    .local_ack_ready_i(local_ack_ready),.local_ack_session_epoch_o(local_ack_session_epoch),
    .local_ack_base_o(local_ack_base),.local_ack_bitmap_o(local_ack_bitmap),
    .local_ack_width_o(local_ack_width),
    .local_ack_receiver_credit_o(local_ack_receiver_credit),
    .tx_next_sequence_o(tx_next_sequence),.tx_ack_base_o(tx_ack_base),
    .tx_outstanding_count_o(tx_outstanding_count),
    .tx_migration_count_o(tx_migration_count),.rx_duplicate_count_o(rx_duplicate_count),
    .scheduler_last_defer_reason_o(scheduler_last_defer_reason)
  );

  task automatic check_expect(input logic condition,input string message);
    if(!condition) $fatal(1,"DATA_PLANE_INTEGRATION_EXPECT_FAIL: %s",message);
  endtask
  task automatic allocate(input integer tag);
    begin
      @(negedge clk);tx_allocate_payload_ref=tag;tx_allocate_payload_length=128;
      tx_allocate_descriptor=tag;tx_allocate_priority=tag[2:0];tx_allocate_valid=1;
      while(!tx_allocate_ready) @(negedge clk);
      @(posedge clk);#1;tx_allocate_valid=0;
      check_expect(tx_allocate_pulse,"allocation is accepted once");
    end
  endtask
  task automatic acknowledge(input logic [15:0] base);
    begin
      @(negedge clk);peer_ack_session_epoch=session_epoch;peer_ack_base=base;
      peer_ack_bitmap='0;peer_ack_width=SACK_BITS;peer_ack_valid=1;
      @(posedge clk);#1;peer_ack_valid=0;
    end
  endtask
  task automatic receive(input logic [15:0] seq,input logic [15:0] payload);
    begin
      @(negedge clk);rx_session_epoch=session_epoch;rx_sequence=seq;rx_path_epoch=path_epoch;
      rx_payload_ref=payload;rx_payload_length=64;rx_l1_valid=1;rx_frame_valid=1;
      while(!rx_frame_ready) @(negedge clk);
      @(posedge clk);#1;rx_frame_valid=0;
    end
  endtask
  task automatic wait_attempt_count(input integer target);
    integer timeout;
    begin
      timeout=0;
      while(physical_attempts<target && timeout<200) begin @(posedge clk);timeout=timeout+1;end
      check_expect(physical_attempts>=target,"physical attempt arrives within bounded time");
    end
  endtask
  task automatic wait_outstanding(input integer target);
    integer timeout;
    begin
      timeout=0;
      while(tx_outstanding_count!=target && timeout<240) begin
        @(posedge clk);#1;timeout=timeout+1;
      end
      check_expect(tx_outstanding_count==target,"ACK reclaim completes within bounded scan latency");
    end
  endtask

  always @(posedge clk) begin
    if(!rst_n) begin physical_attempts=0;delivered=0;end
    else begin
      if(physical_attempt_valid&&physical_attempt_ready) begin
        physical_attempts=physical_attempts+1;
        last_attempt_lane=physical_attempt_lane;
        last_attempt_sequence=physical_attempt_sequence;
      end
      if(rx_delivery_valid&&rx_delivery_ready) begin
        if(rx_delivery_sequence!==delivered[15:0])
          $fatal(1,"DATA_PLANE_DELIVERY_ORDER_FAIL got=%0d expected=%0d",
                 rx_delivery_sequence,delivered);
        delivered=delivered+1;
      end
    end
  end

  initial begin
    rst_n=0;clear_counters=0;session_reset=0;abort_all=0;session_epoch=32'h44;
    path_epoch=16'd3;path_epoch_valid=1;lane_weights={LANE_COUNT{8'h01}};
    active_lane_mask={LANE_COUNT{1'b1}};lane_ready={LANE_COUNT{1'b1}};
    lane_health={LANE_COUNT{1'b1}};mapping_valid={LANE_COUNT{1'b1}};
    frame_admission={LANE_COUNT{1'b1}};lane_tx_permit={LANE_COUNT{1'b1}};
    duty_headroom={LANE_COUNT{1'b1}};fault_free={LANE_COUNT{1'b1}};
    global_permit_effective=0;endpoint_armed=1;tx_kill_active=0;peer_receiver_credit=64;
    tx_allocate_valid=0;tx_allocate_payload_ref=0;tx_allocate_payload_length=0;
    tx_allocate_descriptor=0;tx_allocate_priority=0;physical_attempt_ready=1;
    peer_ack_valid=0;peer_ack_session_epoch=0;peer_ack_base=0;peer_ack_bitmap=0;
    peer_ack_width=SACK_BITS;rx_frame_valid=0;rx_l1_valid=1;rx_session_epoch=0;
    rx_sequence=0;rx_path_epoch=0;rx_payload_ref=0;rx_payload_length=0;
    rx_delivery_ready=0;ack_control_event=0;ack_direction_boundary=0;
    ack_explicit_request=0;local_ack_ready=0;physical_attempts=0;delivered=0;
    repeat(4) @(posedge clk);rst_n=1;@(posedge clk);#1;

    allocate(1);repeat(12) @(posedge clk);#1;
    check_expect(physical_attempts==0&&tx_outstanding_count==1,
                 "permit-low pauses attempts without losing global window ownership");
    global_permit_effective=1;wait_attempt_count(1);
    check_expect(last_attempt_sequence==0,"first global sequence is attempted once");
    acknowledge(1);wait_outstanding(0);check_expect(tx_outstanding_count==0,"ACK reclaims first entry");

    receive(1,16'h101);receive(1,16'h101);receive(0,16'h100);
    check_expect(rx_duplicate_count==1,"same frame on any lane is suppressed");
    ack_explicit_request=1;@(posedge clk);#1;ack_explicit_request=0;
    repeat(2) @(posedge clk);#1;
    check_expect(local_ack_valid&&local_ack_session_epoch==session_epoch,
                 "aggregated ACK exposes session/base/SACK state");
    local_ack_ready=1;@(posedge clk);#1;local_ack_ready=0;
    rx_delivery_ready=1;repeat(3) @(posedge clk);#1;
    check_expect(delivered==2,"out-of-order RX commits each application frame once");

    active_lane_mask='0;active_lane_mask[LANE_COUNT-1]=1;
    attempt_before=physical_attempts;allocate(2);wait_attempt_count(attempt_before+1);
    check_expect(last_attempt_lane==LANE_COUNT-1,"scheduler isolates all ineligible lanes");
    acknowledge(2);wait_outstanding(0);

    active_lane_mask='0;active_lane_mask[0]=1;global_permit_effective=0;
    attempt_before=physical_attempts;allocate(3);repeat(10) @(posedge clk);#1;
    check_expect(physical_attempts==attempt_before&&tx_outstanding_count==1,
                 "live permit recheck prevents a queued physical attempt");
    global_permit_effective=1;wait_attempt_count(attempt_before+1);
    check_expect(last_attempt_sequence==2,"re-arm restarts at a complete frame boundary");
    acknowledge(3);wait_outstanding(0);check_expect(tx_outstanding_count==0,"final outstanding entry reclaimed");

    $display("P8D_DATA_PLANE_GLOBAL_WINDOW_SAFETY_INTEGRATION_PASS=1");
    $display("P8D_DATA_PLANE_DUPLICATE_APPLICATION_DELIVERY_ZERO_PASS=1");
    if(LANE_COUNT==2) $display("TB_IR_DATA_PLANE_INTEGRATION_2LANE_PASS=1");
    else $display("TB_IR_DATA_PLANE_INTEGRATION_8LANE_PASS=1");
    $finish;
  end
endmodule
