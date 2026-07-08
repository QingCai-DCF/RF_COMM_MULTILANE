set repo_root [file normalize [file join [file dirname [info script]] ".."]]
set out_dir [file join $repo_root "shutdown_bitstream"]
file mkdir $out_dir

set_param general.maxThreads 16

set bit_file [file join $out_dir "tfdu_shutdown_8lane_candidate.bit"]
set dcp_file [file join $out_dir "tfdu_shutdown_8lane_candidate_routed.dcp"]
set util_rpt [file join $out_dir "tfdu_shutdown_8lane_candidate_utilization.rpt"]
set timing_rpt [file join $out_dir "tfdu_shutdown_8lane_candidate_timing_summary.rpt"]
set drc_rpt [file join $out_dir "tfdu_shutdown_8lane_candidate_drc.rpt"]
set io_rpt [file join $out_dir "tfdu_shutdown_8lane_candidate_io.rpt"]

read_verilog [file join $repo_root "tools" "tfdu_shutdown_8lane_candidate_top.v"]
read_xdc [file join $repo_root "tools" "tfdu_shutdown_8lane_candidate.xdc"]

synth_design -top tfdu_shutdown_8lane_candidate_top -part xc7z010clg400-1
report_utilization -file $util_rpt
opt_design
place_design
route_design
report_drc -file $drc_rpt
report_timing_summary -file $timing_rpt
report_io -file $io_rpt
write_checkpoint -force $dcp_file
write_bitstream -force $bit_file
puts "TFDU_SHUTDOWN_8LANE_CANDIDATE_BITSTREAM_READY $bit_file"
