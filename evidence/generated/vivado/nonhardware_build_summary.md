# Vivado Non-Hardware Build Summary

M5_VIVADO_NONHARDWARE_BUILD=PASS
NO_HARDWARE_ACTIONS_EXECUTED=1
VIVADO_BATCH_TCL=scripts/vivado_nonhardware_build.tcl
VIVADO_REPORT_DIR=evidence/generated/vivado
VIVADO_PATH_ON_PATH=0
XILINX_VIVADO_2023_1_BIN=D:\Xilinx\Vivado\2023.1\bin
XILINX_VIVADO_2023_1_BAT_AVAILABLE=1
VIVADO_EXECUTABLE=D:\Xilinx\Vivado\2023.1\bin\vivado.bat
VIVADO_EXIT_CODE=0

## Log Tail

```text
rtical Routing Utilization    = 0 %
  Global Horizontal Routing Utilization  = 0 %
  Routable Net Status*
  *Does not include unroutable nets such as driverless and loadless.
  Run report_route_status for detailed report.
  Number of Failed Nets               = 0
    (Failed Nets is the sum of unrouted and partially routed nets)
  Number of Unrouted Nets             = 0
  Number of Partially Routed Nets     = 0
  Number of Node Overlaps             = 0


--GLOBAL Congestion:
Utilization threshold used for congestion level computation: 0.85
Congestion Report
North Dir 1x1 Area, Max Cong = 0%, No Congested Regions.
South Dir 1x1 Area, Max Cong = 0%, No Congested Regions.
East Dir 1x1 Area, Max Cong = 0%, No Congested Regions.
West Dir 1x1 Area, Max Cong = 0%, No Congested Regions.

------------------------------
Reporting congestion hotspots
------------------------------
Direction: North
----------------
Congested clusters found at Level 0
Effective congestion level: 0 Aspect Ratio: 1 Sparse Ratio: 0
Direction: South
----------------
Congested clusters found at Level 0
Effective congestion level: 0 Aspect Ratio: 1 Sparse Ratio: 0
Direction: East
----------------
Congested clusters found at Level 0
Effective congestion level: 0 Aspect Ratio: 1 Sparse Ratio: 0
Direction: West
----------------
Congested clusters found at Level 0
Effective congestion level: 0 Aspect Ratio: 1 Sparse Ratio: 0

Phase 7 Route finalize | Checksum: 1713a4056

Time (s): cpu = 00:00:07 ; elapsed = 00:00:06 . Memory (MB): peak = 2898.246 ; gain = 0.000

Phase 8 Verifying routed nets

 Verification completed successfully
Phase 8 Verifying routed nets | Checksum: 1713a4056

Time (s): cpu = 00:00:07 ; elapsed = 00:00:06 . Memory (MB): peak = 2898.246 ; gain = 0.000

Phase 9 Depositing Routes
Phase 9 Depositing Routes | Checksum: 1713a4056

Time (s): cpu = 00:00:07 ; elapsed = 00:00:06 . Memory (MB): peak = 2898.246 ; gain = 0.000
INFO: [Route 35-16] Router Completed Successfully

Phase 10 Post-Route Event Processing
Phase 10 Post-Route Event Processing | Checksum: 1a82bed7b

Time (s): cpu = 00:00:07 ; elapsed = 00:00:06 . Memory (MB): peak = 2898.246 ; gain = 0.000

Time (s): cpu = 00:00:07 ; elapsed = 00:00:06 . Memory (MB): peak = 2898.246 ; gain = 0.000

Routing Is Done.
INFO: [Common 17-83] Releasing license: Implementation
8 Infos, 0 Warnings, 0 Critical Warnings and 0 Errors encountered.
route_design completed successfully
route_design: Time (s): cpu = 00:00:07 ; elapsed = 00:00:06 . Memory (MB): peak = 2898.246 ; gain = 0.000
# write_checkpoint -force "$out_dir/post_route.dcp"
INFO: [Timing 38-480] Writing timing data to binary archive.
Writing XDEF routing.
Writing XDEF routing logical nets.
Writing XDEF routing special nets.
Write XDEF Complete: Time (s): cpu = 00:00:00 ; elapsed = 00:00:00.026 . Memory (MB): peak = 2898.246 ; gain = 0.000
INFO: [Common 17-1381] The checkpoint 'C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/vivado/post_route.dcp' has been generated.
# report_drc -file "$out_dir/post_route_drc.rpt"
Command: report_drc -file C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/vivado/post_route_drc.rpt
INFO: [IP_Flow 19-1839] IP Catalog is up to date.
INFO: [DRC 23-27] Running DRC with 2 threads
INFO: [Vivado_Tcl 2-168] The results of DRC are in file C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/vivado/post_route_drc.rpt.
report_drc completed successfully
# report_timing_summary -file "$out_dir/post_route_timing_summary.rpt"
INFO: [Timing 38-91] UpdateTimingParams: Speed grade: -1, Delay Type: min_max.
INFO: [Timing 38-191] Multithreading enabled for timing update using a maximum of 2 CPUs
# report_utilization -file "$out_dir/post_route_utilization.rpt"
# set log_file [open "$out_dir/nonhardware_build_markers.txt" "a"]
# puts $log_file "VIVADO_NONHARDWARE_BUILD_DONE=1"
# puts $log_file "VIVADO_REPORT_DIR=$out_dir"
# close $log_file
INFO: [Common 17-206] Exiting Vivado at Wed Jul  8 21:40:57 2026...
```
