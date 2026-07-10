set root_dir [file normalize [lindex $argv 0]]
set out_dir [file normalize "$root_dir/evidence/generated/vivado/p6_ip_inspect"]
file mkdir $out_dir
create_project p6_ip_inspect $out_dir/project -part xc7z010clg400-1 -force
create_ip -name jtag_axi -vendor xilinx.com -library ip -module_name p6_jtag_axi_master
set ip [get_ips p6_jtag_axi_master]
set_property -dict [list CONFIG.PROTOCOL {2} CONFIG.M_AXI_ADDR_WIDTH {32} CONFIG.M_AXI_DATA_WIDTH {32}] $ip
set f [open "$out_dir/jtag_axi_properties.txt" w]
foreach prop [lsort -dictionary [list_property $ip]] {
  if {[string match "CONFIG.*" $prop]} {
    puts $f "$prop=[get_property $prop $ip]"
  }
}
close $f
generate_target instantiation_template $ip
generate_target all $ip
puts "P6_JTAG_AXI_IP_INSPECT_PASS=1"
puts "P6_JTAG_AXI_IP=$ip"
puts "P6_JTAG_AXI_PROPERTIES=$out_dir/jtag_axi_properties.txt"
