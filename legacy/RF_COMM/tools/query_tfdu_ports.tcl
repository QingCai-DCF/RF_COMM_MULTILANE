set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]

open_project $project_file
open_run impl_1

puts "TFDU_PORT_QUERY_START"
foreach pat {ir_rx_in* ir_tx_out* ir_sd* ir_mode_out*} {
  puts "PATTERN=$pat"
  foreach p [get_ports -quiet $pat] {
    set pin [get_property PACKAGE_PIN $p]
    set iostd [get_property IOSTANDARD $p]
    set loc [get_property LOC $p]
    puts "PORT=$p PACKAGE_PIN=$pin LOC=$loc IOSTANDARD=$iostd"
  }
}

puts "REGEXP_RX_BITS"
foreach p [get_ports -quiet -regexp {ir_rx_in_0\[.*\]}] {
  puts "RX_BIT=$p PACKAGE_PIN=[get_property PACKAGE_PIN $p] IOSTANDARD=[get_property IOSTANDARD $p]"
}

close_project
