set script_dir [file normalize [file dirname [info script]]]
set repo_root  [file normalize [file join $script_dir ../..]]
set ws_dir     [file normalize [file join $repo_root software _vitis_ws]]
set src_dir    [file normalize [file join $script_dir src]]
set xsa_path   [file normalize [file join $repo_root TFDU_VFIR_Client_Array design_shiboqi_wrapper.xsa]]
set app_name   rf_comm_ps_bridge

puts "RF_COMM Vitis build"
puts "  workspace: $ws_dir"
puts "  source:    $src_dir"
puts "  xsa:       $xsa_path"

if {![file exists $xsa_path]} {
    error "Missing XSA: $xsa_path"
}
if {![file isdirectory $src_dir]} {
    error "Missing source directory: $src_dir"
}

set expected_prefix [file normalize [file join $repo_root software]]
if {[file exists $ws_dir]} {
    if {[string first $expected_prefix $ws_dir] != 0} {
        error "Refusing to delete workspace outside software directory: $ws_dir"
    }
    file delete -force $ws_dir
}
file mkdir $ws_dir

setws $ws_dir

app create \
    -name $app_name \
    -hw $xsa_path \
    -proc ps7_cortexa9_0 \
    -os standalone \
    -lang c \
    -template "lwIP Echo Server"

importsources -name $app_name -path $src_dir

set compiler_flags [list]
if {[info exists ::env(IR_HW_MAX_PACKET_BYTES)] && $::env(IR_HW_MAX_PACKET_BYTES) ne ""} {
    lappend compiler_flags "-DIR_HW_MAX_PACKET_BYTES=$::env(IR_HW_MAX_PACKET_BYTES)u"
}
if {[info exists ::env(IR_HW_RX_TRANSFER_BYTES)] && $::env(IR_HW_RX_TRANSFER_BYTES) ne ""} {
    lappend compiler_flags "-DIR_HW_RX_TRANSFER_BYTES=$::env(IR_HW_RX_TRANSFER_BYTES)u"
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
