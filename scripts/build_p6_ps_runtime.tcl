set root_dir [file normalize [lindex $argv 0]]
set xsa_file [file normalize [lindex $argv 1]]
set workspace [file normalize "$root_dir/build/p6_ps_vitis_workspace"]
file mkdir $workspace
setws $workspace

catch {app remove p6_runtime}
catch {platform remove p6_platform}
platform create -name p6_platform -hw $xsa_file -proc ps7_cortexa9_0 -os standalone
platform generate
app create -name p6_runtime -platform p6_platform -domain standalone_domain -template {Empty Application(C)}

set src_dir [file normalize "$workspace/p6_runtime/src"]
file mkdir $src_dir
set linker_file "$src_dir/lscript.ld"
set linker_handle [open $linker_file r]
set linker_text [read $linker_handle]
close $linker_handle
set linker_text [string map [list "> ps7_ddr_0" "> ps7_ram_0"] $linker_text]
set linker_handle [open $linker_file w]
puts -nonewline $linker_handle $linker_text
close $linker_handle
foreach source_name [list p6_runtime_mailbox.c ir_driver.c ir_driver.h ir_regs.h] {
  file copy -force "$root_dir/software/ps_driver/$source_name" "$src_dir/$source_name"
}
app build -name p6_runtime

set elf_file [file normalize "$workspace/p6_runtime/Debug/p6_runtime.elf"]
if {![file exists $elf_file]} { error "P6 runtime ELF missing after build: $elf_file" }
puts "P6_PS_RUNTIME_BUILD=PASS"
puts "P6_PS_RUNTIME_ELF=$elf_file"
