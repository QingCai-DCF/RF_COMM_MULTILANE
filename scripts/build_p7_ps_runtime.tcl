set root_dir [file normalize [lindex $argv 0]]
set xsa_file [file normalize [lindex $argv 1]]
set workspace [file normalize "$root_dir/build/p7_ps_vitis_workspace"]
file mkdir $workspace
setws $workspace

catch {app remove p7_runtime}
catch {platform remove p7_platform}
platform create -name p7_platform -hw $xsa_file -proc ps7_cortexa9_0 -os standalone
platform generate
app create -name p7_runtime -platform p7_platform -domain standalone_domain -template {Empty Application(C)}

set src_dir [file normalize "$workspace/p7_runtime/src"]
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
  error "P7 linker OCM hard boundary was not applied"
}
set diagnostic_memory \
    "   p7_stage62_diag : ORIGIN = 0x21000, LENGTH = 0x1000\n"
if {[string first "p7_stage62_diag : ORIGIN = 0x21000, LENGTH = 0x1000" \
        $linker_text] < 0} {
  set linker_text [string map [list \
      "   ps7_ram_1 : ORIGIN = 0xFFFF0000, LENGTH = 0xFE00" \
      "$diagnostic_memory   ps7_ram_1 : ORIGIN = 0xFFFF0000, LENGTH = 0xFE00"] \
      $linker_text]
}
set diagnostic_section {
.p7_stage62_diagnostic (NOLOAD) : {
   . = ALIGN(64);
   __p7_stage62_diagnostic_start = .;
   KEEP (*(.p7_stage62_diagnostic))
   . = ALIGN(64);
   __p7_stage62_diagnostic_end = .;
} > p7_stage62_diag
ASSERT(ADDR(.p7_stage62_diagnostic) == 0x21000,
       "P7 Stage62 diagnostic address mismatch")
ASSERT(SIZEOF(.p7_stage62_diagnostic) == 1536,
       "P7 Stage62 diagnostic size mismatch")
ASSERT(__p7_stage62_diagnostic_end <= 0x22000,
       "P7 Stage62 diagnostic overlaps fixed input reference")
}
if {[string first ".p7_stage62_diagnostic (NOLOAD)" $linker_text] < 0} {
  set linker_tail [format "\n_end = .;\n%c" 125]
  set linker_replacement [format "\n_end = .;\n%s\n%c" \
      $diagnostic_section 125]
  set linker_text [string map [list \
      $linker_tail $linker_replacement] $linker_text]
}
if {[string first "p7_stage62_diag : ORIGIN = 0x21000, LENGTH = 0x1000" \
        $linker_text] < 0 ||
    [string first ".p7_stage62_diagnostic (NOLOAD)" $linker_text] < 0} {
  error "P7 fixed Stage62 diagnostic linker section was not applied"
}
set linker_handle [open $linker_file w]
puts -nonewline $linker_handle $linker_text
close $linker_handle

foreach source_path [list \
    software/ps_driver/p7_runtime_main.c \
    software/ps_driver/p7_app_service.c \
    software/ps_driver/p7_app_service.h \
    software/ps_driver/p7_stage62_diagnostic.c \
    software/ps_driver/p7_stage62_diagnostic.h \
    software/ps_driver/p7_stage62_microtest.c \
    software/ps_driver/p7_stage62_microtest.h \
    software/ps_driver/p7_admission_contract.h \
    software/ps_driver/ir_driver.c \
    software/ps_driver/ir_driver.h \
    software/ps_driver/ir_regs.h \
    software/common/rf_app_protocol.c \
    software/common/rf_app_protocol.h \
    software/common/rf_transport_backend.c \
    software/common/rf_transport_backend.h] {
  file copy -force "$root_dir/$source_path" "$src_dir/[file tail $source_path]"
}

app build -name p7_runtime
set debug_dir [file normalize "$workspace/p7_runtime/Debug"]
set makefile "$debug_dir/Makefile"
set subdir_makefile "$debug_dir/src/subdir.mk"
set map_file [file normalize "$debug_dir/p7_runtime.map"]
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
set subdir_handle [open $subdir_makefile r]
set subdir_text [read $subdir_handle]
close $subdir_handle
if {[string first "-fstack-usage" $subdir_text] < 0} {
  set subdir_text [string map [list \
      "-fmessage-length=0 -MT" \
      "-fmessage-length=0 -fstack-usage -MT"] $subdir_text]
  if {[string first "-fstack-usage" $subdir_text] < 0} {
    error "P7 stack-usage compiler flag was not applied"
  }
  set subdir_handle [open $subdir_makefile w]
  puts -nonewline $subdir_handle $subdir_text
  close $subdir_handle
}
foreach stale [concat \
    [glob -nocomplain "$debug_dir/src/*.o"] \
    [glob -nocomplain "$debug_dir/src/*.su"]] {
  file delete -force $stale
}
file delete -force "$debug_dir/p7_runtime.elf"
set make_output [exec make -C $debug_dir p7_runtime.elf 2>@1]
puts $make_output
set elf_file [file normalize "$workspace/p7_runtime/Debug/p7_runtime.elf"]
if {![file exists $elf_file]} { error "P7 runtime ELF missing after build: $elf_file" }
if {![file exists $map_file]} { error "P7 runtime linker map missing after build: $map_file" }
puts "P7_PS_RUNTIME_BUILD=PASS"
puts "P7_PS_RUNTIME_ELF=$elf_file"
puts "P7_PS_RUNTIME_MAP=$map_file"
