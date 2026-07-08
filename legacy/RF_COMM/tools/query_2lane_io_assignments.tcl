set script_dir [file dirname [file normalize [info script]]]
set repo_dir [file dirname $script_dir]
set project_path [file join $repo_dir TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]

open_project $project_path

set impl_run [get_runs impl_1]
set dcp_path [file join $repo_dir TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs impl_1 design_shiboqi_wrapper_routed.dcp]
if {[file exists $dcp_path]} {
    open_checkpoint $dcp_path
} else {
    open_run impl_1
}

set ports {
    ir_mode_out_0[0]
    ir_rx_in_0[0]
    ir_sd_0[0]
    ir_tx_out_0[0]
    ir_mode_out_0[1]
    ir_rx_in_0[1]
    ir_sd_0[1]
    ir_tx_out_0[1]
    loop_mode_b0[0]
    loop_rx_b0[0]
    loop_sd_b0[0]
    loop_tx_b0[0]
    loop_mode_b0[1]
    loop_rx_b0[1]
    loop_sd_b0[1]
    loop_tx_b0[1]
}

puts "PORT,PACKAGE_PIN,IOSTANDARD,DIRECTION"
foreach port_name $ports {
    set p [get_ports -quiet $port_name]
    if {[llength $p] == 0} {
        puts "$port_name,<missing>,<missing>,<missing>"
        continue
    }
    puts [format "%s,%s,%s,%s" \
        $port_name \
        [get_property PACKAGE_PIN $p] \
        [get_property IOSTANDARD $p] \
        [get_property DIRECTION $p]]
}

close_project
