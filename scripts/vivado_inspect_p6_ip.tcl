set root_dir [file normalize [lindex $argv 0]]
set out_dir [file normalize "$root_dir/evidence/generated/vivado/p6_ip_inspect"]
file mkdir $out_dir
create_project p6_ip_inspect $out_dir/project -part xc7z010clg400-1 -force
create_ip -name jtag_axi -vendor xilinx.com -library ip -module_name p6_jtag_axi_master
set ip [get_ips p6_jtag_axi_master]
set_property -dict [list \
  CONFIG.PROTOCOL {0} \
  CONFIG.M_AXI_ADDR_WIDTH {32} \
  CONFIG.M_AXI_DATA_WIDTH {32} \
  CONFIG.RD_TXN_QUEUE_LENGTH {16} \
  CONFIG.WR_TXN_QUEUE_LENGTH {16} \
] $ip
set f [open "$out_dir/jtag_axi_properties.txt" w]
foreach prop [lsort -dictionary [list_property $ip]] {
  if {[string match "CONFIG.*" $prop]} {
    puts $f "$prop=[get_property $prop $ip]"
  }
}
close $f
generate_target instantiation_template $ip
generate_target all $ip
create_ip -name axi_protocol_converter -vendor xilinx.com -library ip -module_name p6_axi_protocol_converter
set converter [get_ips p6_axi_protocol_converter]
set_property -dict [list \
  CONFIG.SI_PROTOCOL {AXI4} \
  CONFIG.MI_PROTOCOL {AXI4LITE} \
  CONFIG.DATA_WIDTH {32} \
  CONFIG.ADDR_WIDTH {32} \
  CONFIG.TRANSLATION_MODE {2} \
] $converter
set converter_props [open "$out_dir/axi_protocol_converter_properties.txt" w]
foreach prop [lsort -dictionary [list_property $converter]] {
  if {[string match "CONFIG.*" $prop]} {
    puts $converter_props "$prop=[get_property $prop $converter]"
  }
}
close $converter_props
generate_target instantiation_template $converter
generate_target all $converter
puts "P6_JTAG_AXI_IP_INSPECT_PASS=1"
puts "P6_JTAG_AXI_IP=$ip"
puts "P6_JTAG_AXI_PROPERTIES=$out_dir/jtag_axi_properties.txt"
puts "P6_AXI_PROTOCOL_CONVERTER_PROPERTIES=$out_dir/axi_protocol_converter_properties.txt"
