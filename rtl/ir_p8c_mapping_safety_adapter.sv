`timescale 1ns/1ps
`default_nettype none

// Stateless adapter from the canonical P8B active mapping to physical-module
// safety ownership. It does not keep a second current/candidate/path-epoch
// state and therefore cannot diverge from ir_path_mapping_engine.
module ir_p8c_mapping_safety_adapter #(
  parameter integer PHYSICAL_MODULE_COUNT = 32,
  parameter integer FIXED_ENDPOINT = 1
) (
  input  wire                                 active_mapping_valid_i,
  input  wire [39:0]                          active_current_fixed_i,
  input  wire [23:0]                          active_current_bank_i,
  input  wire [31:0]                          active_path_epoch_i,
  input  wire [31:0]                          logical_path_epoch_i,
  input  wire [7:0]                           logical_selected_i,
  input  wire [7:0]                           logical_lane_tx_permit_i,
  input  wire [7:0]                           logical_frame_admitted_i,
  input  wire [7:0]                           logical_txd_waveform_i,
  output reg  [PHYSICAL_MODULE_COUNT-1:0]     physical_module_selected_o,
  output reg  [PHYSICAL_MODULE_COUNT-1:0]     bank_one_hot_valid_o,
  output reg  [PHYSICAL_MODULE_COUNT-1:0]     lane_tx_permit_o,
  output reg  [PHYSICAL_MODULE_COUNT-1:0]     path_epoch_valid_o,
  output reg  [PHYSICAL_MODULE_COUNT-1:0]     frame_admitted_o,
  output reg  [PHYSICAL_MODULE_COUNT-1:0]     txd_waveform_o,
  output reg                                  mapping_collision_o,
  output reg                                  adapter_mapping_valid_o
);
  integer lane;
  integer physical_index;
  integer bank_index;
  integer scan_index;
  integer bank_selected_count [0:7];

  always @* begin
    physical_module_selected_o = {PHYSICAL_MODULE_COUNT{1'b0}};
    bank_one_hot_valid_o = {PHYSICAL_MODULE_COUNT{1'b0}};
    lane_tx_permit_o = {PHYSICAL_MODULE_COUNT{1'b0}};
    path_epoch_valid_o = {PHYSICAL_MODULE_COUNT{1'b0}};
    frame_admitted_o = {PHYSICAL_MODULE_COUNT{1'b0}};
    txd_waveform_o = {PHYSICAL_MODULE_COUNT{1'b0}};
    mapping_collision_o = 1'b0;
    adapter_mapping_valid_o = active_mapping_valid_i &&
        (logical_path_epoch_i == active_path_epoch_i);
    for (scan_index = 0; scan_index < 8; scan_index = scan_index + 1)
      bank_selected_count[scan_index] = 0;

    for (lane = 0; lane < 8; lane = lane + 1) begin
      if (FIXED_ENDPOINT != 0)
        physical_index = active_current_fixed_i[lane*5 +: 5];
      else
        physical_index = lane;
      if (FIXED_ENDPOINT != 0)
        bank_index = active_current_bank_i[lane*3 +: 3];
      else
        bank_index = lane;

      if (logical_selected_i[lane]) begin
        if (physical_index < 0 || physical_index >= PHYSICAL_MODULE_COUNT ||
            bank_index < 0 || bank_index > 7) begin
          adapter_mapping_valid_o = 1'b0;
          mapping_collision_o = 1'b1;
        end else begin
          if (physical_module_selected_o[physical_index])
            mapping_collision_o = 1'b1;
          physical_module_selected_o[physical_index] = 1'b1;
          lane_tx_permit_o[physical_index] = logical_lane_tx_permit_i[lane];
          path_epoch_valid_o[physical_index] =
              adapter_mapping_valid_o && (logical_path_epoch_i == active_path_epoch_i);
          frame_admitted_o[physical_index] = logical_frame_admitted_i[lane];
          txd_waveform_o[physical_index] = logical_txd_waveform_i[lane];
          bank_selected_count[bank_index] = bank_selected_count[bank_index] + 1;
        end
      end
    end

    for (scan_index = 0; scan_index < PHYSICAL_MODULE_COUNT; scan_index = scan_index + 1) begin
      if (physical_module_selected_o[scan_index]) begin
        if (FIXED_ENDPOINT != 0)
          bank_index = scan_index >> 2;
        else
          bank_index = scan_index;
        if (bank_index >= 0 && bank_index < 8 && bank_selected_count[bank_index] == 1)
          bank_one_hot_valid_o[scan_index] = 1'b1;
        else
          mapping_collision_o = 1'b1;
      end
    end
    if (mapping_collision_o)
      adapter_mapping_valid_o = 1'b0;
  end
endmodule

`default_nettype wire
