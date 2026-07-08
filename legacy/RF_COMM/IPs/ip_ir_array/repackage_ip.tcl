# Repackage the custom IR array IP after RTL source edits.
#
# Run from the repository root or this IP directory:
#   & 'D:\Xilinx\Vivado\2023.1\bin\vivado.bat' -mode batch -source '.\IPs\ip_ir_array\repackage_ip.tcl'

set script_dir [file dirname [file normalize [info script]]]
set edit_project [file join $script_dir tmp_edit_project.xpr]
set component_xml [file join $script_dir component.xml]

if {![file exists $edit_project]} {
    error "Missing IP edit project: $edit_project"
}
if {![file exists $component_xml]} {
    error "Missing component.xml: $component_xml"
}

open_project $edit_project

set extra_rtl_files [list \
    [file join $script_dir src ir_array_top_axi.sv] \
    [file join $script_dir src ir_txonly_ack_axi.sv] \
    [file join $script_dir src ir_stream_array_top.sv] \
    [file join $script_dir src ir_stream_parallel_2lane_top.sv] \
    [file join $script_dir src ir_stream_array_top_axi.sv] \
]
foreach rtl_file $extra_rtl_files {
    if {![file exists $rtl_file]} {
        error "Missing RTL source for IP package: $rtl_file"
    }
    if {[llength [get_files -quiet $rtl_file]] == 0} {
        add_files -norecurse -fileset sources_1 $rtl_file
    }
}
update_compile_order -fileset sources_1

ipx::open_ipxact_file $component_xml
ipx::merge_project_changes files [ipx::current_core]
ipx::merge_project_changes ports [ipx::current_core]
ipx::merge_project_changes hdl_parameters [ipx::current_core]
set current_revision [get_property core_revision [ipx::current_core]]
set_property core_revision [expr {$current_revision + 1}] [ipx::current_core]
ipx::create_xgui_files [ipx::current_core]
ipx::update_checksums [ipx::current_core]
ipx::check_integrity [ipx::current_core]
ipx::save_core [ipx::current_core]

update_ip_catalog -rebuild -repo_path $script_dir

puts "Repackaged [get_property VLNV [ipx::current_core]] revision [get_property core_revision [ipx::current_core]]"
close_project
