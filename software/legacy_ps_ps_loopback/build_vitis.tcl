set script_dir [file normalize [file dirname [info script]]]
set repo_root  [file normalize [file join $script_dir ../..]]
set ws_dir     [file normalize [file join $repo_root software _vitis_ws_ps_ps_loopback]]
set src_dir    [file normalize [file join $script_dir src]]
set shared_dir [file normalize [file join $repo_root software ps_lwip_bridge src]]
set xsa_path   [file normalize [file join $repo_root TFDU_VFIR_Client_Array design_shiboqi_wrapper.xsa]]
set app_name   rf_comm_ps_ps_loopback

puts "RF_COMM PS-PS loopback Vitis build"
puts "  workspace: $ws_dir"
puts "  source:    $src_dir"
puts "  shared:    $shared_dir"
puts "  xsa:       $xsa_path"

if {![file exists $xsa_path]} {
    error "Missing XSA: $xsa_path"
}
if {![file isdirectory $src_dir]} {
    error "Missing source directory: $src_dir"
}
if {![file isdirectory $shared_dir]} {
    error "Missing shared source directory: $shared_dir"
}

set expected_prefix [file normalize [file join $repo_root software]]
if {[file exists $ws_dir]} {
    if {[string first $expected_prefix $ws_dir] != 0} {
        error "Refusing to delete workspace outside software directory: $ws_dir"
    }
    file delete -force $ws_dir
}
file mkdir $ws_dir

set staged_dir [file join $ws_dir _src_import]
file mkdir $staged_dir

foreach f [list main.c] {
    set src [file join $src_dir $f]
    if {![file exists $src]} {
        error "Missing experiment source: $src"
    }
    file copy -force $src [file join $staged_dir $f]
}

foreach f [list ir_hw.c ir_hw.h rf_protocol.h] {
    set src [file join $shared_dir $f]
    if {![file exists $src]} {
        error "Missing shared source: $src"
    }
    file copy -force $src [file join $staged_dir $f]
}

setws $ws_dir

app create \
    -name $app_name \
    -hw $xsa_path \
    -proc ps7_cortexa9_0 \
    -os standalone \
    -lang c \
    -template "Empty Application"

importsources -name $app_name -path $staged_dir

set compiler_flags [list]
if {[info exists ::env(PSPS_PAYLOAD_BYTES)] && $::env(PSPS_PAYLOAD_BYTES) ne ""} {
    lappend compiler_flags "-DPSPS_PAYLOAD_BYTES=$::env(PSPS_PAYLOAD_BYTES)u"
}
if {[info exists ::env(PSPS_TX_ONLY)] && $::env(PSPS_TX_ONLY) ne ""} {
    lappend compiler_flags "-DPSPS_TX_ONLY=$::env(PSPS_TX_ONLY)u"
}
if {[info exists ::env(PSPS_TDM_BIDIR)] && $::env(PSPS_TDM_BIDIR) ne ""} {
    lappend compiler_flags "-DPSPS_TDM_BIDIR=$::env(PSPS_TDM_BIDIR)u"
}
if {[info exists ::env(PSPS_RX_ONLY)] && $::env(PSPS_RX_ONLY) ne ""} {
    lappend compiler_flags "-DPSPS_RX_ONLY=$::env(PSPS_RX_ONLY)u"
}
if {[info exists ::env(PSPS_A2B_RX_SUMMARY)] && $::env(PSPS_A2B_RX_SUMMARY) ne ""} {
    lappend compiler_flags "-DPSPS_A2B_RX_SUMMARY=$::env(PSPS_A2B_RX_SUMMARY)u"
}
if {[info exists ::env(PSPS_UART_OPERATOR)] && $::env(PSPS_UART_OPERATOR) ne ""} {
    lappend compiler_flags "-DPSPS_UART_OPERATOR=$::env(PSPS_UART_OPERATOR)u"
}
if {[info exists ::env(PSPS_INTER_PACKET_US)] && $::env(PSPS_INTER_PACKET_US) ne ""} {
    lappend compiler_flags "-DPSPS_INTER_PACKET_US=$::env(PSPS_INTER_PACKET_US)u"
}
if {[info exists ::env(PSPS_IR_ROUNDTRIP_ECHO_MAX_RETRY)] && $::env(PSPS_IR_ROUNDTRIP_ECHO_MAX_RETRY) ne ""} {
    lappend compiler_flags "-DPSPS_IR_ROUNDTRIP_ECHO_MAX_RETRY=$::env(PSPS_IR_ROUNDTRIP_ECHO_MAX_RETRY)u"
}
if {[info exists ::env(PSPS_IR_ROUNDTRIP_RETRY_GAP_US)] && $::env(PSPS_IR_ROUNDTRIP_RETRY_GAP_US) ne ""} {
    lappend compiler_flags "-DPSPS_IR_ROUNDTRIP_RETRY_GAP_US=$::env(PSPS_IR_ROUNDTRIP_RETRY_GAP_US)u"
}
if {[info exists ::env(PSPS_STAGE_SECONDS)] && $::env(PSPS_STAGE_SECONDS) ne ""} {
    lappend compiler_flags "-DPSPS_STAGE_SECONDS=$::env(PSPS_STAGE_SECONDS)u"
}
if {[info exists ::env(PSPS_STATS_INTERVAL_US)] && $::env(PSPS_STATS_INTERVAL_US) ne ""} {
    lappend compiler_flags "-DPSPS_STATS_INTERVAL_US=$::env(PSPS_STATS_INTERVAL_US)u"
}
if {[info exists ::env(PSPS_RUN_ONCE)] && $::env(PSPS_RUN_ONCE) ne ""} {
    lappend compiler_flags "-DPSPS_RUN_ONCE=$::env(PSPS_RUN_ONCE)u"
}
if {[info exists ::env(PSPS_WARMUP_STAGES)] && $::env(PSPS_WARMUP_STAGES) ne ""} {
    lappend compiler_flags "-DPSPS_WARMUP_STAGES=$::env(PSPS_WARMUP_STAGES)u"
}
if {[info exists ::env(PSPS_MAX_OUTSTANDING)] && $::env(PSPS_MAX_OUTSTANDING) ne ""} {
    lappend compiler_flags "-DPSPS_MAX_OUTSTANDING=$::env(PSPS_MAX_OUTSTANDING)u"
}
if {[info exists ::env(PSPS_WINDOW_START_GAP_US)] && $::env(PSPS_WINDOW_START_GAP_US) ne ""} {
    lappend compiler_flags "-DPSPS_WINDOW_START_GAP_US=$::env(PSPS_WINDOW_START_GAP_US)u"
}
if {[info exists ::env(PSPS_2LANE_ONLY)] && $::env(PSPS_2LANE_ONLY) ne ""} {
    lappend compiler_flags "-DPSPS_2LANE_ONLY=$::env(PSPS_2LANE_ONLY)u"
}
if {[info exists ::env(PSPS_STAGE_LANE_MASK)] && $::env(PSPS_STAGE_LANE_MASK) ne ""} {
    lappend compiler_flags "-DPSPS_STAGE_LANE_MASK=$::env(PSPS_STAGE_LANE_MASK)u"
}
if {[info exists ::env(PSPS_STAGE_SESSION_ID)] && $::env(PSPS_STAGE_SESSION_ID) ne ""} {
    lappend compiler_flags "-DPSPS_STAGE_SESSION_ID=$::env(PSPS_STAGE_SESSION_ID)u"
}
if {[info exists ::env(PSPS_PAYLOAD_LANE_MASK)] && $::env(PSPS_PAYLOAD_LANE_MASK) ne ""} {
    lappend compiler_flags "-DPSPS_PAYLOAD_LANE_MASK=$::env(PSPS_PAYLOAD_LANE_MASK)u"
}
if {[info exists ::env(PSPS_RX_LANE_MASK)] && $::env(PSPS_RX_LANE_MASK) ne ""} {
    lappend compiler_flags "-DPSPS_RX_LANE_MASK=$::env(PSPS_RX_LANE_MASK)u"
}
if {[info exists ::env(PSPS_POLL_SLEEP_US)] && $::env(PSPS_POLL_SLEEP_US) ne ""} {
    lappend compiler_flags "-DPSPS_POLL_SLEEP_US=$::env(PSPS_POLL_SLEEP_US)u"
}
if {[info exists ::env(IR_TX_POLL_US)] && $::env(IR_TX_POLL_US) ne ""} {
    lappend compiler_flags "-DIR_TX_POLL_US=$::env(IR_TX_POLL_US)u"
}
if {[info exists ::env(IR_HW_RX_TRANSFER_BYTES)] && $::env(IR_HW_RX_TRANSFER_BYTES) ne ""} {
    lappend compiler_flags "-DIR_HW_RX_TRANSFER_BYTES=$::env(IR_HW_RX_TRANSFER_BYTES)u"
}
if {[info exists ::env(IR_HW_MAX_PACKET_BYTES)] && $::env(IR_HW_MAX_PACKET_BYTES) ne ""} {
    lappend compiler_flags "-DIR_HW_MAX_PACKET_BYTES=$::env(IR_HW_MAX_PACKET_BYTES)u"
}
if {[llength $compiler_flags] > 0} {
    set compiler_misc [join $compiler_flags " "]
    puts "Using compile flags: $compiler_misc"
    configapp -app $app_name -add compiler-misc $compiler_misc
}

app build -name $app_name

set elf_path [file join $ws_dir $app_name Debug "$app_name.elf"]
if {![file exists $elf_path]} {
    puts "XSCT app build did not produce the ELF; running generated makefile directly."
    set debug_dir [file join $ws_dir $app_name Debug]
    if {![file isdirectory $debug_dir]} {
        error "Missing generated Debug build directory: $debug_dir"
    }
    set old_pwd [pwd]
    cd $debug_dir
    exec make -j12 all >@ stdout 2>@ stderr
    cd $old_pwd
}
if {![file exists $elf_path]} {
    error "Build finished without expected ELF: $elf_path"
}

puts "Built ELF: $elf_path"
