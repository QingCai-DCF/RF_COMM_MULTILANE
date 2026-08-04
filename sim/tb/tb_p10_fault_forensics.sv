`timescale 1ns/1ps
`default_nettype none

module tb_p10_fault_forensics;
  localparam integer LANES = 4;
  localparam integer MODULES = 4;
  localparam integer SNAPSHOT_WORDS = 64;
  localparam integer EVENT_DEPTH = 256;
  localparam integer EVENT_WORDS = 8;

  reg clk = 0;
  always #8 clk = ~clk;

  reg system_reset_n = 1;
  reg capture_fault = 0;
  reg [31:0] fault_cause = 0;
  reg effective_shutdown = 0;
  reg endpoint_armed = 0;
  reg tx_kill = 1;
  reg receiver_enable = 0;
  reg [MODULES-1:0] physical_txd = 0;
  reg [MODULES-1:0] physical_sd = 4'hf;
  reg [MODULES-1:0] physical_mode = 4'hf;
  reg [MODULES-1:0] phy_ready = 0;
  reg [MODULES-1:0] startup_done = 0;
  reg [MODULES-1:0] safety_fault = 0;
  reg [LANES-1:0] configured_lane_mask = 0;
  reg [LANES-1:0] unavailable_lane_mask = 0;
  reg [LANES-1:0] raw_lane_mask = 0;
  reg raw_busy = 0;
  reg raw_direction = 0;
  reg object_active = 0;
  reg object_done = 0;
  reg object_fail = 0;
  reg [31:0] object_id = 0;
  reg [31:0] object_error = 0;
  reg [15:0] tx_next_sequence = 0;
  reg [15:0] tx_ack_base = 0;
  reg [5:0] tx_outstanding = 0;
  reg [5:0] tx_outstanding_high_watermark = 0;
  reg [15:0] rx_base_sequence = 0;
  reg [31:0] rx_sack_bitmap = 0;
  reg [31:0] tx_attempt_count = 0;
  reg [31:0] tx_retry_count = 0;
  reg [31:0] tx_retry_exhausted_count = 0;
  reg [31:0] tx_timeout_count = 0;
  reg [31:0] tx_migration_count = 0;
  reg [31:0] input_byte_count = 0;
  reg [31:0] output_byte_count = 0;
  reg [MODULES*32-1:0] physical_tx_counts_flat = 0;
  reg [MODULES*32-1:0] tx_high_current_flat = 0;
  reg [MODULES*32-1:0] tx_high_max_flat = 0;
  reg [MODULES*32-1:0] duty_high_current_flat = 0;
  reg [MODULES*32-1:0] duty_high_max_flat = 0;
  reg [MODULES*32-1:0] duty_headroom_flat = 0;
  reg [MODULES*32-1:0] duty_target_throttle_count_flat = 0;
  reg [MODULES*32-1:0] duty_hard_fault_count_flat = 0;
  reg [MODULES*32-1:0] raw_rx_counts_flat = 0;
  reg [5:0] snapshot_read_index = 0;
  reg snapshot_read_strobe = 0;
  wire [31:0] snapshot_read_data;
  reg [7:0] event_read_index = 0;
  reg [2:0] event_read_word = 0;
  reg event_read_strobe = 0;
  wire [31:0] event_read_data;
  reg archive_digest_write = 0;
  reg [2:0] archive_digest_index = 0;
  reg [31:0] archive_digest_data = 0;
  reg archive_commit = 0;
  reg clear_key_write = 0;
  reg [31:0] clear_key = 0;
  reg checkpoint_event = 0;
  reg [31:0] checkpoint_tag = 0;
  wire first_fault_hold;
  wire frozen;
  wire post_trace_complete;
  wire snapshot_read_complete;
  wire event_read_complete;
  wire archive_committed;
  wire clear_armed;
  wire [31:0] fault_sequence;
  wire [63:0] fault_timestamp;
  wire [31:0] frozen_fault_cause;
  wire [31:0] pre_event_count;
  wire [31:0] post_event_count;
  wire [31:0] total_event_count;
  wire [31:0] clear_count;
  wire [31:0] clear_reject_count;
  wire [255:0] archive_digest;

  p10_fault_forensics #(
    .LANE_COUNT(LANES), .MODULE_COUNT(MODULES),
    .SNAPSHOT_WORDS(SNAPSHOT_WORDS), .EVENT_DEPTH(EVENT_DEPTH),
    .POST_EVENT_COUNT(8), .EVENT_WORDS(EVENT_WORDS),
    .SAMPLE_INTERVAL_CYCLES(16)
  ) dut (
    .clk, .system_reset_n_i(system_reset_n),
    .capture_fault_i(capture_fault), .fault_cause_i(fault_cause),
    .effective_shutdown_i(effective_shutdown),
    .endpoint_armed_i(endpoint_armed), .tx_kill_i(tx_kill),
    .receiver_enable_i(receiver_enable), .physical_txd_i(physical_txd),
    .physical_sd_i(physical_sd), .physical_mode_i(physical_mode),
    .phy_ready_i(phy_ready), .startup_done_i(startup_done),
    .safety_fault_i(safety_fault),
    .configured_lane_mask_i(configured_lane_mask),
    .unavailable_lane_mask_i(unavailable_lane_mask),
    .raw_lane_mask_i(raw_lane_mask), .raw_busy_i(raw_busy),
    .raw_direction_i(raw_direction), .object_active_i(object_active),
    .object_done_i(object_done), .object_fail_i(object_fail),
    .object_id_i(object_id), .object_error_i(object_error),
    .tx_next_sequence_i(tx_next_sequence), .tx_ack_base_i(tx_ack_base),
    .tx_outstanding_i(tx_outstanding),
    .tx_outstanding_high_watermark_i(tx_outstanding_high_watermark),
    .rx_base_sequence_i(rx_base_sequence),
    .rx_sack_bitmap_i(rx_sack_bitmap),
    .tx_attempt_count_i(tx_attempt_count), .tx_retry_count_i(tx_retry_count),
    .tx_retry_exhausted_count_i(tx_retry_exhausted_count),
    .tx_timeout_count_i(tx_timeout_count),
    .tx_migration_count_i(tx_migration_count),
    .input_byte_count_i(input_byte_count),
    .output_byte_count_i(output_byte_count),
    .physical_tx_counts_flat_i(physical_tx_counts_flat),
    .tx_high_current_flat_i(tx_high_current_flat),
    .tx_high_max_flat_i(tx_high_max_flat),
    .duty_high_current_flat_i(duty_high_current_flat),
    .duty_high_max_flat_i(duty_high_max_flat),
    .duty_headroom_flat_i(duty_headroom_flat),
    .duty_target_throttle_count_flat_i(duty_target_throttle_count_flat),
    .duty_hard_fault_count_flat_i(duty_hard_fault_count_flat),
    .raw_rx_counts_flat_i(raw_rx_counts_flat),
    .snapshot_read_index_i(snapshot_read_index),
    .snapshot_read_strobe_i(snapshot_read_strobe),
    .snapshot_read_data_o(snapshot_read_data),
    .event_read_index_i(event_read_index),
    .event_read_word_i(event_read_word),
    .event_read_strobe_i(event_read_strobe),
    .event_read_data_o(event_read_data),
    .archive_digest_write_i(archive_digest_write),
    .archive_digest_index_i(archive_digest_index),
    .archive_digest_data_i(archive_digest_data),
    .archive_commit_i(archive_commit),
    .clear_key_write_i(clear_key_write), .clear_key_i(clear_key),
    .checkpoint_event_i(checkpoint_event),
    .checkpoint_tag_i(checkpoint_tag),
    .first_fault_hold_o(first_fault_hold), .frozen_o(frozen),
    .post_trace_complete_o(post_trace_complete),
    .snapshot_read_complete_o(snapshot_read_complete),
    .event_read_complete_o(event_read_complete),
    .archive_committed_o(archive_committed), .clear_armed_o(clear_armed),
    .fault_sequence_o(fault_sequence), .fault_timestamp_o(fault_timestamp),
    .frozen_fault_cause_o(frozen_fault_cause),
    .pre_event_count_o(pre_event_count),
    .post_event_count_o(post_event_count),
    .total_event_count_o(total_event_count), .clear_count_o(clear_count),
    .clear_reject_count_o(clear_reject_count),
    .archive_digest_o(archive_digest)
  );

  task pulse_checkpoint(input [31:0] tag);
    begin
      @(negedge clk); checkpoint_tag = tag; checkpoint_event = 1;
      @(negedge clk); checkpoint_event = 0;
    end
  endtask

  task read_snapshot_word(input integer index);
    begin
      @(negedge clk); snapshot_read_index = index; snapshot_read_strobe = 1;
      @(negedge clk); snapshot_read_strobe = 0;
    end
  endtask

  task read_event_word(input integer entry, input integer word_index);
    begin
      @(negedge clk); event_read_index = entry; event_read_word = word_index;
      @(negedge clk); event_read_strobe = 1;
      @(negedge clk); event_read_strobe = 0;
    end
  endtask

  task write_digest_word(input integer index, input [31:0] value);
    begin
      @(negedge clk); archive_digest_index = index;
      archive_digest_data = value; archive_digest_write = 1;
      @(negedge clk); archive_digest_write = 0;
    end
  endtask

  task write_clear_key(input [31:0] value);
    begin
      @(negedge clk); clear_key = value; clear_key_write = 1;
      @(negedge clk); clear_key_write = 0;
    end
  endtask

  integer index;
  integer event_index;
  integer event_word_index;
  reg [31:0] total_at_fault;
  reg [7:0] observed_event_code;
  reg found_checkpoint_event;
  initial begin
    repeat (4) @(posedge clk);
    receiver_enable = 1;
    endpoint_armed = 1;
    tx_kill = 0;
    physical_sd = 0;
    phy_ready = 4'hf;
    startup_done = 4'hf;
    configured_lane_mask = 4'hf;
    object_active = 1;
    object_id = 32'h1234_5678;
    tx_next_sequence = 16'h0042;
    tx_ack_base = 16'h0020;
    tx_outstanding = 6'd12;
    tx_outstanding_high_watermark = 6'd24;
    rx_base_sequence = 16'h001f;
    rx_sack_bitmap = 32'h0000_00ff;
    tx_attempt_count = 32'd1000;
    tx_retry_count = 32'd7;
    tx_retry_exhausted_count = 32'd1;
    tx_timeout_count = 32'd3;
    tx_migration_count = 32'd2;
    input_byte_count = 32'd4096;
    output_byte_count = 32'd2048;
    physical_tx_counts_flat[31:0] = 32'd101;
    physical_tx_counts_flat[63:32] = 32'd202;
    physical_tx_counts_flat[95:64] = 32'd303;
    physical_tx_counts_flat[127:96] = 32'd404;
    tx_high_current_flat[63:32] = 32'd64;
    tx_high_max_flat[63:32] = 32'd64;
    duty_high_current_flat[63:32] = 32'd11519;
    duty_high_max_flat[63:32] = 32'd11519;
    duty_headroom_flat[63:32] = 32'd1;
    duty_target_throttle_count_flat[63:32] = 32'd9;
    duty_hard_fault_count_flat[63:32] = 32'd1;
    raw_rx_counts_flat[63:32] = 32'd777;
    pulse_checkpoint(32'h0000_0400);
    repeat (20) @(posedge clk);

    // First fault snapshots live state and asserts a persistent one-way hold.
    @(negedge clk);
    safety_fault = 4'b0010;
    object_fail = 1;
    object_error = 32'h5009_0002;
    fault_cause = 32'h00A5_0102;
    capture_fault = 1;
    @(negedge clk);
    capture_fault = 0;
    safety_fault = 0;
    object_fail = 0;
    object_active = 0;
    endpoint_armed = 0;
    tx_kill = 1;
    effective_shutdown = 1;
    physical_txd = 0;
    physical_sd = 4'hf;
    repeat (12) @(posedge clk);

    if (!frozen || !first_fault_hold || !post_trace_complete)
      $fatal(1, "first fault did not freeze and complete post trace");
    if (fault_sequence != 1 || frozen_fault_cause != 32'h00A5_0102)
      $fatal(1, "first-fault identity mismatch");
    if (post_event_count != 8 || total_event_count == 0)
      $fatal(1, "event count mismatch");
    total_at_fault = total_event_count;
    snapshot_read_index = 0;
    #1;
    if (snapshot_read_data != 32'h4646_5331)
      $fatal(1, "snapshot magic mismatch");
    snapshot_read_index = 8;
    #1;
    if (snapshot_read_data != 32'h1234_5678)
      $fatal(1, "object ID not frozen");
    snapshot_read_index = 34; // module1 tx count: 24 + 10*1
    #1;
    if (snapshot_read_data != 32'd202)
      $fatal(1, "module TX count not frozen");
    snapshot_read_index = 35;
    #1;
    if (snapshot_read_data != 32'd64)
      $fatal(1, "continuous-high state not frozen");
    snapshot_read_index = 37;
    #1;
    if (snapshot_read_data != 32'd11519)
      $fatal(1, "rolling-duty state not frozen");

    // Functional reset is observable but may not clear frozen evidence.
    system_reset_n = 0;
    repeat (4) @(posedge clk);
    system_reset_n = 1;
    repeat (2) @(posedge clk);
    if (!frozen || !first_fault_hold || total_event_count != total_at_fault)
      $fatal(1, "functional reset erased or changed frozen evidence");

    // Read actual banked event data before exercising the ordered archival
    // interlock.  This catches a disconnected/inferred-memory-only shell and
    // proves that both the event header and checkpoint payload survive.
    found_checkpoint_event = 1'b0;
    for (event_index = 0; event_index < total_at_fault;
         event_index = event_index + 1) begin
      read_event_word(event_index, 0);
      if (event_read_data[31:16] != 16'h4646)
        $fatal(1, "event BRAM record magic mismatch");
      observed_event_code = event_read_data[15:8];
      read_event_word(event_index, 7);
      if (observed_event_code == 8'h07 &&
          event_read_data == 32'h0000_0400)
        found_checkpoint_event = 1'b1;
    end
    if (!found_checkpoint_event)
      $fatal(1, "checkpoint event payload missing from event BRAM");

    for (index = 0; index < SNAPSHOT_WORDS; index = index + 1)
      read_snapshot_word(index);
    if (!snapshot_read_complete)
      $fatal(1, "ordered snapshot read interlock did not complete");
    for (event_index = 0; event_index < total_at_fault;
         event_index = event_index + 1)
      for (event_word_index = 0; event_word_index < EVENT_WORDS;
           event_word_index = event_word_index + 1)
        read_event_word(event_index, event_word_index);
    if (!event_read_complete)
      $fatal(1, "ordered event read interlock did not complete");

    for (index = 0; index < 8; index = index + 1)
      write_digest_word(index, 32'h1020_3040 + index);
    @(negedge clk); archive_commit = 1;
    @(negedge clk); archive_commit = 0;
    repeat (2) @(posedge clk);
    if (!archive_committed || archive_digest == 0)
      $fatal(1, "archive commit interlock did not complete");

    // An explicit key sequence is still rejected unless all physical outputs
    // are in verified full shutdown.
    physical_sd = 0;
    write_clear_key(32'h4652_4F5A);
    if (clear_armed || !frozen)
      $fatal(1, "unsafe clear arm was accepted");
    physical_sd = 4'hf;
    write_clear_key(32'h4652_4F5A);
    if (!clear_armed)
      $fatal(1, "safe clear arm was rejected");
    write_clear_key(32'h434C_5241);
    repeat (2) @(posedge clk);
    if (frozen || first_fault_hold || clear_count != 1)
      $fatal(1, "explicit archived clear did not release recorder");

    $display("P10_FAULT_FORENSICS_XSIM=PASS");
    $finish;
  end
endmodule

`default_nettype wire
