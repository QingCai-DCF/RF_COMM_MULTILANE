set repo_root [file normalize [file join [file dirname [info script]] ..]]
set out_dir [file join $repo_root reports pin_static_diag]
file mkdir $out_dir

create_project -force pin_static_diag $out_dir -part xc7z010clg400-1
set_param general.maxThreads 16

add_files -norecurse [file join $repo_root tools pin_static_diag_top.v]
add_files -fileset constrs_1 -norecurse [file join $repo_root tools pin_static_diag.xdc]
set_property top pin_static_diag_top [current_fileset]
update_compile_order -fileset sources_1

synth_design -top pin_static_diag_top -part xc7z010clg400-1
opt_design
place_design
route_design
write_bitstream -force [file join $out_dir pin_static_diag.bit]

puts "PIN_STATIC_DIAG_BIT=[file join $out_dir pin_static_diag.bit]"
