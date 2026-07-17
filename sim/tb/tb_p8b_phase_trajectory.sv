`timescale 1ns/1ps

module tb_p8b_phase_trajectory;
  import ir_path_mapping_pkg::*;
  logic clk = 0;
  logic rst_n = 0;
  always #5 clk = ~clk;

  logic phase_valid;
  logic speed_valid;
  logic [9:0] speed_abs_rpm;
  logic direction_valid;
  logic [1:0] direction;
  logic [15:0] phase_data_age_us;
  logic [31:0] phase_uncertainty_mdeg;
  logic [15:0] prepare_latency_us;
  logic [15:0] commit_latency_us;
  logic [15:0] max_phase_data_age_us;
  logic [31:0] uncertainty_budget_mdeg;
  logic encoder_fault;
  logic mapping_readback_match;
  logic epoch_match;
  logic mapping_fresh;
  logic [31:0] phase_age_motion_mdeg;
  logic [31:0] prepare_motion_mdeg;
  logic [31:0] commit_motion_mdeg;
  logic [31:0] total_effective_phase_uncertainty_mdeg;
  logic phase_contract_valid;
  logic reversal_detected;
  logic acquisition;
  logic tx_admission_allowed;

  logic phase_sample_event;
  logic mapping_prepare_event;
  logic mapping_ready_event;
  logic commit_request_event;
  logic commit_accept_event;
  logic service_interrupt_event;
  logic service_resume_event;
  logic epoch_visible_event;
  logic acquisition_start_event;
  logic acquisition_complete_event;
  logic [31:0] phase_sample_to_mapping_prepare_us;
  logic [31:0] mapping_prepare_to_ready_us;
  logic [31:0] atomic_mapping_commit_us;
  logic [31:0] application_service_gap_us;
  logic [31:0] path_epoch_visibility_us;
  logic [31:0] reacquisition_time_us;

  integer seed;
  integer seed_index;
  integer step;
  integer random_value;
  integer randomized_samples;

  ir_phase_validity_guard u_guard (
    .clk(clk), .rst_n(rst_n), .phase_valid(phase_valid), .speed_valid(speed_valid),
    .speed_abs_rpm(speed_abs_rpm), .direction_valid(direction_valid), .direction(direction),
    .phase_data_age_us(phase_data_age_us), .phase_uncertainty_mdeg(phase_uncertainty_mdeg),
    .prepare_latency_us(prepare_latency_us), .commit_latency_us(commit_latency_us),
    .max_phase_data_age_us(max_phase_data_age_us), .uncertainty_budget_mdeg(uncertainty_budget_mdeg),
    .encoder_fault(encoder_fault), .mapping_readback_match(mapping_readback_match),
    .epoch_match(epoch_match), .mapping_fresh(mapping_fresh),
    .phase_age_motion_mdeg(phase_age_motion_mdeg), .prepare_motion_mdeg(prepare_motion_mdeg),
    .commit_motion_mdeg(commit_motion_mdeg),
    .total_effective_phase_uncertainty_mdeg(total_effective_phase_uncertainty_mdeg),
    .phase_contract_valid(phase_contract_valid), .reversal_detected(reversal_detected),
    .acquisition(acquisition), .tx_admission_allowed(tx_admission_allowed)
  );

  ir_handover_metrics #(.CYCLES_PER_US(1)) u_metrics (
    .clk(clk), .rst_n(rst_n), .phase_sample_event(phase_sample_event),
    .mapping_prepare_event(mapping_prepare_event), .mapping_ready_event(mapping_ready_event),
    .commit_request_event(commit_request_event), .commit_accept_event(commit_accept_event),
    .service_interrupt_event(service_interrupt_event), .service_resume_event(service_resume_event),
    .epoch_visible_event(epoch_visible_event), .acquisition_start_event(acquisition_start_event),
    .acquisition_complete_event(acquisition_complete_event),
    .phase_sample_to_mapping_prepare_us(phase_sample_to_mapping_prepare_us),
    .mapping_prepare_to_ready_us(mapping_prepare_to_ready_us),
    .atomic_mapping_commit_us(atomic_mapping_commit_us),
    .application_service_gap_us(application_service_gap_us),
    .path_epoch_visibility_us(path_epoch_visibility_us), .reacquisition_time_us(reacquisition_time_us)
  );

  task automatic check(input logic condition, input string message);
    if (!condition) begin
      $display("P8B_ASSERT_FAIL=%s", message);
      $fatal(1);
    end
  endtask

  task automatic pulse_event(ref logic signal);
    begin
      @(negedge clk); signal = 1;
      @(posedge clk); #1;
      @(negedge clk); signal = 0;
    end
  endtask

  task automatic wait_cycles(input integer count);
    repeat (count) @(posedge clk);
  endtask

  initial begin
    phase_valid = 1;
    speed_valid = 1;
    speed_abs_rpm = 600;
    direction_valid = 1;
    direction = DIRECTION_FORWARD;
    phase_data_age_us = 50;
    phase_uncertainty_mdeg = 100;
    prepare_latency_us = 100;
    commit_latency_us = 10;
    max_phase_data_age_us = 100;
    uncertainty_budget_mdeg = 1000;
    encoder_fault = 0;
    mapping_readback_match = 1;
    epoch_match = 1;
    mapping_fresh = 1;
    phase_sample_event = 0;
    mapping_prepare_event = 0;
    mapping_ready_event = 0;
    commit_request_event = 0;
    commit_accept_event = 0;
    service_interrupt_event = 0;
    service_resume_event = 0;
    epoch_visible_event = 0;
    acquisition_start_event = 0;
    acquisition_complete_event = 0;
    randomized_samples = 0;

    repeat (3) @(posedge clk);
    rst_n = 1;
    @(posedge clk); #1;
    check(phase_age_motion_mdeg == 180, "50 us age must consume 0.18 deg at 600 rpm bound");
    check(prepare_motion_mdeg == 360, "100 us prepare must consume 0.36 deg");
    check(commit_motion_mdeg == 36, "10 us commit must consume 0.036 deg");
    check(total_effective_phase_uncertainty_mdeg == 676, "uncertainty terms not kept separate/summed");
    check(tx_admission_allowed, "valid fresh forward phase did not lock");

    @(negedge clk); phase_valid = 0;
    @(posedge clk); #1;
    check(!tx_admission_allowed && acquisition, "invalid phase did not enter acquisition");
    @(negedge clk); phase_valid = 1; mapping_fresh = 1;
    @(posedge clk); #1;
    check(tx_admission_allowed, "phase recovery did not reacquire with fresh mapping");

    @(negedge clk); direction = DIRECTION_REVERSE;
    #1;
    check(reversal_detected && !tx_admission_allowed, "reversal reused old candidate");
    @(posedge clk); #1;
    check(acquisition, "reversal did not clear lock");
    @(negedge clk); mapping_fresh = 0;
    @(posedge clk); #1;
    check(!tx_admission_allowed, "stale reversal mapping admitted TX");
    @(negedge clk); mapping_fresh = 1;
    @(posedge clk); #1;
    check(tx_admission_allowed, "fresh post-reversal mapping did not reacquire");

    @(negedge clk); phase_data_age_us = 101;
    @(posedge clk); #1;
    check(!tx_admission_allowed && acquisition, "stale phase age did not fail closed");
    @(negedge clk); phase_data_age_us = 0; phase_uncertainty_mdeg = 2000;
    @(posedge clk); #1;
    check(!tx_admission_allowed, "over-budget uncertainty did not fail closed");
    @(negedge clk); phase_uncertainty_mdeg = 100; encoder_fault = 1;
    @(posedge clk); #1;
    check(!tx_admission_allowed, "encoder fault did not fail closed");
    @(negedge clk); encoder_fault = 0; speed_abs_rpm = 0; direction = DIRECTION_STOPPED;
    @(posedge clk); #1;
    check(tx_admission_allowed, "stationary phase contract rejected");
    repeat (5) @(posedge clk);
    check(tx_admission_allowed, "stationary phase drifted without input change");

    // Six metrics are captured independently; no aggregate handover number is used.
    pulse_event(phase_sample_event);
    wait_cycles(9);
    pulse_event(mapping_prepare_event);
    wait_cycles(19);
    pulse_event(mapping_ready_event);
    pulse_event(commit_request_event);
    wait_cycles(1);
    pulse_event(commit_accept_event);
    pulse_event(service_interrupt_event);
    wait_cycles(29);
    pulse_event(service_resume_event);
    wait_cycles(2);
    pulse_event(epoch_visible_event);
    pulse_event(acquisition_start_event);
    wait_cycles(99);
    pulse_event(acquisition_complete_event);
    #1;
    check(phase_sample_to_mapping_prepare_us <= 50, "sample-to-prepare target exceeded");
    check(mapping_prepare_to_ready_us <= 100, "prepare-to-ready target exceeded");
    check(atomic_mapping_commit_us <= 10, "atomic commit target exceeded");
    check(application_service_gap_us <= 100, "service gap target exceeded");
    check(path_epoch_visibility_us > 0, "epoch visibility metric missing");
    check(reacquisition_time_us > 0, "reacquisition metric missing");

    // Fixed seeds, bounded RPM, stop/restart, reverse and fault/age bursts.
    for (seed_index = 0; seed_index < 7; seed_index = seed_index + 1) begin
      case (seed_index)
        0: seed = 1; 1: seed = 7; 2: seed = 17; 3: seed = 31;
        4: seed = 127; 5: seed = 1024; default: seed = 20260717;
      endcase
      for (step = 0; step < 128; step = step + 1) begin
        random_value = $urandom(seed);
        @(negedge clk);
        speed_abs_rpm = random_value % 601;
        if ((step % 29) == 0) begin
          speed_abs_rpm = 0;
          direction = DIRECTION_STOPPED;
        end else if ((random_value & 1) == 0) begin
          direction = DIRECTION_FORWARD;
        end else begin
          direction = DIRECTION_REVERSE;
        end
        phase_valid = ((step % 43) != 0);
        encoder_fault = ((step % 97) == 0);
        phase_data_age_us = ((step % 61) == 0) ? 300 : (random_value % 61);
        mapping_fresh = !reversal_detected;
        @(posedge clk); #1;
        if (!phase_valid || encoder_fault || phase_data_age_us > max_phase_data_age_us)
          check(!tx_admission_allowed, "random invalid sample admitted TX");
        randomized_samples = randomized_samples + 1;
        @(negedge clk); mapping_fresh = 1;
      end
    end

    $display("P8B_METRIC_SAMPLE_TO_PREPARE_US=%0d", phase_sample_to_mapping_prepare_us);
    $display("P8B_METRIC_PREPARE_TO_READY_US=%0d", mapping_prepare_to_ready_us);
    $display("P8B_METRIC_ATOMIC_COMMIT_US=%0d", atomic_mapping_commit_us);
    $display("P8B_METRIC_SERVICE_GAP_US=%0d", application_service_gap_us);
    $display("P8B_METRIC_EPOCH_VISIBILITY_US=%0d", path_epoch_visibility_us);
    $display("P8B_METRIC_REACQUISITION_US=%0d", reacquisition_time_us);
    $display("P8B_RANDOMIZED_SAMPLES=%0d", randomized_samples);
    $display("P8B_HDL_PHASE_ACQUISITION_PASS=1");
    $display("P8B_HDL_TRAJECTORY_RANDOMIZED_PASS=1");
    $display("TB_P8B_PHASE_TRAJECTORY_PASS=1");
    $finish;
  end
endmodule
