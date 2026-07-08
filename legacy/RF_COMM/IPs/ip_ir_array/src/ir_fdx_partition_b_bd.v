module ir_fdx_partition_b_bd #(
  parameter integer LANE_COUNT        = 2,
  parameter integer B_SESSION_ID      = 16'h2203,
  parameter integer B_CNT_CHIP_MAX    = 7,
  parameter integer B_CNT_PREAMBLE    = 64,
  parameter integer RAW_PACKET_BYTES  = 64,
  parameter integer FRAGMENT_BYTES    = 16,
  parameter integer APP_PAYLOAD_BYTES = 56,
  parameter integer B2A_ENABLE        = 1,
  parameter integer B_TX_LANE_MASK    = 2,
  parameter integer B_RX_LANE_MASK    = 1
)(
  input  wire                  clk_phy,
  input  wire                  rst_n,
  output wire [LANE_COUNT-1:0] ir_tx_out,
  input  wire [LANE_COUNT-1:0] ir_rx_in,
  output wire [LANE_COUNT-1:0] ir_sd,
  output wire [LANE_COUNT-1:0] ir_mode_out,
  output wire [31:0]           debug_status
);
  ir_fdx_partition_b_core #(
    .LANE_COUNT        (LANE_COUNT),
    .B_SESSION_ID      (B_SESSION_ID),
    .B_CNT_CHIP_MAX    (B_CNT_CHIP_MAX),
    .B_CNT_PREAMBLE    (B_CNT_PREAMBLE),
    .RAW_PACKET_BYTES  (RAW_PACKET_BYTES),
    .FRAGMENT_BYTES    (FRAGMENT_BYTES),
    .APP_PAYLOAD_BYTES (APP_PAYLOAD_BYTES),
    .B2A_ENABLE        (B2A_ENABLE),
    .B_TX_LANE_MASK    (B_TX_LANE_MASK),
    .B_RX_LANE_MASK    (B_RX_LANE_MASK)
  ) u_core (
    .clk_phy      (clk_phy),
    .rst_n        (rst_n),
    .ir_tx_out    (ir_tx_out),
    .ir_rx_in     (ir_rx_in),
    .ir_sd        (ir_sd),
    .ir_mode_out  (ir_mode_out),
    .debug_status (debug_status)
  );
endmodule
