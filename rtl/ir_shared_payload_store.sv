`timescale 1ns/1ps
module ir_shared_payload_store #(
  parameter int ENTRY_COUNT = 64,
  parameter int MAX_FRAME_BYTES = 288,
  parameter int DATA_WIDTH = 64
) (
  input  logic                         clk,
  input  logic                         rst_n,
  input  logic                         allocate_valid_i,
  output logic                         allocate_ready_o,
  input  logic [$clog2(ENTRY_COUNT)-1:0] allocate_entry_i,
  input  logic                         release_valid_i,
  input  logic [$clog2(ENTRY_COUNT)-1:0] release_entry_i,
  input  logic                         write_valid_i,
  input  logic [$clog2(ENTRY_COUNT)-1:0] write_entry_i,
  input  logic [$clog2((MAX_FRAME_BYTES+(DATA_WIDTH/8)-1)/(DATA_WIDTH/8))-1:0] write_beat_i,
  input  logic [DATA_WIDTH-1:0]        write_data_i,
  input  logic [DATA_WIDTH/8-1:0]      write_keep_i,
  input  logic                         read_valid_i,
  input  logic [$clog2(ENTRY_COUNT)-1:0] read_entry_i,
  input  logic [$clog2((MAX_FRAME_BYTES+(DATA_WIDTH/8)-1)/(DATA_WIDTH/8))-1:0] read_beat_i,
  output logic [DATA_WIDTH-1:0]        read_data_o,
  output logic [DATA_WIDTH/8-1:0]      read_keep_o,
  output logic [$clog2(ENTRY_COUNT+1)-1:0] used_entries_o,
  output logic [$clog2(ENTRY_COUNT+1)-1:0] high_watermark_o,
  output logic                         ownership_error_sticky_o
);
  localparam int KEEP_WIDTH = DATA_WIDTH / 8;
  localparam int BEATS_PER_FRAME = (MAX_FRAME_BYTES + KEEP_WIDTH - 1) / KEEP_WIDTH;
  localparam int MEMORY_DEPTH = ENTRY_COUNT * BEATS_PER_FRAME;
  localparam int ADDRESS_WIDTH = $clog2(MEMORY_DEPTH);
  (* ram_style = "block" *) logic [DATA_WIDTH+KEEP_WIDTH-1:0] memory [0:MEMORY_DEPTH-1];
  logic [ENTRY_COUNT-1:0] allocated;
  logic [ADDRESS_WIDTH-1:0] write_address;
  logic [ADDRESS_WIDTH-1:0] read_address;
  logic write_pending;
  logic [ADDRESS_WIDTH-1:0] write_address_pending;
  logic [DATA_WIDTH+KEEP_WIDTH-1:0] write_payload_pending;
  logic read_pending;
  logic [ADDRESS_WIDTH-1:0] read_address_pending;

  assign allocate_ready_o = !allocated[allocate_entry_i];
  assign write_address = write_entry_i * BEATS_PER_FRAME + write_beat_i;
  assign read_address = read_entry_i * BEATS_PER_FRAME + read_beat_i;

  // RAM controls are produced only by synchronously reset command registers.
  // The asynchronously observable ownership table never directly drives a
  // RAMB enable, closing Vivado REQP-1839 without suppressing the rule.
  always_ff @(posedge clk) begin
    if (!rst_n) begin
      write_pending <= 1'b0;
      write_address_pending <= '0;
      write_payload_pending <= '0;
      read_pending <= 1'b0;
      read_address_pending <= '0;
      read_data_o <= '0;
      read_keep_o <= '0;
    end else begin
      if (write_pending)
        memory[write_address_pending] <= write_payload_pending;
      if (read_pending)
        {read_keep_o, read_data_o} <= memory[read_address_pending];
      write_pending <= write_valid_i && allocated[write_entry_i];
      if (write_valid_i && allocated[write_entry_i]) begin
        write_address_pending <= write_address;
        write_payload_pending <= {write_keep_i, write_data_i};
      end
      read_pending <= read_valid_i && allocated[read_entry_i];
      if (read_valid_i && allocated[read_entry_i])
        read_address_pending <= read_address;
    end
  end

  // Ownership reset is synchronous because it feeds the RAM command capture.
  always_ff @(posedge clk) begin
    integer ownership_delta;
    if (!rst_n) begin
      allocated <= '0;
      used_entries_o <= '0;
      high_watermark_o <= '0;
      ownership_error_sticky_o <= 1'b0;
    end else begin
      ownership_delta = 0;
      if (allocate_valid_i) begin
        if (!allocated[allocate_entry_i]) begin
          allocated[allocate_entry_i] <= 1'b1;
          ownership_delta = ownership_delta + 1;
        end else ownership_error_sticky_o <= 1'b1;
      end
      if (release_valid_i) begin
        if (allocated[release_entry_i]) begin
          allocated[release_entry_i] <= 1'b0;
          ownership_delta = ownership_delta - 1;
        end else ownership_error_sticky_o <= 1'b1;
      end
      if (allocate_valid_i && release_valid_i &&
          allocate_entry_i == release_entry_i)
        ownership_error_sticky_o <= 1'b1;
      if (ownership_delta != 0) begin
        used_entries_o <= used_entries_o + ownership_delta;
        if (used_entries_o + ownership_delta > high_watermark_o)
          high_watermark_o <= used_entries_o + ownership_delta;
      end
      if (write_valid_i && !allocated[write_entry_i]) ownership_error_sticky_o <= 1'b1;
      if (read_valid_i && !allocated[read_entry_i]) ownership_error_sticky_o <= 1'b1;
    end
  end
endmodule
