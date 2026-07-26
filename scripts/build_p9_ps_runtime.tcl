set root_dir [file normalize [lindex $argv 0]]
set xsa_file [file normalize [lindex $argv 1]]
set workspace [file normalize "$root_dir/build/p9_ps_vitis_workspace"]
file mkdir $workspace
setws $workspace

catch {app remove p9_runtime}
catch {platform remove p9_platform}
platform create -name p9_platform -hw $xsa_file -proc ps7_cortexa9_0 -os standalone
platform generate
app create -name p9_runtime -platform p9_platform -domain standalone_domain -template {Empty Application(C)}

set src_dir [file normalize "$workspace/p9_runtime/src"]
file mkdir $src_dir
set linker_file "$src_dir/lscript.ld"
set linker_handle [open $linker_file r]
set linker_text [read $linker_handle]
close $linker_handle
set linker_text [string map [list "> ps7_ddr_0" "> ps7_ram_0"] $linker_text]
set linker_text [string map [list \
    "ps7_ram_0 : ORIGIN = 0x0, LENGTH = 0x30000" \
    "ps7_ram_0 : ORIGIN = 0x0, LENGTH = 0x20000"] $linker_text]
if {[string first "ps7_ram_0 : ORIGIN = 0x0, LENGTH = 0x20000" $linker_text] < 0} {
  error "P9 linker OCM hard boundary was not applied"
}
set linker_handle [open $linker_file w]
puts -nonewline $linker_handle $linker_text
close $linker_handle

foreach source_path [list \
    software/ps_driver/p9_runtime_main.c \
    software/ps_driver/p9_runtime_protocol.h \
    software/ps_driver/p9_crypto.c \
    software/ps_driver/p9_crypto.h \
    software/ps_driver/ir_regs.h] {
  file copy -force "$root_dir/$source_path" "$src_dir/[file tail $source_path]"
}

app build -name p9_runtime
set debug_dir [file normalize "$workspace/p9_runtime/Debug"]
set makefile "$debug_dir/Makefile"
set map_file [file normalize "$debug_dir/p9_runtime.map"]
set make_handle [open $makefile r]
set make_text [read $make_handle]
close $make_handle
set map_flag "-Wl,-Map=$map_file"
if {[string first $map_flag $make_text] < 0} {
  set make_text [string map [list \
      "-Wl,-build-id=none" \
      "-Wl,-build-id=none $map_flag"] $make_text]
  set make_handle [open $makefile w]
  puts -nonewline $make_handle $make_text
  close $make_handle
}
file delete -force "$debug_dir/p9_runtime.elf"
set make_output [exec make -C $debug_dir p9_runtime.elf 2>@1]
puts $make_output
set elf_file [file normalize "$debug_dir/p9_runtime.elf"]
if {![file exists $elf_file]} { error "P9 runtime ELF missing after build: $elf_file" }
if {![file exists $map_file]} { error "P9 runtime linker map missing after build: $map_file" }
puts "P9_PS_RUNTIME_BUILD=PASS"
puts "P9_PS_RUNTIME_ELF=$elf_file"
puts "P9_PS_RUNTIME_MAP=$map_file"
