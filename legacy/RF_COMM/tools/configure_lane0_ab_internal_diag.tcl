# Configure the current block design for a lane0 A/B internal diagnostic loop.
#
# This keeps the external TFDU lane0 ports present so the active XDC remains
# valid, but the receive inputs used by the protocol are driven internally:
#   A TX -> invert -> B RX
#   B TX -> invert -> A RX
#
# TFDU RXD is active-low relative to the FPGA TX drive in our PHY model, so the
# internal diagnostic route uses NOT gates to match the optical board behavior.

set script_dir [file dirname [file normalize [info script]]]
set repo_root [file normalize [file join $script_dir ..]]
set proj_path [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set bd_name design_shiboqi
set bd_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.srcs sources_1 bd $bd_name ${bd_name}.bd]

if {[llength [get_projects -quiet]] == 0} {
    open_project $proj_path
}

open_bd_design $bd_file
current_bd_design $bd_name

proc delete_if_exists {kind name} {
    set obj {}
    if {$kind eq "cell"} {
        set obj [get_bd_cells -quiet $name]
    } elseif {$kind eq "port"} {
        set obj [get_bd_ports -quiet $name]
    } elseif {$kind eq "net"} {
        set obj [get_bd_nets -quiet $name]
    }
    if {[llength $obj] > 0} {
        delete_bd_objs $obj
    }
}

proc set_ir_vector_port {cell_name pin_name width} {
    set pin [get_bd_pins -quiet ${cell_name}/${pin_name}]
    if {[llength $pin] == 0} {
        return
    }
    set max_idx [expr {$width - 1}]
    catch {set_property LEFT $max_idx $pin}
    catch {set_property RIGHT 0 $pin}
}

proc make_port {name dir from to} {
    delete_if_exists port $name
    if {$from eq "" || $to eq ""} {
        return [create_bd_port -dir $dir $name]
    }
    return [create_bd_port -dir $dir -from $from -to $to $name]
}

proc connect_port {cell_pin port_name dir {from ""} {to ""}} {
    set p [make_port $port_name $dir $from $to]
    connect_bd_net [get_bd_pins $cell_pin] $p
    return $p
}

# Remove stale diagnostic/loopback objects before recreating the topology.
foreach net_name {
    a_rx_internal_net
    b_rx_internal_net
    a_tx_internal_net
    b_tx_internal_net
} {
    delete_if_exists net $net_name
}
foreach cell_name {
    not_a_to_b
    not_b_to_a
    ir_loopback_b0
    system_ila_0
} {
    delete_if_exists cell $cell_name
}
foreach port_name {
    ir_rx_in_0
    ir_tx_out_0
    ir_sd_0
    ir_mode_out_0
    loop_rx_b0
    loop_tx_b0
    loop_sd_b0
    loop_mode_b0
} {
    delete_if_exists port $port_name
}

# Keep the active design to a single lane for this bring-up step.
set_property -dict [list CONFIG.LANE_COUNT {1}] [get_bd_cells ir_array_top_axi_0]
set_ir_vector_port ir_array_top_axi_0 ir_rx_in 1
set_ir_vector_port ir_array_top_axi_0 ir_tx_out 1
set_ir_vector_port ir_array_top_axi_0 ir_sd 1
set_ir_vector_port ir_array_top_axi_0 ir_mode_out 1

# External A-side ports. RX is intentionally left dangling for this diagnostic
# bitstream while the core receives the internally routed B TX.
make_port ir_rx_in_0 I 0 0
connect_port ir_array_top_axi_0/ir_tx_out ir_tx_out_0 O 0 0
connect_port ir_array_top_axi_0/ir_sd ir_sd_0 O 0 0
connect_port ir_array_top_axi_0/ir_mode_out ir_mode_out_0 O 0 0

# B-side module reference and external ports. B RX is also left dangling.
set loopback_src [file join $repo_root IPs ip_ir_array src ir_loopback_b0_bd.v]
add_files -norecurse -quiet $loopback_src
create_bd_cell -type module -reference ir_loopback_b0_bd ir_loopback_b0
connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] [get_bd_pins ir_loopback_b0/clk_phy]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins ir_loopback_b0/rst_n]
make_port loop_rx_b0 I "" ""
connect_port ir_loopback_b0/ir_tx_out loop_tx_b0 O "" ""
connect_port ir_loopback_b0/ir_sd loop_sd_b0 O "" ""
connect_port ir_loopback_b0/ir_mode_out loop_mode_b0 O "" ""

# Internal inverted digital route that emulates the TFDU active-low RXD signal.
create_bd_cell -type ip -vlnv xilinx.com:ip:util_vector_logic:2.0 not_a_to_b
set_property -dict [list CONFIG.C_OPERATION {not} CONFIG.C_SIZE {1}] [get_bd_cells not_a_to_b]
create_bd_cell -type ip -vlnv xilinx.com:ip:util_vector_logic:2.0 not_b_to_a
set_property -dict [list CONFIG.C_OPERATION {not} CONFIG.C_SIZE {1}] [get_bd_cells not_b_to_a]

connect_bd_net [get_bd_pins ir_array_top_axi_0/ir_tx_out] [get_bd_pins not_a_to_b/Op1]
connect_bd_net [get_bd_pins not_a_to_b/Res] [get_bd_pins ir_loopback_b0/ir_rx_in]

connect_bd_net [get_bd_pins ir_loopback_b0/ir_tx_out] [get_bd_pins not_b_to_a/Op1]
connect_bd_net [get_bd_pins not_b_to_a/Res] [get_bd_pins ir_array_top_axi_0/ir_rx_in]

validate_bd_design
save_bd_design
generate_target all [get_files $bd_file]
catch {
    export_ip_user_files -of_objects [get_files $bd_file] -no_script -sync -force -quiet
}

close_project
puts "Configured lane0 A/B internal diagnostic loopback without modifying the hard target constraint file."
