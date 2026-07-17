`timescale 1ns/1ps
module ir_handover_metrics #(
  parameter integer CYCLES_PER_US = 100
) (
  input  logic        clk,
  input  logic        rst_n,
  input  logic        phase_sample_event,
  input  logic        mapping_prepare_event,
  input  logic        mapping_ready_event,
  input  logic        commit_request_event,
  input  logic        commit_accept_event,
  input  logic        service_interrupt_event,
  input  logic        service_resume_event,
  input  logic        epoch_visible_event,
  input  logic        acquisition_start_event,
  input  logic        acquisition_complete_event,
  output logic [31:0] phase_sample_to_mapping_prepare_us,
  output logic [31:0] mapping_prepare_to_ready_us,
  output logic [31:0] atomic_mapping_commit_us,
  output logic [31:0] application_service_gap_us,
  output logic [31:0] path_epoch_visibility_us,
  output logic [31:0] reacquisition_time_us
);
  logic [63:0] cycle_count;
  logic [63:0] phase_sample_cycle;
  logic [63:0] prepare_cycle;
  logic [63:0] commit_request_cycle;
  logic [63:0] service_interrupt_cycle;
  logic [63:0] commit_accept_cycle;
  logic [63:0] acquisition_start_cycle;

  function automatic logic [31:0] cycles_to_us(input logic [63:0] cycles);
    cycles_to_us = (cycles + CYCLES_PER_US - 1) / CYCLES_PER_US;
  endfunction

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      cycle_count <= '0;
      phase_sample_cycle <= '0;
      prepare_cycle <= '0;
      commit_request_cycle <= '0;
      service_interrupt_cycle <= '0;
      commit_accept_cycle <= '0;
      acquisition_start_cycle <= '0;
      phase_sample_to_mapping_prepare_us <= '0;
      mapping_prepare_to_ready_us <= '0;
      atomic_mapping_commit_us <= '0;
      application_service_gap_us <= '0;
      path_epoch_visibility_us <= '0;
      reacquisition_time_us <= '0;
    end else begin
      cycle_count <= cycle_count + 1'b1;
      if (phase_sample_event)
        phase_sample_cycle <= cycle_count;
      if (mapping_prepare_event) begin
        prepare_cycle <= cycle_count;
        phase_sample_to_mapping_prepare_us <= cycles_to_us(cycle_count - phase_sample_cycle);
      end
      if (mapping_ready_event)
        mapping_prepare_to_ready_us <= cycles_to_us(cycle_count - prepare_cycle);
      if (commit_request_event)
        commit_request_cycle <= cycle_count;
      if (commit_accept_event) begin
        commit_accept_cycle <= cycle_count;
        atomic_mapping_commit_us <= cycles_to_us(cycle_count - commit_request_cycle);
      end
      if (service_interrupt_event)
        service_interrupt_cycle <= cycle_count;
      if (service_resume_event)
        application_service_gap_us <= cycles_to_us(cycle_count - service_interrupt_cycle);
      if (epoch_visible_event)
        path_epoch_visibility_us <= cycles_to_us(cycle_count - commit_accept_cycle);
      if (acquisition_start_event)
        acquisition_start_cycle <= cycle_count;
      if (acquisition_complete_event)
        reacquisition_time_us <= cycles_to_us(cycle_count - acquisition_start_cycle);
    end
  end
endmodule
