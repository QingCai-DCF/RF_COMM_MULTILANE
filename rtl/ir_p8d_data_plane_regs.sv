`timescale 1ns/1ps
`default_nettype none
`include "generated/ir_register_map_defs.svh"

// Additive P8D register front-end.  Safety and GLOBAL_PERMIT remain status-only
// at the P8C boundary; this block cannot create, override, or bypass permit high.
module ir_p8d_data_plane_regs #(
  parameter integer MAX_WINDOW_SIZE=64,
  parameter integer MAX_RING_DEPTH=64
) (
  input  wire         clk,input wire rst_n,
  input  wire         wr_en,input wire [11:0] wr_addr,input wire [31:0] wr_data,
  input  wire         rd_en,input wire [11:0] rd_addr,
  output reg [31:0]   rd_data,output reg rd_valid,
  output reg          enable_request_o,output reg disable_request_o,
  output reg          reset_request_o,output reg abort_request_o,
  output reg          snapshot_request_o,output reg clear_sticky_request_o,
  output reg [31:0]   protocol_mode_o,output reg [31:0] session_epoch_o,
  output reg [15:0]   path_epoch_o,output reg [15:0] tx_window_size_o,
  output reg [15:0]   rx_window_size_o,output reg [31:0] retry_config_o,
  output reg [6:0]    sack_window_bits_o,output reg [7:0] scheduler_active_mask_o,
  output reg [31:0]   scheduler_starvation_bound_o,output reg [63:0] lane_weights_o,
  output reg [15:0]   tx_ring_depth_o,output reg [15:0] rx_ring_depth_o,
  output reg [31:0]   abort_stream_id_o,output reg [31:0] abort_object_id_o,
  output reg          configuration_error_sticky_o,
  input  wire         enabled_i,input wire tx_window_full_i,input wire rx_window_full_i,
  input  wire         tx_ring_full_i,input wire rx_ring_full_i,input wire sticky_error_i,
  input  wire         abort_active_i,
  input  wire [15:0]  tx_next_sequence_i,input wire [15:0] tx_ack_base_i,
  input  wire [15:0]  rx_base_sequence_i,input wire [31:0] outstanding_count_i,
  input  wire [31:0]  outstanding_high_watermark_i,input wire [63:0] sack_bitmap_i,
  input  wire [31:0]  ack_aggregation_count_i,input wire [31:0] ack_timer_expiry_count_i,
  input  wire [31:0]  ack_frames_sent_i,input wire [31:0] ack_frames_received_i,
  input  wire [31:0]  duplicate_ack_count_i,input wire [31:0] stale_ack_count_i,
  input  wire [31:0]  out_of_window_ack_count_i,input wire [31:0] tx_retry_count_i,
  input  wire [31:0]  tx_retry_exhausted_count_i,input wire [31:0] timeout_count_i,
  input  wire [31:0]  migration_count_i,input wire [31:0] lane_fault_migration_count_i,
  input  wire [31:0]  duty_defer_count_i,input wire [31:0] permit_defer_count_i,
  input  wire [31:0]  mapping_defer_count_i,input wire [31:0] rx_out_of_order_count_i,
  input  wire [31:0]  rx_duplicate_count_i,input wire [31:0] rx_old_count_i,
  input  wire [31:0]  rx_future_count_i,input wire [31:0] rx_stale_session_count_i,
  input  wire [31:0]  rx_stale_path_count_i,input wire [31:0] rx_gap_count_i,
  input  wire [31:0]  rx_gap_timeout_count_i,input wire [3:0] scheduler_defer_reason_i,
  input  wire [31:0]  scheduler_starvation_max_i,
  input  wire [31:0]  tx_ring_producer_i,input wire [31:0] tx_ring_consumer_i,
  input  wire [15:0]  tx_ring_generation_i,input wire [31:0] tx_ring_high_watermark_i,
  input  wire [31:0]  tx_ring_full_count_i,input wire [31:0] rx_ring_producer_i,
  input  wire [31:0]  rx_ring_consumer_i,input wire [15:0] rx_ring_generation_i,
  input  wire [31:0]  rx_ring_high_watermark_i,input wire [31:0] rx_ring_full_count_i,
  input  wire [31:0]  descriptor_complete_count_i,input wire [31:0] descriptor_error_count_i,
  input  wire [31:0]  descriptor_abort_count_i,input wire [31:0] descriptor_stale_count_i,
  input  wire [31:0]  axis_tx_stall_cycles_i,input wire [31:0] axis_rx_stall_cycles_i,
  input  wire [31:0]  axis_protocol_error_count_i,input wire [31:0] payload_store_used_i,
  input  wire [31:0]  payload_store_high_watermark_i,
  input  wire [255:0] lane_scheduled_frames_flat_i,
  input  wire [255:0] lane_scheduled_bytes_flat_i,
  input  wire [255:0] lane_retries_flat_i,
  input  wire [255:0] lane_migrations_flat_i,
  input  wire [255:0] lane_defer_flat_i
);
  reg snapshot_valid_q;
  reg [15:0] snap_tx_next_q,snap_tx_ack_base_q,snap_rx_base_q;
  reg [31:0] snap_outstanding_q,snap_outstanding_hwm_q;
  reg [63:0] snap_sack_q;
  reg [31:0] snap_ack_aggregation_q,snap_ack_timer_q,snap_ack_sent_q,snap_ack_received_q;
  reg [31:0] snap_duplicate_ack_q,snap_stale_ack_q,snap_bad_ack_q;
  reg [31:0] snap_retry_q,snap_exhausted_q,snap_timeout_q,snap_migration_q;
  reg [31:0] snap_lane_fault_migration_q,snap_duty_defer_q,snap_permit_defer_q,snap_mapping_defer_q;
  reg [31:0] snap_rx_ooo_q,snap_rx_duplicate_q,snap_rx_old_q,snap_rx_future_q;
  reg [31:0] snap_rx_stale_session_q,snap_rx_stale_path_q,snap_rx_gap_q,snap_rx_gap_timeout_q;
  reg [3:0] snap_scheduler_defer_q;
  reg [31:0] snap_scheduler_starvation_q;
  reg [31:0] snap_tx_producer_q,snap_tx_consumer_q,snap_tx_hwm_q,snap_tx_full_q;
  reg [15:0] snap_tx_generation_q;
  reg [31:0] snap_rx_producer_q,snap_rx_consumer_q,snap_rx_hwm_q,snap_rx_full_q;
  reg [15:0] snap_rx_generation_q;
  reg [31:0] snap_desc_complete_q,snap_desc_error_q,snap_desc_abort_q,snap_desc_stale_q;
  reg [31:0] snap_axis_tx_stall_q,snap_axis_rx_stall_q,snap_axis_error_q;
  reg [31:0] snap_store_used_q,snap_store_hwm_q;
  reg [255:0] snap_lane_frames_q,snap_lane_bytes_q,snap_lane_retries_q;
  reg [255:0] snap_lane_migrations_q,snap_lane_defer_q;

  function automatic is_power_of_two(input [31:0] value);
    is_power_of_two=(value>=2)&&((value&(value-1))==0);
  endfunction

  integer lane_index;
  always @(posedge clk or negedge rst_n) begin
    if(!rst_n) begin
      enable_request_o<=0;disable_request_o<=0;reset_request_o<=0;abort_request_o<=0;
      snapshot_request_o<=0;clear_sticky_request_o<=0;snapshot_valid_q<=0;
      protocol_mode_o<=32'd2;session_epoch_o<=32'd1;path_epoch_o<=16'd0;
      tx_window_size_o<=16'd32;rx_window_size_o<=16'd64;retry_config_o<=32'h0007_fa00;
      sack_window_bits_o<=7'd32;scheduler_active_mask_o<=8'hff;
      scheduler_starvation_bound_o<=32'd4096;lane_weights_o<=64'h0101010101010101;
      tx_ring_depth_o<=16'd64;rx_ring_depth_o<=16'd64;
      abort_stream_id_o<=0;abort_object_id_o<=0;configuration_error_sticky_o<=0;
    end else begin
      enable_request_o<=0;disable_request_o<=0;reset_request_o<=0;abort_request_o<=0;
      snapshot_request_o<=0;clear_sticky_request_o<=0;
      if(wr_en&&wr_addr==`IR_REG_P8D_CONTROL) begin
        enable_request_o<=wr_data[`IR_P8D_CONTROL_ENABLE_REQUEST_SHIFT];
        disable_request_o<=wr_data[`IR_P8D_CONTROL_DISABLE_REQUEST_SHIFT];
        reset_request_o<=wr_data[`IR_P8D_CONTROL_RESET_REQUEST_SHIFT];
        abort_request_o<=wr_data[`IR_P8D_CONTROL_ABORT_REQUEST_SHIFT];
        snapshot_request_o<=wr_data[`IR_P8D_CONTROL_SNAPSHOT_REQUEST_SHIFT];
        clear_sticky_request_o<=wr_data[`IR_P8D_CONTROL_CLEAR_STICKY_REQUEST_SHIFT];
        if(wr_data[`IR_P8D_CONTROL_CLEAR_STICKY_REQUEST_SHIFT])
          configuration_error_sticky_o<=0;
        if(wr_data[`IR_P8D_CONTROL_SNAPSHOT_REQUEST_SHIFT]) begin
          snapshot_valid_q<=1;
          snap_tx_next_q<=tx_next_sequence_i;snap_tx_ack_base_q<=tx_ack_base_i;
          snap_rx_base_q<=rx_base_sequence_i;snap_outstanding_q<=outstanding_count_i;
          snap_outstanding_hwm_q<=outstanding_high_watermark_i;snap_sack_q<=sack_bitmap_i;
          snap_ack_aggregation_q<=ack_aggregation_count_i;snap_ack_timer_q<=ack_timer_expiry_count_i;
          snap_ack_sent_q<=ack_frames_sent_i;snap_ack_received_q<=ack_frames_received_i;
          snap_duplicate_ack_q<=duplicate_ack_count_i;snap_stale_ack_q<=stale_ack_count_i;
          snap_bad_ack_q<=out_of_window_ack_count_i;snap_retry_q<=tx_retry_count_i;
          snap_exhausted_q<=tx_retry_exhausted_count_i;snap_timeout_q<=timeout_count_i;
          snap_migration_q<=migration_count_i;snap_lane_fault_migration_q<=lane_fault_migration_count_i;
          snap_duty_defer_q<=duty_defer_count_i;snap_permit_defer_q<=permit_defer_count_i;
          snap_mapping_defer_q<=mapping_defer_count_i;snap_rx_ooo_q<=rx_out_of_order_count_i;
          snap_rx_duplicate_q<=rx_duplicate_count_i;snap_rx_old_q<=rx_old_count_i;
          snap_rx_future_q<=rx_future_count_i;snap_rx_stale_session_q<=rx_stale_session_count_i;
          snap_rx_stale_path_q<=rx_stale_path_count_i;snap_rx_gap_q<=rx_gap_count_i;
          snap_rx_gap_timeout_q<=rx_gap_timeout_count_i;snap_scheduler_defer_q<=scheduler_defer_reason_i;
          snap_scheduler_starvation_q<=scheduler_starvation_max_i;
          snap_tx_producer_q<=tx_ring_producer_i;snap_tx_consumer_q<=tx_ring_consumer_i;
          snap_tx_generation_q<=tx_ring_generation_i;snap_tx_hwm_q<=tx_ring_high_watermark_i;
          snap_tx_full_q<=tx_ring_full_count_i;snap_rx_producer_q<=rx_ring_producer_i;
          snap_rx_consumer_q<=rx_ring_consumer_i;snap_rx_generation_q<=rx_ring_generation_i;
          snap_rx_hwm_q<=rx_ring_high_watermark_i;snap_rx_full_q<=rx_ring_full_count_i;
          snap_desc_complete_q<=descriptor_complete_count_i;snap_desc_error_q<=descriptor_error_count_i;
          snap_desc_abort_q<=descriptor_abort_count_i;snap_desc_stale_q<=descriptor_stale_count_i;
          snap_axis_tx_stall_q<=axis_tx_stall_cycles_i;snap_axis_rx_stall_q<=axis_rx_stall_cycles_i;
          snap_axis_error_q<=axis_protocol_error_count_i;snap_store_used_q<=payload_store_used_i;
          snap_store_hwm_q<=payload_store_high_watermark_i;
          snap_lane_frames_q<=lane_scheduled_frames_flat_i;snap_lane_bytes_q<=lane_scheduled_bytes_flat_i;
          snap_lane_retries_q<=lane_retries_flat_i;snap_lane_migrations_q<=lane_migrations_flat_i;
          snap_lane_defer_q<=lane_defer_flat_i;
        end
      end
      if(wr_en) begin
        case(wr_addr)
          `IR_REG_P8D_PROTOCOL_MODE: if(wr_data==1||wr_data==2)protocol_mode_o<=wr_data;
            else configuration_error_sticky_o<=1;
          `IR_REG_P8D_SESSION_EPOCH: session_epoch_o<=wr_data;
          `IR_REG_P8D_PATH_EPOCH: path_epoch_o<=wr_data[15:0];
          `IR_REG_P8D_TX_WINDOW_SIZE: if(is_power_of_two(wr_data)&&wr_data>=32&&wr_data<=MAX_WINDOW_SIZE)
            tx_window_size_o<=wr_data[15:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_RX_WINDOW_SIZE: if(is_power_of_two(wr_data)&&wr_data>=32&&wr_data<=MAX_WINDOW_SIZE)
            rx_window_size_o<=wr_data[15:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_RETRY_CONFIG: retry_config_o<=wr_data;
          `IR_REG_P8D_SACK_WINDOW_BITS: if((wr_data==32||wr_data==64)&&wr_data<=MAX_WINDOW_SIZE)
            sack_window_bits_o<=wr_data[6:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_SCHEDULER_ACTIVE_MASK: scheduler_active_mask_o<=wr_data[7:0];
          `IR_REG_P8D_SCHEDULER_STARVATION_BOUND: if(wr_data!=0)scheduler_starvation_bound_o<=wr_data;
            else configuration_error_sticky_o<=1;
          `IR_REG_P8D_SCHEDULER_WEIGHT0: if(wr_data[7:0]!=0)lane_weights_o[7:0]<=wr_data[7:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_SCHEDULER_WEIGHT1: if(wr_data[7:0]!=0)lane_weights_o[15:8]<=wr_data[7:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_SCHEDULER_WEIGHT2: if(wr_data[7:0]!=0)lane_weights_o[23:16]<=wr_data[7:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_SCHEDULER_WEIGHT3: if(wr_data[7:0]!=0)lane_weights_o[31:24]<=wr_data[7:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_SCHEDULER_WEIGHT4: if(wr_data[7:0]!=0)lane_weights_o[39:32]<=wr_data[7:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_SCHEDULER_WEIGHT5: if(wr_data[7:0]!=0)lane_weights_o[47:40]<=wr_data[7:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_SCHEDULER_WEIGHT6: if(wr_data[7:0]!=0)lane_weights_o[55:48]<=wr_data[7:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_SCHEDULER_WEIGHT7: if(wr_data[7:0]!=0)lane_weights_o[63:56]<=wr_data[7:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_TX_RING_DEPTH: if(is_power_of_two(wr_data)&&wr_data<=MAX_RING_DEPTH)
            tx_ring_depth_o<=wr_data[15:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_RX_RING_DEPTH: if(is_power_of_two(wr_data)&&wr_data<=MAX_RING_DEPTH)
            rx_ring_depth_o<=wr_data[15:0];else configuration_error_sticky_o<=1;
          `IR_REG_P8D_ABORT_STREAM_ID: abort_stream_id_o<=wr_data;
          `IR_REG_P8D_ABORT_OBJECT_ID: abort_object_id_o<=wr_data;
          default: ;
        endcase
      end
    end
  end

  integer statistic_index;
  integer statistic_lane;
  integer statistic_field;
  always @* begin
    rd_data=0;rd_valid=rd_en;
    if(rd_en) begin
      case(rd_addr)
        `IR_REG_P8D_CONTROL:rd_data=0;
        `IR_REG_P8D_STATUS:rd_data={24'd0,abort_active_i,
          (sticky_error_i|configuration_error_sticky_o),rx_ring_full_i,tx_ring_full_i,
          rx_window_full_i,tx_window_full_i,snapshot_valid_q,enabled_i};
        `IR_REG_P8D_L2_PROTOCOL_VERSION:rd_data=32'd2;
        `IR_REG_P8D_L2_CAPABILITIES:rd_data=32'h0008_011f;
        `IR_REG_P8D_PROTOCOL_MODE:rd_data=protocol_mode_o;
        `IR_REG_P8D_SESSION_EPOCH:rd_data=session_epoch_o;
        `IR_REG_P8D_PATH_EPOCH:rd_data={16'd0,path_epoch_o};
        `IR_REG_P8D_TX_WINDOW_SIZE:rd_data={16'd0,tx_window_size_o};
        `IR_REG_P8D_RX_WINDOW_SIZE:rd_data={16'd0,rx_window_size_o};
        `IR_REG_P8D_RETRY_CONFIG:rd_data=retry_config_o;
        `IR_REG_P8D_TX_NEXT_SEQUENCE:rd_data={16'd0,snap_tx_next_q};
        `IR_REG_P8D_TX_ACK_BASE:rd_data={16'd0,snap_tx_ack_base_q};
        `IR_REG_P8D_RX_BASE_SEQUENCE:rd_data={16'd0,snap_rx_base_q};
        `IR_REG_P8D_GLOBAL_OUTSTANDING_COUNT:rd_data=snap_outstanding_q;
        `IR_REG_P8D_GLOBAL_OUTSTANDING_HIGH_WATERMARK:rd_data=snap_outstanding_hwm_q;
        `IR_REG_P8D_SACK_WINDOW_BITS:rd_data={25'd0,sack_window_bits_o};
        `IR_REG_P8D_LAST_SACK_BITMAP_LOW:rd_data=snap_sack_q[31:0];
        `IR_REG_P8D_LAST_SACK_BITMAP_HIGH:rd_data=snap_sack_q[63:32];
        `IR_REG_P8D_ACK_AGGREGATION_COUNT:rd_data=snap_ack_aggregation_q;
        `IR_REG_P8D_ACK_TIMER_EXPIRY_COUNT:rd_data=snap_ack_timer_q;
        `IR_REG_P8D_ACK_FRAMES_SENT:rd_data=snap_ack_sent_q;
        `IR_REG_P8D_ACK_FRAMES_RECEIVED:rd_data=snap_ack_received_q;
        `IR_REG_P8D_DUPLICATE_ACK_COUNT:rd_data=snap_duplicate_ack_q;
        `IR_REG_P8D_STALE_ACK_COUNT:rd_data=snap_stale_ack_q;
        `IR_REG_P8D_OUT_OF_WINDOW_ACK_COUNT:rd_data=snap_bad_ack_q;
        `IR_REG_P8D_TX_RETRY_COUNT:rd_data=snap_retry_q;
        `IR_REG_P8D_TX_RETRY_EXHAUSTED_COUNT:rd_data=snap_exhausted_q;
        `IR_REG_P8D_TIMEOUT_COUNT:rd_data=snap_timeout_q;
        `IR_REG_P8D_MIGRATION_COUNT:rd_data=snap_migration_q;
        `IR_REG_P8D_LANE_FAULT_MIGRATION_COUNT:rd_data=snap_lane_fault_migration_q;
        `IR_REG_P8D_DUTY_DEFER_COUNT:rd_data=snap_duty_defer_q;
        `IR_REG_P8D_PERMIT_DEFER_COUNT:rd_data=snap_permit_defer_q;
        `IR_REG_P8D_MAPPING_DEFER_COUNT:rd_data=snap_mapping_defer_q;
        `IR_REG_P8D_RX_OUT_OF_ORDER_COUNT:rd_data=snap_rx_ooo_q;
        `IR_REG_P8D_RX_DUPLICATE_COUNT:rd_data=snap_rx_duplicate_q;
        `IR_REG_P8D_RX_OLD_COUNT:rd_data=snap_rx_old_q;
        `IR_REG_P8D_RX_FUTURE_COUNT:rd_data=snap_rx_future_q;
        `IR_REG_P8D_RX_STALE_SESSION_COUNT:rd_data=snap_rx_stale_session_q;
        `IR_REG_P8D_RX_STALE_PATH_EPOCH_COUNT:rd_data=snap_rx_stale_path_q;
        `IR_REG_P8D_RX_GAP_COUNT:rd_data=snap_rx_gap_q;
        `IR_REG_P8D_RX_GAP_TIMEOUT_COUNT:rd_data=snap_rx_gap_timeout_q;
        `IR_REG_P8D_SCHEDULER_ACTIVE_MASK:rd_data={24'd0,scheduler_active_mask_o};
        `IR_REG_P8D_SCHEDULER_STARVATION_BOUND:rd_data=scheduler_starvation_bound_o;
        `IR_REG_P8D_SCHEDULER_DEFER_REASON:rd_data={28'd0,snap_scheduler_defer_q};
        `IR_REG_P8D_SCHEDULER_WEIGHT0:rd_data={24'd0,lane_weights_o[7:0]};
        `IR_REG_P8D_SCHEDULER_WEIGHT1:rd_data={24'd0,lane_weights_o[15:8]};
        `IR_REG_P8D_SCHEDULER_WEIGHT2:rd_data={24'd0,lane_weights_o[23:16]};
        `IR_REG_P8D_SCHEDULER_WEIGHT3:rd_data={24'd0,lane_weights_o[31:24]};
        `IR_REG_P8D_SCHEDULER_WEIGHT4:rd_data={24'd0,lane_weights_o[39:32]};
        `IR_REG_P8D_SCHEDULER_WEIGHT5:rd_data={24'd0,lane_weights_o[47:40]};
        `IR_REG_P8D_SCHEDULER_WEIGHT6:rd_data={24'd0,lane_weights_o[55:48]};
        `IR_REG_P8D_SCHEDULER_WEIGHT7:rd_data={24'd0,lane_weights_o[63:56]};
        `IR_REG_P8D_SCHEDULER_STARVATION_MAX:rd_data=snap_scheduler_starvation_q;
        `IR_REG_P8D_TX_RING_DEPTH:rd_data={16'd0,tx_ring_depth_o};
        `IR_REG_P8D_TX_RING_PRODUCER:rd_data=snap_tx_producer_q;
        `IR_REG_P8D_TX_RING_CONSUMER:rd_data=snap_tx_consumer_q;
        `IR_REG_P8D_TX_RING_GENERATION:rd_data={16'd0,snap_tx_generation_q};
        `IR_REG_P8D_TX_RING_HIGH_WATERMARK:rd_data=snap_tx_hwm_q;
        `IR_REG_P8D_TX_RING_FULL_COUNT:rd_data=snap_tx_full_q;
        `IR_REG_P8D_RX_RING_DEPTH:rd_data={16'd0,rx_ring_depth_o};
        `IR_REG_P8D_RX_RING_PRODUCER:rd_data=snap_rx_producer_q;
        `IR_REG_P8D_RX_RING_CONSUMER:rd_data=snap_rx_consumer_q;
        `IR_REG_P8D_RX_RING_GENERATION:rd_data={16'd0,snap_rx_generation_q};
        `IR_REG_P8D_RX_RING_HIGH_WATERMARK:rd_data=snap_rx_hwm_q;
        `IR_REG_P8D_RX_RING_FULL_COUNT:rd_data=snap_rx_full_q;
        `IR_REG_P8D_DESCRIPTOR_COMPLETE_COUNT:rd_data=snap_desc_complete_q;
        `IR_REG_P8D_DESCRIPTOR_ERROR_COUNT:rd_data=snap_desc_error_q;
        `IR_REG_P8D_DESCRIPTOR_ABORT_COUNT:rd_data=snap_desc_abort_q;
        `IR_REG_P8D_DESCRIPTOR_STALE_GENERATION_COUNT:rd_data=snap_desc_stale_q;
        `IR_REG_P8D_AXIS_TX_STALL_CYCLES:rd_data=snap_axis_tx_stall_q;
        `IR_REG_P8D_AXIS_RX_STALL_CYCLES:rd_data=snap_axis_rx_stall_q;
        `IR_REG_P8D_AXIS_PROTOCOL_ERROR_COUNT:rd_data=snap_axis_error_q;
        `IR_REG_P8D_PAYLOAD_STORE_USED:rd_data=snap_store_used_q;
        `IR_REG_P8D_PAYLOAD_STORE_HIGH_WATERMARK:rd_data=snap_store_hwm_q;
        `IR_REG_P8D_ABORT_STREAM_ID:rd_data=abort_stream_id_o;
        `IR_REG_P8D_ABORT_OBJECT_ID:rd_data=abort_object_id_o;
        `IR_REG_P8D_REGISTER_MAP_VERSION:rd_data=`IR_REGISTER_MAP_VERSION;
        `IR_REG_P8D_REGISTER_MAP_HASH_LOW:rd_data=`IR_REGISTER_MAP_HASH_LOW;
        default: begin
          if(rd_addr>=12'h640&&rd_addr<=12'h6dc&&rd_addr[1:0]==0) begin
            statistic_index=(rd_addr-12'h640)>>2;
            statistic_lane=statistic_index/5;
            statistic_field=statistic_index%5;
            case(statistic_field)
              0:rd_data=snap_lane_frames_q[statistic_lane*32+:32];
              1:rd_data=snap_lane_bytes_q[statistic_lane*32+:32];
              2:rd_data=snap_lane_retries_q[statistic_lane*32+:32];
              3:rd_data=snap_lane_migrations_q[statistic_lane*32+:32];
              4:rd_data=snap_lane_defer_q[statistic_lane*32+:32];
              default:rd_data=0;
            endcase
          end
        end
      endcase
    end
  end
endmodule
`default_nettype wire
