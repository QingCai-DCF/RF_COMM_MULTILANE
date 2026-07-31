// Generated from config/performance/p10_1_*.yaml; do not edit.
package p10_1_contract_pkg;
  localparam longint unsigned P10_1_PL_TIMER_FREQUENCY_HZ = 64000000;
  localparam longint unsigned P10_1_PL_TIMER_COUNTER_WIDTH_BITS = 64;
  localparam longint unsigned P10_1_PS_TIMER_FREQUENCY_HZ = 333333343;
  localparam longint unsigned P10_1_PS_TRACE_DEPTH_RECORDS = 1024;
  localparam longint unsigned P10_1_PL_EVENT_FIFO_DEPTH_RECORDS = 256;
  localparam longint unsigned P10_1_BUFFER_COUNT = 4;
  localparam longint unsigned P10_1_BUFFER_SIZE_BYTES = 262144;
  localparam longint unsigned P10_1_RING_DEPTH = 16;
  localparam longint unsigned P10_1_DESCRIPTOR_BATCH = 4;
  localparam longint unsigned P10_1_INTERRUPT_COALESCING = 16;
  localparam longint unsigned P10_1_SEGMENT_SIZE_BYTES = 65536;
  localparam longint unsigned P10_1_MAX_STREAM_SIZE_BYTES = 134217728;
  localparam longint unsigned P10_1_ACK_AGGREGATION_THRESHOLD = 8;
  localparam longint unsigned P10_1_DIRECTION_WINDOW_US = 250000;
  localparam longint unsigned P10_1_OUTSTANDING_FRAMES = 32;
  localparam longint unsigned P10_1_LANE_MASK = 3;
  localparam longint unsigned P10_1_MEASUREMENT_DURATION_SECONDS = 30;
  localparam longint unsigned P10_1_HARD_TARGET_BPS = 4000000;
  localparam longint unsigned P10_1_STRETCH_TARGET_BPS = 4800000;
  localparam longint unsigned P10_1_MANDATORY_STREAM_SIZE_BYTES = 67108864;
  localparam longint unsigned P10_1_OPTIONAL_STREAM_SIZE_BYTES = 134217728;

  typedef enum logic [3:0] {
    P10_1_COMMAND_PERF_CAPS = 4'd1,
    P10_1_COMMAND_PERF_CONFIG = 4'd2,
    P10_1_COMMAND_PERF_START = 4'd3,
    P10_1_COMMAND_PERF_STATUS = 4'd4,
    P10_1_COMMAND_PERF_SNAPSHOT = 4'd5,
    P10_1_COMMAND_PERF_STOP = 4'd6,
    P10_1_COMMAND_PERF_ABORT = 4'd7,
    P10_1_COMMAND_PERF_CLEAR = 4'd8
  } p10_1_perf_command_t;

  typedef enum logic [3:0] {
    P10_1_BUFFER_FREE = 4'd0,
    P10_1_BUFFER_FILLING = 4'd1,
    P10_1_BUFFER_READY = 4'd2,
    P10_1_BUFFER_DMA_OWNED = 4'd3,
    P10_1_BUFFER_IN_FLIGHT = 4'd4,
    P10_1_BUFFER_REMOTE_RECEIVED = 4'd5,
    P10_1_BUFFER_VERIFYING = 4'd6,
    P10_1_BUFFER_COMMITTED = 4'd7,
    P10_1_BUFFER_ERROR = 4'd8,
    P10_1_BUFFER_RECLAIMABLE = 4'd9
  } p10_1_buffer_state_t;
endpackage
