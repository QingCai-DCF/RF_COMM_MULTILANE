module ir_stream_bidir_b0_bd #(
  parameter integer B_SESSION_ID       = 16'h2201,
  parameter integer B_CNT_CHIP_MAX     = 15,
  parameter integer B_CNT_PREAMBLE     = 64,
  parameter integer B_RX_DATA_PHASE_DELAY_CYCLES = 0,
  parameter integer B_RX_DETECT_START_CYCLES = (B_CNT_CHIP_MAX >= 15) ? 0 : ((B_CNT_CHIP_MAX >= 7) ? 3 : 0),
  parameter integer B_RX_DETECT_END_CYCLES = (B_CNT_CHIP_MAX >= 15) ? 10 : B_CNT_CHIP_MAX,
  parameter integer B_RX_PREAMBLE_REALIGN_EDGE = 0,
  parameter integer B_GUARD_CYCLES     = 1408,
  parameter integer B_BACKOFF_SLOT_CYCLES = 1024,
  parameter integer B_START_IDLE_CYCLES = 100000,
  parameter integer B_RECOVERY_RESET_CYCLES = 2048,
  parameter integer B_PARALLEL_2LANE_MODE = 0,
  parameter integer B_DEBUG_SELECT_RX_STATUS = 0,
  parameter integer B_ACK_LANE_MASK = -1,
  parameter integer B_TX_LANE_MASK = -1,
  parameter integer B_RX_LANE_MASK = -1,
  parameter integer B_EXPECTED_A_LANE_MASK = -1,
  parameter integer RAW_PACKET_BYTES   = 255,
  parameter integer FRAGMENT_BYTES     = (RAW_PACKET_BYTES > 255) ? 255 : RAW_PACKET_BYTES,
  parameter integer APP_PAYLOAD_BYTES  = 247,
  parameter integer B2A_ENABLE         = 1,
  parameter integer B2A_FREE_RUN       = 0,
  parameter integer B2A_ECHO_ENABLE    = 0,
  parameter integer TX_GAP_CYCLES      = 0
)(
  input  wire        clk_phy,
  input  wire        rst_n,
  output wire        ir_tx_out,
  input  wire        ir_rx_in,
  output wire        ir_sd,
  output wire        ir_mode_out,
  output wire [31:0] debug_status
);
  wire [0:0] ir_tx_vec;
  wire [0:0] ir_rx_vec;
  wire [0:0] ir_sd_vec;
  wire [0:0] ir_mode_vec;

  assign ir_tx_out = ir_tx_vec[0];
  assign ir_rx_vec[0] = ir_rx_in;
  assign ir_sd = ir_sd_vec[0];
  assign ir_mode_out = ir_mode_vec[0];

  ir_stream_bidir_b0_core #(
    .LANE_COUNT(1),
    .B_SESSION_ID(B_SESSION_ID),
    .B_CNT_CHIP_MAX(B_CNT_CHIP_MAX),
    .B_CNT_PREAMBLE(B_CNT_PREAMBLE),
    .B_RX_DATA_PHASE_DELAY_CYCLES(B_RX_DATA_PHASE_DELAY_CYCLES),
    .B_RX_DETECT_START_CYCLES(B_RX_DETECT_START_CYCLES),
    .B_RX_DETECT_END_CYCLES(B_RX_DETECT_END_CYCLES),
    .B_RX_PREAMBLE_REALIGN_EDGE(B_RX_PREAMBLE_REALIGN_EDGE),
    .B_GUARD_CYCLES(B_GUARD_CYCLES),
    .B_BACKOFF_SLOT_CYCLES(B_BACKOFF_SLOT_CYCLES),
    .B_START_IDLE_CYCLES(B_START_IDLE_CYCLES),
    .B_RECOVERY_RESET_CYCLES(B_RECOVERY_RESET_CYCLES),
    .B_PARALLEL_2LANE_MODE(B_PARALLEL_2LANE_MODE),
    .B_DEBUG_SELECT_RX_STATUS(B_DEBUG_SELECT_RX_STATUS),
    .B_ACK_LANE_MASK(B_ACK_LANE_MASK),
    .B_TX_LANE_MASK(B_TX_LANE_MASK),
    .B_RX_LANE_MASK(B_RX_LANE_MASK),
    .B_EXPECTED_A_LANE_MASK(B_EXPECTED_A_LANE_MASK),
    .RAW_PACKET_BYTES(RAW_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .APP_PAYLOAD_BYTES(APP_PAYLOAD_BYTES),
    .B2A_ENABLE(B2A_ENABLE),
    .B2A_FREE_RUN(B2A_FREE_RUN),
    .B2A_ECHO_ENABLE(B2A_ECHO_ENABLE),
    .TX_GAP_CYCLES(TX_GAP_CYCLES)
  ) u_core (
    .clk_phy(clk_phy),
    .rst_n(rst_n),
    .ir_tx_out(ir_tx_vec),
    .ir_rx_in(ir_rx_vec),
    .ir_sd(ir_sd_vec),
    .ir_mode_out(ir_mode_vec),
    .debug_status(debug_status)
  );
endmodule
