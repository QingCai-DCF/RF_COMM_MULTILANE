`timescale 1ns/1ps
`default_nettype none

// P10 first-fault forensic recorder.
//
// This block deliberately has no functional reset input.  Configuration
// initializes it once; ordinary AXI/PS/transport resets and endpoint shutdown
// do not erase the first-fault snapshot or event BRAM.  FPGA reconfiguration
// and loss of PL power necessarily destroy this volatile state, so the host
// must archive it before loading the independent shutdown image.
//
// The recorder is observational.  first_fault_hold_o is the only output that
// enters the safety path, and it can only add a persistent shutdown/kill.  No
// recorder state can permit TX, provide backpressure, or alter protocol data.
module p10_fault_forensics #(
  parameter integer CLK_HZ = 64_000_000,
  parameter integer LANE_COUNT = 4,
  parameter integer MODULE_COUNT = 4,
  parameter integer SNAPSHOT_WORDS = 64,
  parameter integer EVENT_DEPTH = 256,
  parameter integer POST_EVENT_COUNT = 8,
  parameter integer EVENT_WORDS = 8,
  parameter integer SAMPLE_INTERVAL_CYCLES = 1024
) (
  input  wire                              clk,
  input  wire                              system_reset_n_i,
  input  wire                              capture_fault_i,
  input  wire [31:0]                       fault_cause_i,
  input  wire                              effective_shutdown_i,
  input  wire                              endpoint_armed_i,
  input  wire                              tx_kill_i,
  input  wire                              receiver_enable_i,
  input  wire [MODULE_COUNT-1:0]           physical_txd_i,
  input  wire [MODULE_COUNT-1:0]           physical_sd_i,
  input  wire [MODULE_COUNT-1:0]           physical_mode_i,
  input  wire [MODULE_COUNT-1:0]           phy_ready_i,
  input  wire [MODULE_COUNT-1:0]           startup_done_i,
  input  wire [MODULE_COUNT-1:0]           safety_fault_i,
  input  wire [LANE_COUNT-1:0]             configured_lane_mask_i,
  input  wire [LANE_COUNT-1:0]             unavailable_lane_mask_i,
  input  wire [LANE_COUNT-1:0]             raw_lane_mask_i,
  input  wire                              raw_busy_i,
  input  wire                              raw_direction_i,
  input  wire                              object_active_i,
  input  wire                              object_done_i,
  input  wire                              object_fail_i,
  input  wire [31:0]                       object_id_i,
  input  wire [31:0]                       object_error_i,
  input  wire [15:0]                       tx_next_sequence_i,
  input  wire [15:0]                       tx_ack_base_i,
  input  wire [5:0]                        tx_outstanding_i,
  input  wire [5:0]                        tx_outstanding_high_watermark_i,
  input  wire [15:0]                       rx_base_sequence_i,
  input  wire [31:0]                       rx_sack_bitmap_i,
  input  wire [31:0]                       tx_attempt_count_i,
  input  wire [31:0]                       tx_retry_count_i,
  input  wire [31:0]                       tx_retry_exhausted_count_i,
  input  wire [31:0]                       tx_timeout_count_i,
  input  wire [31:0]                       tx_migration_count_i,
  input  wire [31:0]                       input_byte_count_i,
  input  wire [31:0]                       output_byte_count_i,
  input  wire [MODULE_COUNT*32-1:0]        physical_tx_counts_flat_i,
  input  wire [MODULE_COUNT*32-1:0]        tx_high_current_flat_i,
  input  wire [MODULE_COUNT*32-1:0]        tx_high_max_flat_i,
  input  wire [MODULE_COUNT*32-1:0]        duty_high_current_flat_i,
  input  wire [MODULE_COUNT*32-1:0]        duty_high_max_flat_i,
  input  wire [MODULE_COUNT*32-1:0]        duty_headroom_flat_i,
  input  wire [MODULE_COUNT*32-1:0]        duty_target_throttle_count_flat_i,
  input  wire [MODULE_COUNT*32-1:0]        duty_hard_fault_count_flat_i,
  input  wire [MODULE_COUNT*32-1:0]        raw_rx_counts_flat_i,

  input  wire [$clog2(SNAPSHOT_WORDS)-1:0] snapshot_read_index_i,
  input  wire                              snapshot_read_strobe_i,
  output wire [31:0]                       snapshot_read_data_o,
  input  wire [$clog2(EVENT_DEPTH)-1:0]    event_read_index_i,
  input  wire [$clog2(EVENT_WORDS)-1:0]    event_read_word_i,
  input  wire                              event_read_strobe_i,
  output wire [31:0]                       event_read_data_o,
  input  wire                              archive_digest_write_i,
  input  wire [2:0]                        archive_digest_index_i,
  input  wire [31:0]                       archive_digest_data_i,
  input  wire                              archive_commit_i,
  input  wire                              clear_key_write_i,
  input  wire [31:0]                       clear_key_i,
  input  wire                              checkpoint_event_i,
  input  wire [31:0]                       checkpoint_tag_i,

  output wire                              first_fault_hold_o,
  output wire                              frozen_o,
  output wire                              post_trace_complete_o,
  output wire                              snapshot_read_complete_o,
  output wire                              event_read_complete_o,
  output wire                              archive_committed_o,
  output wire                              clear_armed_o,
  output wire [31:0]                       fault_sequence_o,
  output wire [63:0]                       fault_timestamp_o,
  output wire [31:0]                       frozen_fault_cause_o,
  output wire [31:0]                       pre_event_count_o,
  output wire [31:0]                       post_event_count_o,
  output wire [31:0]                       total_event_count_o,
  output wire [31:0]                       clear_count_o,
  output wire [31:0]                       clear_reject_count_o,
  output wire [255:0]                      archive_digest_o
);
  localparam integer PRE_EVENT_DEPTH = EVENT_DEPTH - POST_EVENT_COUNT;
  localparam integer EVENT_BITS = 32 * EVENT_WORDS;
  localparam integer EVENT_PTR_W = $clog2(EVENT_DEPTH);
  localparam integer PRE_PTR_W = $clog2(PRE_EVENT_DEPTH);
  localparam integer SNAP_INDEX_W = $clog2(SNAPSHOT_WORDS);
  localparam integer SAMPLE_COUNTER_W = $clog2(SAMPLE_INTERVAL_CYCLES);
  localparam integer CLEAR_TIMEOUT_W = $clog2(CLK_HZ + 1);
  localparam [31:0] SNAPSHOT_MAGIC = 32'h4646_5331; // "FFS1"
  localparam [31:0] SNAPSHOT_SCHEMA = 32'h0001_0001;
  localparam [31:0] EVENT_MAGIC = 32'h4646_4531;    // "FFE1"
  localparam [31:0] ARCHIVE_MAGIC = 32'h4152_4348;  // "ARCH"
  localparam [31:0] CLEAR_KEY_ARM = 32'h4652_4F5A;  // "FROZ"
  localparam [31:0] CLEAR_KEY_COMMIT = 32'h434C_5241; // "CLRA"

  localparam [7:0] EVENT_PERIODIC = 8'h01;
  localparam [7:0] EVENT_CONTROL = 8'h02;
  localparam [7:0] EVENT_OBJECT = 8'h03;
  localparam [7:0] EVENT_RETRY = 8'h04;
  localparam [7:0] EVENT_LANE = 8'h05;
  localparam [7:0] EVENT_TX_BURST = 8'h06;
  localparam [7:0] EVENT_CHECKPOINT = 8'h07;
  localparam [7:0] EVENT_FIRST_FAULT = 8'hF0;
  localparam [7:0] EVENT_POST_FAULT = 8'hF1;

  (* ram_style = "block" *) reg [EVENT_BITS-1:0] event_mem [0:EVENT_DEPTH-1];
  reg [31:0] snapshot_q [0:SNAPSHOT_WORDS-1];
  reg [EVENT_BITS-1:0] event_read_record_q;
  reg [63:0] timestamp_q;
  reg frozen_q;
  reg post_complete_q;
  reg [31:0] fault_sequence_q;
  reg [63:0] fault_timestamp_q;
  reg [31:0] frozen_fault_cause_q;
  reg [PRE_PTR_W-1:0] pre_write_ptr_q;
  reg [PRE_PTR_W-1:0] frozen_pre_start_q;
  reg [PRE_PTR_W:0] pre_count_q;
  reg [$clog2(POST_EVENT_COUNT+1)-1:0] post_count_q;
  reg [SNAP_INDEX_W:0] snapshot_expected_q;
  reg [EVENT_PTR_W:0] event_expected_entry_q;
  reg [$clog2(EVENT_WORDS):0] event_expected_word_q;
  reg snapshot_read_complete_q;
  reg event_read_complete_q;
  reg [255:0] archive_digest_q;
  reg [7:0] archive_digest_written_q;
  reg archive_committed_q;
  reg clear_armed_q;
  reg [CLEAR_TIMEOUT_W-1:0] clear_arm_timeout_q;
  reg [31:0] clear_count_q;
  reg [31:0] clear_reject_count_q;
  reg [SAMPLE_COUNTER_W-1:0] sample_counter_q;
  reg [$clog2(MODULE_COUNT)-1:0] sample_module_q;
  reg [7:0] tx_idle_count_q;
  reg tx_burst_active_q;
  reg tx_burst_active_d_q;
  reg endpoint_armed_d_q;
  reg tx_kill_d_q;
  reg receiver_enable_d_q;
  reg effective_shutdown_d_q;
  reg system_reset_n_d_q;
  reg [MODULE_COUNT-1:0] physical_sd_d_q;
  reg [MODULE_COUNT-1:0] physical_mode_d_q;
  reg [MODULE_COUNT-1:0] safety_fault_d_q;
  reg [LANE_COUNT-1:0] configured_lane_mask_d_q;
  reg [LANE_COUNT-1:0] unavailable_lane_mask_d_q;
  reg [LANE_COUNT-1:0] raw_lane_mask_d_q;
  reg raw_busy_d_q;
  reg raw_direction_d_q;
  reg object_active_d_q;
  reg object_done_d_q;
  reg object_fail_d_q;
  reg [31:0] object_id_d_q;
  reg [31:0] tx_retry_count_d_q;
  reg [31:0] tx_retry_exhausted_count_d_q;
  reg [15:0] tx_next_sequence_d_q;
  reg [15:0] tx_ack_base_d_q;
  reg event_valid;
  reg [7:0] event_code;
  reg [$clog2(MODULE_COUNT)-1:0] event_module;
  reg [31:0] event_tag;
  reg [EVENT_PTR_W-1:0] event_read_physical_index;
  integer init_index;
  integer module_index;

  function automatic [31:0] pack_status;
    reg [31:0] value;
    begin
      value = 32'd0;
      value[MODULE_COUNT-1:0] = physical_txd_i;
      value[8 +: MODULE_COUNT] = physical_sd_i;
      value[16 +: MODULE_COUNT] = safety_fault_i;
      value[24] = endpoint_armed_i;
      value[25] = tx_kill_i;
      value[26] = effective_shutdown_i;
      value[27] = receiver_enable_i;
      value[28] = system_reset_n_i;
      value[29] = object_active_i;
      value[30] = object_fail_i;
      value[31] = raw_busy_i;
      pack_status = value;
    end
  endfunction

  function automatic [31:0] pack_module_flags(input integer index);
    reg [31:0] value;
    begin
      value = 32'd0;
      value[0] = physical_txd_i[index];
      value[1] = physical_sd_i[index];
      value[2] = physical_mode_i[index];
      value[3] = safety_fault_i[index];
      value[4] = endpoint_armed_i;
      value[5] = tx_kill_i;
      value[6] = effective_shutdown_i;
      value[7] = !system_reset_n_i;
      value[8] = phy_ready_i[index];
      value[9] = startup_done_i[index];
      value[15:12] = index;
      value[23:16] = configured_lane_mask_i;
      value[31:24] = unavailable_lane_mask_i;
      pack_module_flags = value;
    end
  endfunction

  function automatic [EVENT_BITS-1:0] make_event(
    input [7:0] code,
    input integer selected_module,
    input [31:0] tag
  );
    reg [EVENT_BITS-1:0] value;
    begin
      value = {EVENT_BITS{1'b0}};
      value[0 +: 32] = {EVENT_MAGIC[31:16], code, selected_module[7:0]};
      value[32 +: 32] = timestamp_q[31:0];
      value[64 +: 32] = timestamp_q[63:32];
      value[96 +: 32] = pack_status();
      value[128 +: 32] = object_id_i;
      value[160 +: 32] = {tx_ack_base_i, tx_next_sequence_i};
      value[192 +: 32] = tx_retry_count_i;
      // Word 7 is event-specific evidence.  Periodic module samples provide
      // that module's physical-TX count; control/object/retry/checkpoint/fault
      // records preserve their explicit tag instead of silently discarding it.
      value[224 +: 32] = tag;
      make_event = value;
    end
  endfunction

  initial begin
    if (MODULE_COUNT < 1 || MODULE_COUNT > 8)
      $fatal(1, "P10 forensic MODULE_COUNT must be in 1..8");
    if (LANE_COUNT < 1 || LANE_COUNT > 8)
      $fatal(1, "P10 forensic LANE_COUNT must be in 1..8");
    if (SNAPSHOT_WORDS != 24 + 10*MODULE_COUNT)
      $fatal(1, "P10 forensic snapshot schema size mismatch");
    if (EVENT_WORDS != 8)
      $fatal(1, "P10 forensic event schema freezes eight words");
    if (EVENT_DEPTH < 32 || POST_EVENT_COUNT < 2 ||
        POST_EVENT_COUNT >= EVENT_DEPTH)
      $fatal(1, "P10 forensic event depth/post-tail invalid");
    if (SAMPLE_INTERVAL_CYCLES < 16 ||
        (SAMPLE_INTERVAL_CYCLES & (SAMPLE_INTERVAL_CYCLES-1)) != 0)
      $fatal(1, "P10 forensic sample interval must be a power of two >=16");
    timestamp_q = 64'd0;
    frozen_q = 1'b0;
    post_complete_q = 1'b0;
    fault_sequence_q = 32'd0;
    fault_timestamp_q = 64'd0;
    frozen_fault_cause_q = 32'd0;
    pre_write_ptr_q = {PRE_PTR_W{1'b0}};
    frozen_pre_start_q = {PRE_PTR_W{1'b0}};
    pre_count_q = {(PRE_PTR_W+1){1'b0}};
    post_count_q = 0;
    snapshot_expected_q = 0;
    event_expected_entry_q = 0;
    event_expected_word_q = 0;
    snapshot_read_complete_q = 1'b0;
    event_read_complete_q = 1'b0;
    archive_digest_q = 256'd0;
    archive_digest_written_q = 8'd0;
    archive_committed_q = 1'b0;
    clear_armed_q = 1'b0;
    clear_arm_timeout_q = 0;
    clear_count_q = 0;
    clear_reject_count_q = 0;
    sample_counter_q = 0;
    sample_module_q = 0;
    tx_idle_count_q = 0;
    tx_burst_active_q = 0;
    tx_burst_active_d_q = 0;
    endpoint_armed_d_q = 0;
    tx_kill_d_q = 1;
    receiver_enable_d_q = 0;
    effective_shutdown_d_q = 1;
    system_reset_n_d_q = 0;
    physical_sd_d_q = {MODULE_COUNT{1'b1}};
    physical_mode_d_q = {MODULE_COUNT{1'b1}};
    safety_fault_d_q = 0;
    configured_lane_mask_d_q = 0;
    unavailable_lane_mask_d_q = 0;
    raw_lane_mask_d_q = 0;
    raw_busy_d_q = 0;
    raw_direction_d_q = 0;
    object_active_d_q = 0;
    object_done_d_q = 0;
    object_fail_d_q = 0;
    object_id_d_q = 0;
    tx_retry_count_d_q = 0;
    tx_retry_exhausted_count_d_q = 0;
    tx_next_sequence_d_q = 0;
    tx_ack_base_d_q = 0;
    event_read_record_q = 0;
    for (init_index = 0; init_index < SNAPSHOT_WORDS; init_index = init_index + 1)
      snapshot_q[init_index] = 32'd0;
    for (init_index = 0; init_index < EVENT_DEPTH; init_index = init_index + 1)
      event_mem[init_index] = {EVENT_BITS{1'b0}};
  end

  assign first_fault_hold_o = frozen_q;
  assign frozen_o = frozen_q;
  assign post_trace_complete_o = post_complete_q;
  assign snapshot_read_complete_o = snapshot_read_complete_q;
  assign event_read_complete_o = event_read_complete_q;
  assign archive_committed_o = archive_committed_q;
  assign clear_armed_o = clear_armed_q;
  assign fault_sequence_o = fault_sequence_q;
  assign fault_timestamp_o = fault_timestamp_q;
  assign frozen_fault_cause_o = frozen_fault_cause_q;
  assign pre_event_count_o = pre_count_q;
  assign post_event_count_o = post_count_q;
  assign total_event_count_o = pre_count_q + post_count_q;
  assign clear_count_o = clear_count_q;
  assign clear_reject_count_o = clear_reject_count_q;
  assign archive_digest_o = archive_digest_q;
  assign snapshot_read_data_o = snapshot_q[snapshot_read_index_i];
  assign event_read_data_o =
      event_read_record_q[32*event_read_word_i +: 32];

  always @* begin
    if (event_read_index_i < pre_count_q) begin
      if (pre_count_q < PRE_EVENT_DEPTH)
        event_read_physical_index = event_read_index_i;
      else if (frozen_pre_start_q + event_read_index_i >= PRE_EVENT_DEPTH)
        event_read_physical_index =
            frozen_pre_start_q + event_read_index_i - PRE_EVENT_DEPTH;
      else
        event_read_physical_index = frozen_pre_start_q + event_read_index_i;
    end else begin
      event_read_physical_index = PRE_EVENT_DEPTH +
          (event_read_index_i - pre_count_q);
    end
  end

  always @* begin
    event_valid = 1'b0;
    event_code = EVENT_PERIODIC;
    event_module = sample_module_q;
    event_tag = physical_tx_counts_flat_i[32*sample_module_q +: 32];
    if (capture_fault_i) begin
      event_valid = 1'b1;
      event_code = EVENT_FIRST_FAULT;
      event_module = 0;
      event_tag = fault_cause_i;
    end else if (checkpoint_event_i) begin
      event_valid = 1'b1;
      event_code = EVENT_CHECKPOINT;
      event_module = 0;
      event_tag = checkpoint_tag_i;
    end else if (endpoint_armed_i != endpoint_armed_d_q ||
                 tx_kill_i != tx_kill_d_q ||
                 receiver_enable_i != receiver_enable_d_q ||
                 effective_shutdown_i != effective_shutdown_d_q ||
                 system_reset_n_i != system_reset_n_d_q ||
                 physical_sd_i != physical_sd_d_q ||
                 physical_mode_i != physical_mode_d_q ||
                 safety_fault_i != safety_fault_d_q) begin
      event_valid = 1'b1;
      event_code = EVENT_CONTROL;
      event_module = 0;
      event_tag = fault_cause_i;
    end else if (object_active_i != object_active_d_q ||
                 object_done_i != object_done_d_q ||
                 object_fail_i != object_fail_d_q ||
                 object_id_i != object_id_d_q) begin
      event_valid = 1'b1;
      event_code = EVENT_OBJECT;
      event_module = 0;
      event_tag = object_error_i;
    end else if (tx_retry_count_i != tx_retry_count_d_q ||
                 tx_retry_exhausted_count_i != tx_retry_exhausted_count_d_q ||
                 tx_next_sequence_i != tx_next_sequence_d_q ||
                 tx_ack_base_i != tx_ack_base_d_q) begin
      event_valid = 1'b1;
      event_code = EVENT_RETRY;
      event_module = 0;
      event_tag = tx_retry_exhausted_count_i;
    end else if (configured_lane_mask_i != configured_lane_mask_d_q ||
                 unavailable_lane_mask_i != unavailable_lane_mask_d_q ||
                 raw_lane_mask_i != raw_lane_mask_d_q ||
                 raw_busy_i != raw_busy_d_q ||
                 raw_direction_i != raw_direction_d_q) begin
      event_valid = 1'b1;
      event_code = EVENT_LANE;
      event_module = 0;
      event_tag = {16'd0, raw_direction_i, raw_busy_i, 2'd0,
                   unavailable_lane_mask_i, configured_lane_mask_i};
    end else if (tx_burst_active_q != tx_burst_active_d_q) begin
      event_valid = 1'b1;
      event_code = EVENT_TX_BURST;
      event_module = sample_module_q;
      event_tag = {31'd0, tx_burst_active_q};
    end else if (sample_counter_q == SAMPLE_INTERVAL_CYCLES-1 &&
                 (endpoint_armed_i || object_active_i || raw_busy_i ||
                  tx_burst_active_q)) begin
      event_valid = 1'b1;
      event_code = EVENT_PERIODIC;
      event_module = sample_module_q;
      event_tag = physical_tx_counts_flat_i[32*sample_module_q +: 32];
    end
  end

  // Synchronous BRAM read port.  XSDB writes the logical entry index, waits
  // for the AXI transaction to complete, then reads one or more selected
  // words; continuous prefetch makes the data stable before that read.
  always @(posedge clk) begin
    event_read_record_q <= event_mem[event_read_physical_index];
  end

  always @(posedge clk) begin
    timestamp_q <= timestamp_q + 1'b1;

    endpoint_armed_d_q <= endpoint_armed_i;
    tx_kill_d_q <= tx_kill_i;
    receiver_enable_d_q <= receiver_enable_i;
    effective_shutdown_d_q <= effective_shutdown_i;
    system_reset_n_d_q <= system_reset_n_i;
    physical_sd_d_q <= physical_sd_i;
    physical_mode_d_q <= physical_mode_i;
    safety_fault_d_q <= safety_fault_i;
    configured_lane_mask_d_q <= configured_lane_mask_i;
    unavailable_lane_mask_d_q <= unavailable_lane_mask_i;
    raw_lane_mask_d_q <= raw_lane_mask_i;
    raw_busy_d_q <= raw_busy_i;
    raw_direction_d_q <= raw_direction_i;
    object_active_d_q <= object_active_i;
    object_done_d_q <= object_done_i;
    object_fail_d_q <= object_fail_i;
    object_id_d_q <= object_id_i;
    tx_retry_count_d_q <= tx_retry_count_i;
    tx_retry_exhausted_count_d_q <= tx_retry_exhausted_count_i;
    tx_next_sequence_d_q <= tx_next_sequence_i;
    tx_ack_base_d_q <= tx_ack_base_i;
    tx_burst_active_d_q <= tx_burst_active_q;

    if (|physical_txd_i) begin
      tx_idle_count_q <= 0;
      tx_burst_active_q <= 1'b1;
    end else if (tx_burst_active_q) begin
      if (&tx_idle_count_q) begin
        tx_burst_active_q <= 1'b0;
        tx_idle_count_q <= 0;
      end else begin
        tx_idle_count_q <= tx_idle_count_q + 1'b1;
      end
    end else begin
      tx_idle_count_q <= 0;
    end

    if (sample_counter_q == SAMPLE_INTERVAL_CYCLES-1) begin
      sample_counter_q <= 0;
      if (sample_module_q == MODULE_COUNT-1)
        sample_module_q <= 0;
      else
        sample_module_q <= sample_module_q + 1'b1;
    end else begin
      sample_counter_q <= sample_counter_q + 1'b1;
    end

    if (clear_armed_q) begin
      if (!system_reset_n_i || clear_arm_timeout_q == 0) begin
        clear_armed_q <= 1'b0;
      end else begin
        clear_arm_timeout_q <= clear_arm_timeout_q - 1'b1;
      end
    end

    if (!frozen_q) begin
      if (event_valid) begin
        event_mem[pre_write_ptr_q] <=
            make_event(event_code, event_module, event_tag);
        if (pre_count_q < PRE_EVENT_DEPTH)
          pre_count_q <= pre_count_q + 1'b1;
        if (pre_write_ptr_q == PRE_EVENT_DEPTH-1)
          pre_write_ptr_q <= 0;
        else
          pre_write_ptr_q <= pre_write_ptr_q + 1'b1;
      end

      if (capture_fault_i) begin
        frozen_q <= 1'b1;
        post_complete_q <= 1'b0;
        post_count_q <= 0;
        fault_sequence_q <= fault_sequence_q + 1'b1;
        fault_timestamp_q <= timestamp_q;
        frozen_fault_cause_q <= fault_cause_i;
        if (pre_count_q >= PRE_EVENT_DEPTH)
          frozen_pre_start_q <=
              (pre_write_ptr_q == PRE_EVENT_DEPTH-1) ? 0 : pre_write_ptr_q + 1'b1;
        else
          frozen_pre_start_q <= 0;
        snapshot_expected_q <= 0;
        event_expected_entry_q <= 0;
        event_expected_word_q <= 0;
        snapshot_read_complete_q <= 1'b0;
        event_read_complete_q <= 1'b0;
        archive_digest_written_q <= 0;
        archive_committed_q <= 1'b0;
        clear_armed_q <= 1'b0;

        snapshot_q[0] <= SNAPSHOT_MAGIC;
        snapshot_q[1] <= SNAPSHOT_SCHEMA;
        snapshot_q[2] <= SNAPSHOT_WORDS;
        snapshot_q[3] <= {EVENT_DEPTH[15:0], EVENT_WORDS[7:0],
                          MODULE_COUNT[3:0], LANE_COUNT[3:0]};
        snapshot_q[4] <= timestamp_q[31:0];
        snapshot_q[5] <= timestamp_q[63:32];
        snapshot_q[6] <= fault_cause_i;
        snapshot_q[7] <= pack_status();
        snapshot_q[8] <= object_id_i;
        snapshot_q[9] <= object_error_i;
        snapshot_q[10] <= {16'd0, raw_direction_i, raw_busy_i, 2'd0,
                           unavailable_lane_mask_i, configured_lane_mask_i};
        snapshot_q[11] <= {tx_ack_base_i, tx_next_sequence_i};
        snapshot_q[12] <= {4'd0, tx_outstanding_high_watermark_i,
                           tx_outstanding_i, rx_base_sequence_i};
        snapshot_q[13] <= {16'd0, rx_base_sequence_i};
        snapshot_q[14] <= rx_sack_bitmap_i;
        snapshot_q[15] <= {24'd0, raw_direction_i, raw_busy_i, 2'd0,
                           raw_lane_mask_i};
        snapshot_q[16] <= tx_attempt_count_i;
        snapshot_q[17] <= tx_retry_count_i;
        snapshot_q[18] <= tx_retry_exhausted_count_i;
        snapshot_q[19] <= tx_timeout_count_i;
        snapshot_q[20] <= tx_migration_count_i;
        snapshot_q[21] <= input_byte_count_i;
        snapshot_q[22] <= output_byte_count_i;
        snapshot_q[23] <= {16'd0, startup_done_i, phy_ready_i,
                           safety_fault_i, physical_txd_i};
        for (module_index = 0; module_index < MODULE_COUNT;
             module_index = module_index + 1) begin
          snapshot_q[24+10*module_index+0] <=
              physical_tx_counts_flat_i[32*module_index +: 32];
          snapshot_q[24+10*module_index+1] <=
              tx_high_current_flat_i[32*module_index +: 32];
          snapshot_q[24+10*module_index+2] <=
              tx_high_max_flat_i[32*module_index +: 32];
          snapshot_q[24+10*module_index+3] <=
              duty_high_current_flat_i[32*module_index +: 32];
          snapshot_q[24+10*module_index+4] <=
              duty_high_max_flat_i[32*module_index +: 32];
          snapshot_q[24+10*module_index+5] <=
              duty_headroom_flat_i[32*module_index +: 32];
          snapshot_q[24+10*module_index+6] <=
              duty_hard_fault_count_flat_i[32*module_index +: 32];
          snapshot_q[24+10*module_index+7] <= pack_module_flags(module_index);
          snapshot_q[24+10*module_index+8] <=
              raw_rx_counts_flat_i[32*module_index +: 32];
          snapshot_q[24+10*module_index+9] <=
              duty_target_throttle_count_flat_i[32*module_index +: 32];
        end
      end
    end else if (!post_complete_q) begin
      event_mem[PRE_EVENT_DEPTH + post_count_q] <=
          make_event(EVENT_POST_FAULT, post_count_q, frozen_fault_cause_q);
      if (post_count_q == POST_EVENT_COUNT-1) begin
        post_count_q <= POST_EVENT_COUNT;
        post_complete_q <= 1'b1;
      end else begin
        post_count_q <= post_count_q + 1'b1;
      end
    end

    if (frozen_q && snapshot_read_strobe_i &&
        !snapshot_read_complete_q) begin
      if (snapshot_read_index_i == snapshot_expected_q) begin
        if (snapshot_expected_q == SNAPSHOT_WORDS-1)
          snapshot_read_complete_q <= 1'b1;
        else
          snapshot_expected_q <= snapshot_expected_q + 1'b1;
      end else begin
        snapshot_expected_q <= 0;
      end
    end

    if (frozen_q && post_complete_q && event_read_strobe_i &&
        !event_read_complete_q) begin
      if (event_read_index_i == event_expected_entry_q &&
          event_read_word_i == event_expected_word_q) begin
        if (event_expected_word_q == EVENT_WORDS-1) begin
          event_expected_word_q <= 0;
          if (event_expected_entry_q + 1'b1 == pre_count_q + post_count_q)
            event_read_complete_q <= 1'b1;
          else
            event_expected_entry_q <= event_expected_entry_q + 1'b1;
        end else begin
          event_expected_word_q <= event_expected_word_q + 1'b1;
        end
      end else begin
        event_expected_entry_q <= 0;
        event_expected_word_q <= 0;
      end
    end

    if (frozen_q && archive_digest_write_i) begin
      archive_digest_q[32*archive_digest_index_i +: 32] <=
          archive_digest_data_i;
      archive_digest_written_q[archive_digest_index_i] <= 1'b1;
      archive_committed_q <= 1'b0;
      clear_armed_q <= 1'b0;
    end

    if (archive_commit_i) begin
      if (frozen_q && post_complete_q && snapshot_read_complete_q &&
          event_read_complete_q && &archive_digest_written_q &&
          archive_digest_q != 0)
        archive_committed_q <= 1'b1;
      else
        clear_reject_count_q <= clear_reject_count_q + 1'b1;
    end

    if (clear_key_write_i) begin
      if (clear_key_i == CLEAR_KEY_ARM && frozen_q && archive_committed_q &&
          effective_shutdown_i && tx_kill_i && !(|physical_txd_i) &&
          (&physical_sd_i) && !capture_fault_i) begin
        clear_armed_q <= 1'b1;
        // One second is bounded yet long enough for two authenticated XSDB
        // AXI writes; a 64-cycle window is not operable over JTAG.
        clear_arm_timeout_q <= CLK_HZ;
      end else if (clear_key_i == CLEAR_KEY_COMMIT && clear_armed_q &&
                   frozen_q && archive_committed_q &&
                   effective_shutdown_i && tx_kill_i &&
                   !(|physical_txd_i) && (&physical_sd_i) &&
                   !capture_fault_i) begin
        frozen_q <= 1'b0;
        post_complete_q <= 1'b0;
        pre_write_ptr_q <= 0;
        frozen_pre_start_q <= 0;
        pre_count_q <= 0;
        post_count_q <= 0;
        snapshot_expected_q <= 0;
        event_expected_entry_q <= 0;
        event_expected_word_q <= 0;
        snapshot_read_complete_q <= 1'b0;
        event_read_complete_q <= 1'b0;
        archive_committed_q <= 1'b0;
        archive_digest_written_q <= 0;
        clear_armed_q <= 1'b0;
        clear_count_q <= clear_count_q + 1'b1;
        for (module_index = 0; module_index < SNAPSHOT_WORDS;
             module_index = module_index + 1)
          snapshot_q[module_index] <= 0;
      end else begin
        clear_armed_q <= 1'b0;
        clear_reject_count_q <= clear_reject_count_q + 1'b1;
      end
    end
  end
endmodule

`default_nettype wire
