`timescale 1ns/1ps
`default_nettype none

// P10.4 connector-local ACK echo quarantine.
//
// AX7020 lanes are installed as two-module connector pairs: J10 carries
// lanes 0/1 and J11 carries lanes 2/3.  Current hardware evidence shows that
// a physical ACK on the first lane of a pair can create raw optical edges at
// the adjacent local receiver.  This monitor-only mapper extends the existing
// per-module RX admission source to that paired receiver only for an ACK.
// Ordinary DATA on the peer lane remains independent, and the other connector
// pair remains open.  Every input is observational: there is no output to a
// TX request, GLOBAL_PERMIT, SD, Mode, duty guard, kill, or scheduler path.
module p10_4_connector_ack_rx_quarantine #(
  parameter integer LANE_COUNT = 4
) (
  input  wire [LANE_COUNT-1:0] final_local_txd_i,
  input  wire [LANE_COUNT-1:0] local_tx_is_ack_i,
  output wire [LANE_COUNT-1:0] paired_ack_txd_o,
  output wire [LANE_COUNT-1:0] rx_quarantine_source_o
);
  initial begin
    if (LANE_COUNT < 2 || (LANE_COUNT % 2) != 0)
      $error("P10.4 connector ACK quarantine requires an even lane count >=2");
  end

  genvar lane;
  generate
    for (lane = 0; lane < LANE_COUNT; lane = lane + 1) begin : g_pair
      localparam integer PEER_LANE = lane ^ 1;
      assign paired_ack_txd_o[lane] =
          final_local_txd_i[PEER_LANE] && local_tx_is_ack_i[PEER_LANE];
      assign rx_quarantine_source_o[lane] =
          final_local_txd_i[lane] || paired_ack_txd_o[lane];
    end
  endgenerate
endmodule

`default_nettype wire
