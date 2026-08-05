// Auto-generated from config/p8d_data_plane.yaml; do not edit.
package ir_p8d_data_plane_pkg;
  localparam logic [255:0] P8D_CONFIG_SHA256 = 256'h7254ea226e2d369f3c2e4532059736eee63a30f6f90deedc317ba419fd47f732;
  localparam int unsigned P8D_LEGACY_MODE_VERSION = 1;
  localparam int unsigned P8D_VNEXT_MODE_VERSION = 2;
  localparam int unsigned P8D_SEQUENCE_WIDTH = 16;
  localparam int unsigned P8D_GLOBAL_OUTSTANDING_DEFAULT = 32;
  localparam int unsigned P8D_RX_REORDER_WINDOW = 64;
  localparam int unsigned P8D_DUPLICATE_HISTORY_DEPTH = 128;
  localparam int unsigned P8D_MAX_RETRY = 7;
  localparam int unsigned P8D_RTO_INITIAL_CYCLES = 64000;
  localparam int unsigned P8D_RTO_MIN_CYCLES = 32000;
  localparam int unsigned P8D_RTO_MAX_CYCLES = 512000;
  localparam int unsigned P8D_ACK_AGGREGATION_FRAME_THRESHOLD = 8;
  localparam int unsigned P8D_ACK_AGGREGATION_MAX_DELAY_CYCLES = 32000;
  localparam int unsigned P8D_ACK_CREDIT_LOW_WATERMARK = 8;
  localparam int unsigned P8D_MAX_ACK_PAYLOAD_BYTES = 32;
  localparam int unsigned P8D_SCHEDULER_WEIGHT_WIDTH = 8;
  localparam int unsigned P8D_STARVATION_BOUND = 4096;
  localparam int unsigned P8D_MAX_FRAME_BYTES = 288;
  localparam int unsigned P8D_MAX_L1_PAYLOAD_BYTES = 247;
  localparam int unsigned P8D_RFAP_V1_USEFUL_CHUNK_BYTES = 215;
  localparam int unsigned P8D_TX_RING_DEPTH = 64;
  localparam int unsigned P8D_RX_RING_DEPTH = 64;
  localparam int unsigned P8D_DESCRIPTOR_BYTES = 64;
  localparam int unsigned P8D_DESCRIPTOR_ALIGNMENT_BYTES = 64;
  localparam int unsigned P8D_DESCRIPTOR_GENERATION_BITS = 16;
  localparam int unsigned P8D_RING_INDEX_BITS = 32;
  localparam int unsigned P8D_SESSION_EPOCH_WIDTH = 32;
  localparam int unsigned P8D_PATH_EPOCH_WIDTH = 16;
  localparam int unsigned P8D_ACCEPTED_PREVIOUS_PATH_EPOCHS = 1;
  localparam int unsigned P8D_STREAM_ID_WIDTH = 32;
  localparam int unsigned P8D_OBJECT_ID_WIDTH = 32;
  localparam int unsigned P8D_AXIS_USER_WIDTH = 64;
  localparam int unsigned P8D_Z7010_2LANE_DEV_GLOBAL_OUTSTANDING = 32;
  localparam int unsigned P8D_Z7010_2LANE_DEV_SACK_WINDOW_BITS = 32;
  localparam int unsigned P8D_Z7010_2LANE_DEV_AXIS_DATA_WIDTH = 32;
  localparam int unsigned P8D_Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE_GLOBAL_OUTSTANDING = 64;
  localparam int unsigned P8D_Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE_SACK_WINDOW_BITS = 64;
  localparam int unsigned P8D_Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE_AXIS_DATA_WIDTH = 64;
  localparam int unsigned P8D_Z7020_ROTATING_8LANE_MODEL_GLOBAL_OUTSTANDING = 64;
  localparam int unsigned P8D_Z7020_ROTATING_8LANE_MODEL_SACK_WINDOW_BITS = 64;
  localparam int unsigned P8D_Z7020_ROTATING_8LANE_MODEL_AXIS_DATA_WIDTH = 64;
  typedef enum logic [3:0] {
    P8D_TX_FREE=4'd0, P8D_TX_ALLOCATED=4'd1, P8D_TX_QUEUED=4'd2,
    P8D_TX_SCHEDULED=4'd3, P8D_TX_IN_FLIGHT=4'd4, P8D_TX_ACKED=4'd5,
    P8D_TX_RETRY_PENDING=4'd6, P8D_TX_ABORT_PENDING=4'd7,
    P8D_TX_FAILED=4'd8, P8D_TX_RECLAIMABLE=4'd9
  } p8d_tx_state_t;
endpackage
