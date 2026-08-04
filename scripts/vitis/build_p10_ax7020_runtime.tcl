set root_dir [file normalize [lindex $argv 0]]
set role [string tolower [lindex $argv 1]]
set xsa_file [file normalize [lindex $argv 2]]
set campaign p10
if {[llength $argv] > 3} { set campaign [string tolower [lindex $argv 3]] }

if {$role eq "fixed"} {
  if {$campaign eq "p10_3f"} {
    set role_header "$root_dir/board_profiles/ax7020_fixed_4lane/p10_3f_runtime_role.h"
  } elseif {$campaign eq "p10_3"} {
    set role_header "$root_dir/board_profiles/ax7020_fixed_4lane/p10_3_runtime_role.h"
  } elseif {$campaign eq "p10_2"} {
    set role_header "$root_dir/board_profiles/ax7020_fixed_4lane/p10_runtime_role.h"
  } else {
    set role_header "$root_dir/board_profiles/ax7020_fixed_2lane/p10_runtime_role.h"
  }
} elseif {$role eq "rotating"} {
  if {$campaign eq "p10_3f"} {
    set role_header "$root_dir/board_profiles/ax7020_rotating_4lane/p10_3f_runtime_role.h"
  } elseif {$campaign eq "p10_3"} {
    set role_header "$root_dir/board_profiles/ax7020_rotating_4lane/p10_3_runtime_role.h"
  } elseif {$campaign eq "p10_2"} {
    set role_header "$root_dir/board_profiles/ax7020_rotating_4lane/p10_runtime_role.h"
  } else {
    set role_header "$root_dir/board_profiles/ax7020_rotating_2lane/p10_runtime_role.h"
  }
} else {
  error "P10 runtime role must be fixed or rotating"
}

# Keep generated Vitis paths short enough for Windows/Xilinx legacy tools.
set workspace [file normalize "C:/p10_vitis/${campaign}_$role"]
file mkdir $workspace
setws $workspace
set platform_name "p10_${role}_platform"
set app_name "p10_${role}_runtime"

catch {app remove $app_name}
catch {platform remove $platform_name}
platform create -name $platform_name -hw $xsa_file -proc ps7_cortexa9_0 -os standalone
platform generate
app create -name $app_name -platform $platform_name -domain standalone_domain \
  -template {Empty Application(C)}

set src_dir [file normalize "$workspace/$app_name/src"]
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
  error "P10 linker OCM hard boundary was not applied"
}
set linker_handle [open $linker_file w]
puts -nonewline $linker_handle $linker_text
close $linker_handle

file copy -force "$root_dir/software/ps_driver/p10_runtime_main.c" \
  "$src_dir/p10_runtime_main.c"
file copy -force "$root_dir/software/ps_driver/p9_runtime_main.c" \
  "$src_dir/p9_runtime_main.inc"
file copy -force $role_header "$src_dir/p10_runtime_role.h"
foreach source_path [list \
    software/ps_driver/p9_runtime_protocol.h \
    software/ps_driver/p10_1_runtime_protocol.h \
    software/ps_driver/p10_1_runtime_extension.inc \
    software/ps_driver/p9_crypto.c \
    software/ps_driver/p9_crypto.h \
    software/ps_driver/ir_regs.h] {
  file copy -force "$root_dir/$source_path" "$src_dir/[file tail $source_path]"
}

app build -name $app_name
set debug_dir [file normalize "$workspace/$app_name/Debug"]
set makefile "$debug_dir/Makefile"
set source_makefile "$debug_dir/src/subdir.mk"
set map_file [file normalize "$debug_dir/${app_name}.map"]
foreach generated_makefile [list $makefile $source_makefile] {
  if {![file exists $generated_makefile]} {
    error "P10 generated makefile missing: $generated_makefile"
  }
  set make_handle [open $generated_makefile r]
  set make_text [read $make_handle]
  close $make_handle
  set make_text [string map [list "-O0" "-O3"] $make_text]
  set make_handle [open $generated_makefile w]
  puts -nonewline $make_handle $make_text
  close $make_handle
}
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
exec make -C $debug_dir clean
file delete -force "$debug_dir/${app_name}.elf"
set make_output [exec make -C $debug_dir "${app_name}.elf" 2>@1]
puts $make_output
set verify_handle [open $source_makefile r]
set verify_text [read $verify_handle]
close $verify_handle
if {[string first "-O0" $verify_text] >= 0 ||
    [string first "-O3" $verify_text] < 0} {
  error "P10 runtime optimization flags were not frozen to -O3"
}
set elf_file [file normalize "$debug_dir/${app_name}.elf"]
if {![file exists $elf_file]} { error "P10 runtime ELF missing: $elf_file" }
if {![file exists $map_file]} { error "P10 runtime linker map missing: $map_file" }
puts "P10_PS_RUNTIME_BUILD=PASS"
puts "P10_PS_RUNTIME_ROLE=$role"
puts "P10_PS_RUNTIME_ELF=$elf_file"
puts "P10_PS_RUNTIME_MAP=$map_file"
