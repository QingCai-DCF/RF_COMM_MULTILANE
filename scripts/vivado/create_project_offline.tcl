# Offline-only Vivado project creation script.
# This script creates or validates sources only. It does not connect to hardware.
set origin_dir [file normalize [file join [pwd]]]
puts "NO_HARDWARE_ACTIONS_EXECUTED: true"
puts "HARDWARE_ACCEPTANCE: PENDING_HW"
puts "TOP_MODULE=ir_top_new"
puts "ACTIVE_XDC=constraints/active/PORT1.generated.xdc"
create_project rf_comm_multilane_offline ./evidence/generated/vivado/project -part xc7z010clg400-1 -force
add_files [glob -nocomplain ./rtl/*.sv]
add_files -fileset constrs_1 ./constraints/active/PORT1.generated.xdc
set_property top ir_top_new [current_fileset]
puts "VIVADO_PROJECT_OFFLINE_CREATE=PASS"
