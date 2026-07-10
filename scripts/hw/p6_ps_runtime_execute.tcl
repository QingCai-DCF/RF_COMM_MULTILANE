set root_dir [file normalize [lindex $argv 0]]
set bit_file [file normalize [lindex $argv 1]]
set elf_file [file normalize [lindex $argv 2]]
set ps7_init_file [file normalize [lindex $argv 3]]
set result_file [file normalize [lindex $argv 4]]
set hw_server_url [lindex $argv 5]

# --allow-hardware: fail closed before XSDB connects to the board when this
# script is invoked outside the shutdown-bounded PS runtime wrapper.
if {![info exists ::env(RF_COMM_HW_AUTH)] || $::env(RF_COMM_HW_AUTH) ne "P6_LOCAL_TRANSPORT_APPROVED"} {
  error "RF_COMM_HW_AUTH=P6_LOCAL_TRANSPORT_APPROVED required"
}
set auth_file [file join $root_dir .hardware_authorization P6_LOCAL_TRANSPORT_APPROVED.txt]
set abort_file [file join $root_dir .hardware_authorization ABORT_NOW.txt]
if {![file exists $auth_file]} { error "P6 hardware authorization file missing" }
if {[file exists $abort_file]} { error "P6 abort file is present" }
set auth_handle [open $auth_file r]
set auth_text [read $auth_handle]
close $auth_handle
foreach phrase [list "P6_LOCAL_TRANSPORT_APPROVED" "NETWORK_CABLE_CONNECTED=false" "HARDWARE_MOVEMENT_ALLOWED=false" "AVAILABLE_LANES=2" "MAX_LANE_MASK=0x3" "SHUTDOWN_ON_EXIT=required"] {
  if {[string first $phrase $auth_text] < 0} { error "P6 authorization phrase missing: $phrase" }
}

foreach required [list $bit_file $elf_file $ps7_init_file] {
  if {![file exists $required]} { error "P6 PS runtime required file missing: $required" }
}
set out [open $result_file w]
proc say {handle text} { puts $handle $text; flush $handle; puts $text }

connect -url $hw_server_url
if {[catch {targets -set -nocase -filter {name =~ "*DAP*"}} dap_error]} {
  # Some XSDB target enumerations expose APU/Cortex/FPGA targets but omit the
  # DAP alias after a shutdown-bitstream program.  The APU target supports the
  # same bounded system reset and avoids treating an alias difference as a
  # runtime-environment blocker.
  targets -set -nocase -filter {name =~ "*APU*"}
  say $out "P6_PS_RESET_TARGET_FALLBACK=APU"
} else {
  say $out "P6_PS_RESET_TARGET=DAP"
}
rst -system
after 1000
targets -set -nocase -filter {name =~ "*xc7z*"}
fpga -file $bit_file
say $out "P6_PS_CANDIDATE_PROGRAMMED=1"
after 1000

targets -set -nocase -filter {name =~ "*Cortex-A9*#0"}
source $ps7_init_file
ps7_init
ps7_post_config
rst -processor
mwr 0x00020000 0x00000000 16
dow $elf_file
say $out "P6_PS_ELF_DOWNLOADED=1"
set magic_seen 0
for {set poll 0} {$poll < 300} {incr poll} {
  con
  after 100
  catch {stop}
  set magic [mrd -value 0x00020000]
  if {$magic == 0x50365254} {
    set magic_seen 1
    say $out "P6_PS_MAILBOX_POLLS=[expr {$poll + 1}]"
    break
  }
}
if {!$magic_seen} {
  close $out
  error "P6 PS runtime mailbox timeout"
}

set keys [list MAGIC STATUS P6_STATUS MAILBOX_STATUS PAYLOAD_CRC32 RX_PAYLOAD_CRC32 RX_PAYLOAD_LEN TX_COUNT RX_GOOD_L0 RX_GOOD_L1 CRC_BAD PAYLOAD_MISMATCH RETRY_EXHAUSTED TX_FAIL ERROR_CODE STICKY_ERROR]
set values {}
for {set idx 0} {$idx < 16} {incr idx} {
  set value [mrd -value [expr {0x00020000 + 4*$idx}]]
  lappend values $value
  say $out "P6_PS_[lindex $keys $idx]=[format %08X $value]"
}
if {[lindex $values 0] != 0x50365254} { close $out; error "P6 PS mailbox magic mismatch" }
if {[lindex $values 1] != 0} { close $out; error "P6 PS runtime returned failure status=[lindex $values 1]" }
if {([lindex $values 2] & 0xF0) != 0x10} { close $out; error "P6 PS transport status mismatch" }
if {[lindex $values 3] != 0x50364F4B} { close $out; error "P6 PS transport mailbox mismatch" }
if {[lindex $values 4] != [lindex $values 5]} { close $out; error "P6 PS payload CRC mismatch" }
if {[lindex $values 6] != 247} { close $out; error "P6 PS RX payload length mismatch" }
if {[lindex $values 7] != 1 || [lindex $values 8] != 1 || [lindex $values 9] != 1} { close $out; error "P6 PS lane counter mismatch" }
for {set idx 10} {$idx < 16} {incr idx} {
  if {[lindex $values $idx] != 0} { close $out; error "P6 PS error mailbox field [lindex $keys $idx] nonzero" }
}
say $out "P6_PS_RUNTIME_MAILBOX=PASS"
close $out
disconnect
