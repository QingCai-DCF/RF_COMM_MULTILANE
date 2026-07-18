`timescale 1ns/1ps
module tb_ir_p8d_data_plane_regs;
  `include "generated/ir_register_map_defs.svh"
  logic clk=0;always #5 clk=~clk;
  logic rst_n,wr_en,rd_en;
  logic [11:0] wr_addr,rd_addr;
  logic [31:0] wr_data,rd_data;
  logic rd_valid;
  logic enable_request_o,disable_request_o,reset_request_o,abort_request_o;
  logic snapshot_request_o,clear_sticky_request_o,configuration_error_sticky_o;
  logic [31:0] protocol_mode_o,session_epoch_o,retry_config_o;
  logic [15:0] path_epoch_o,tx_window_size_o,rx_window_size_o;
  logic [6:0] sack_window_bits_o;
  logic [7:0] scheduler_active_mask_o;
  logic [31:0] scheduler_starvation_bound_o;
  logic [63:0] lane_weights_o;
  logic [15:0] tx_ring_depth_o,rx_ring_depth_o;
  logic [31:0] abort_stream_id_o,abort_object_id_o;
  logic enabled_i,tx_window_full_i,rx_window_full_i,tx_ring_full_i,rx_ring_full_i;
  logic sticky_error_i,abort_active_i;
  logic [15:0] tx_next_sequence_i,tx_ack_base_i,rx_base_sequence_i;
  logic [31:0] outstanding_count_i,outstanding_high_watermark_i;
  logic [63:0] sack_bitmap_i;
  logic [31:0] ack_aggregation_count_i=0,ack_timer_expiry_count_i=0;
  logic [31:0] ack_frames_sent_i=0,ack_frames_received_i=0;
  logic [31:0] duplicate_ack_count_i=0,stale_ack_count_i=0,out_of_window_ack_count_i=0;
  logic [31:0] tx_retry_count_i=0,tx_retry_exhausted_count_i=0,timeout_count_i=0;
  logic [31:0] migration_count_i=0,lane_fault_migration_count_i=0;
  logic [31:0] duty_defer_count_i=0,permit_defer_count_i=0,mapping_defer_count_i=0;
  logic [31:0] rx_out_of_order_count_i=0,rx_duplicate_count_i=0,rx_old_count_i=0;
  logic [31:0] rx_future_count_i=0,rx_stale_session_count_i=0,rx_stale_path_count_i=0;
  logic [31:0] rx_gap_count_i=0,rx_gap_timeout_count_i=0;
  logic [3:0] scheduler_defer_reason_i=0;
  logic [31:0] scheduler_starvation_max_i=0;
  logic [31:0] tx_ring_producer_i=0,tx_ring_consumer_i=0,tx_ring_high_watermark_i=0;
  logic [31:0] tx_ring_full_count_i=0,rx_ring_producer_i=0,rx_ring_consumer_i=0;
  logic [31:0] rx_ring_high_watermark_i=0,rx_ring_full_count_i=0;
  logic [15:0] tx_ring_generation_i=0,rx_ring_generation_i=0;
  logic [31:0] descriptor_complete_count_i=0,descriptor_error_count_i=0;
  logic [31:0] descriptor_abort_count_i=0,descriptor_stale_count_i=0;
  logic [31:0] axis_tx_stall_cycles_i=0,axis_rx_stall_cycles_i=0;
  logic [31:0] axis_protocol_error_count_i=0,payload_store_used_i=0;
  logic [31:0] payload_store_high_watermark_i=0;
  logic [255:0] lane_scheduled_frames_flat_i,lane_scheduled_bytes_flat_i;
  logic [255:0] lane_retries_flat_i,lane_migrations_flat_i,lane_defer_flat_i;

  ir_p8d_data_plane_regs dut(.*);
  task automatic check_expect(input logic condition,input string message);
    if(!condition)$fatal(1,"P8D_REG_EXPECT_FAIL: %s",message);
  endtask
  task automatic write_reg(input logic [11:0] address,input logic [31:0] value);
    begin @(negedge clk);wr_addr=address;wr_data=value;wr_en=1;
      @(posedge clk);#1;wr_en=0;end
  endtask
  task automatic read_reg(input logic [11:0] address,output logic [31:0] value);
    begin rd_addr=address;rd_en=1;#1;value=rd_data;check_expect(rd_valid,"read valid");rd_en=0;end
  endtask
  logic [31:0] value;
  initial begin
    rst_n=0;wr_en=0;rd_en=0;wr_addr=0;wr_data=0;rd_addr=0;
    enabled_i=1;tx_window_full_i=0;rx_window_full_i=0;tx_ring_full_i=0;rx_ring_full_i=0;
    sticky_error_i=0;abort_active_i=0;tx_next_sequence_i=16'hfffe;
    tx_ack_base_i=16'hfff0;rx_base_sequence_i=16'h0002;outstanding_count_i=32'd31;
    outstanding_high_watermark_i=32'd32;sack_bitmap_i=64'h80000000_00000005;
    lane_scheduled_frames_flat_i=0;lane_scheduled_bytes_flat_i=0;
    lane_retries_flat_i=0;lane_migrations_flat_i=0;lane_defer_flat_i=0;
    lane_scheduled_frames_flat_i[4*32+:32]=32'd444;
    repeat(3)@(posedge clk);rst_n=1;@(posedge clk);#1;

    read_reg(`IR_REG_P8D_TX_WINDOW_SIZE,value);check_expect(value==32,"default window is 32");
    write_reg(`IR_REG_P8D_TX_WINDOW_SIZE,64);read_reg(`IR_REG_P8D_TX_WINDOW_SIZE,value);
    check_expect(value==64,"valid profile window is writable");
    write_reg(`IR_REG_P8D_TX_WINDOW_SIZE,16);read_reg(`IR_REG_P8D_TX_WINDOW_SIZE,value);
    check_expect(value==64&&configuration_error_sticky_o,"invalid window fails closed");
    write_reg(`IR_REG_P8D_CONTROL,`IR_P8D_CONTROL_CLEAR_STICKY_REQUEST_MASK);
    check_expect(clear_sticky_request_o&&!configuration_error_sticky_o,"sticky clear is a request pulse");
    @(posedge clk);#1;check_expect(!clear_sticky_request_o,"control pulse is one cycle");

    write_reg(`IR_REG_P8D_CONTROL,`IR_P8D_CONTROL_ENABLE_REQUEST_MASK|
      `IR_P8D_CONTROL_ABORT_REQUEST_MASK|`IR_P8D_CONTROL_SNAPSHOT_REQUEST_MASK);
    check_expect(enable_request_o&&abort_request_o&&snapshot_request_o,"control requests pulse together");
    tx_next_sequence_i=0;sack_bitmap_i=0;lane_scheduled_frames_flat_i=0;
    read_reg(`IR_REG_P8D_TX_NEXT_SEQUENCE,value);check_expect(value==16'hfffe,"snapshot is atomic");
    read_reg(`IR_REG_P8D_LAST_SACK_BITMAP_HIGH,value);
    check_expect(value==32'h80000000,"64-bit SACK snapshot is complete");
    read_reg(`IR_REG_P8D_LANE4_SCHEDULED_FRAMES,value);
    check_expect(value==444,"indexed per-lane telemetry is snapshot-consistent");

    write_reg(`IR_REG_P8D_TX_NEXT_SEQUENCE,32'hdeadbeef);
    read_reg(`IR_REG_P8D_TX_NEXT_SEQUENCE,value);
    check_expect(value==16'hfffe,"writes to read-only sequence status are ignored");
    read_reg(`IR_REG_P8D_REGISTER_MAP_VERSION,value);
    check_expect(value==`IR_REGISTER_MAP_VERSION,"register-map version exported");
    read_reg(`IR_REG_P8D_REGISTER_MAP_HASH_LOW,value);
    check_expect(value==`IR_REGISTER_MAP_HASH_LOW,"register-map hash exported");
    $display("P8D_REGISTER_RO_SNAPSHOT_PASS=1");
    $display("P8D_REGISTER_CONFIG_FAIL_CLOSED_PASS=1");
    $display("TB_IR_P8D_DATA_PLANE_REGS_PASS=1");
    $finish;
  end
endmodule
