// Generated from config/p10_5_dual_direction.yaml; do not edit.
package p10_5_dual_direction_pkg;
  localparam logic [31:0] P10_5_CAPABILITY_VERSION = 32'h0000_0001;
  localparam logic [31:0] P10_5_CAPABILITY_WORD = 32'h5035_021F;
  localparam logic [31:0] P10_5_CONFIG_HASH_LOW = 32'h44304D46;
  localparam int P10_5_LANE_COUNT = 4;
  localparam logic [3:0] P10_5_ACTIVE_LANE_MASK = 4'hF;
  localparam logic [3:0] P10_5_F_TO_R_LANE_MASK = 4'h3;
  localparam logic [3:0] P10_5_R_TO_F_LANE_MASK = 4'hC;
  localparam int P10_5_ROLE_EPOCH_WIDTH = 16;
  localparam int P10_5_SEQUENCE_WIDTH = 16;
  localparam int P10_5_OUTSTANDING = 32;
  localparam int P10_5_SACK_BITS = 32;
  localparam int P10_5_ACK_THRESHOLD = 8;
  localparam int P10_5_ACK_MAX_DELAY_CYCLES = 64000;
  localparam int P10_5_CONTROL_COLLISION_BACKOFF_CYCLES = 32000;
  localparam logic P10_5_PIGGYBACK_ENABLE = 1'b1;
  localparam logic P10_5_CONTROL_ONLY_ACK_ENABLE = 1'b1;
  typedef enum logic { P10_5_DIR_F_TO_R = 1'b0, P10_5_DIR_R_TO_F = 1'b1 } p10_5_direction_t;
  typedef enum logic { P10_5_MODE_LEGACY = 1'b0, P10_5_MODE_SPLIT = 1'b1 } p10_5_mode_t;
endpackage
