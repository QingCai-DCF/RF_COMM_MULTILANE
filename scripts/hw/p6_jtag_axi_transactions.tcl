set root_dir [file normalize [lindex $argv 0]]
set bit_file [file normalize [lindex $argv 1]]
set ltx_file [file normalize [lindex $argv 2]]
set txn_file [file normalize [lindex $argv 3]]
set result_file [file normalize [lindex $argv 4]]
set hw_server_url [lindex $argv 5]
set jtag_frequency_hz [lindex $argv 6]

# --allow-hardware: fail closed before any hardware connection when invoked
# outside the shutdown-bounded P6 wrapper.
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

foreach required [list $bit_file $ltx_file $txn_file] {
  if {![file exists $required]} { error "P6 required file missing: $required" }
}
source [file join $root_dir legacy RF_COMM tools hw_connect_utils.tcl]

set dev [rf_hw_open_zynq_device $hw_server_url $jtag_frequency_hz]
set_property PROGRAM.FILE $bit_file $dev
set_property PROBES.FILE $ltx_file $dev
set_property FULL_PROBES.FILE $ltx_file $dev
program_hw_devices $dev
refresh_hw_device -update_hw_probes true $dev
after 1000

set hw_axis [get_hw_axis -quiet -of_objects $dev]
if {[llength $hw_axis] == 0} { set hw_axis [get_hw_axis -quiet] }
if {[llength $hw_axis] == 0} { error "P6 JTAG AXI master not discovered after programming candidate" }
set hw_axi [lindex $hw_axis 0]
set out [open $result_file w]
puts $out "P6_CANDIDATE_PROGRAMMED=1"
puts $out "P6_HW_AXI=[get_property NAME $hw_axi]"

set txn_index 0
set soak_cases {}
proc p6_axi_write {hw_axi address data txn_index_var} {
  upvar $txn_index_var txn_index
  incr txn_index
  set name "p6_w_$txn_index"
  create_hw_axi_txn $name $hw_axi -type write -address $address -data $data -len 1 -force
  run_hw_axi [get_hw_axi_txns $name]
  delete_hw_axi_txn [get_hw_axi_txns $name]
}
proc p6_axi_read {hw_axi address txn_index_var} {
  upvar $txn_index_var txn_index
  incr txn_index
  set name "p6_r_$txn_index"
  create_hw_axi_txn $name $hw_axi -type read -address $address -len 1 -force
  run_hw_axi [get_hw_axi_txns $name]
  set txn [get_hw_axi_txns $name]
  set data [get_property DATA $txn]
  delete_hw_axi_txn $txn
  return [string toupper [string range "00000000$data" end-7 end]]
}

set tf [open $txn_file r]
set lines [split [read $tf] "\n"]
close $tf
foreach raw_line $lines {
  set line [string trim $raw_line]
  if {$line eq "" || [string match "#*" $line]} { continue }
  set fields [regexp -all -inline {\S+} $line]
  set op [lindex $fields 0]
  if {$op eq "W"} {
    p6_axi_write $hw_axi [lindex $fields 1] [lindex $fields 2] txn_index
  } elseif {$op eq "R"} {
    set value [p6_axi_read $hw_axi [lindex $fields 1] txn_index]
    puts $out "[lindex $fields 2]=$value"
    flush $out
  } elseif {$op eq "POLL"} {
    set address [lindex $fields 1]
    scan [lindex $fields 2] %x mask
    scan [lindex $fields 3] %x expected
    set max_polls [lindex $fields 4]
    set key [lindex $fields 5]
    set matched 0
    set last_value 0
    for {set poll 0} {$poll < $max_polls} {incr poll} {
      set value_text [p6_axi_read $hw_axi $address txn_index]
      scan $value_text %x last_value
      if {[expr {$last_value & $mask}] == $expected} {
        set matched 1
        puts $out "$key=$value_text"
        puts $out "${key}_POLLS=[expr {$poll + 1}]"
        flush $out
        break
      }
      after 1
    }
    if {!$matched} {
      puts $out "$key=[format %08X $last_value]"
      puts $out "${key}_TIMEOUT=1"
      close $out
      error "P6 bounded poll timeout key=$key address=$address"
    }
  } elseif {$op eq "ASSERT"} {
    set address [lindex $fields 1]
    scan [lindex $fields 2] %x mask
    scan [lindex $fields 3] %x expected
    set key [lindex $fields 4]
    set value_text [p6_axi_read $hw_axi $address txn_index]
    scan $value_text %x value
    puts $out "$key=$value_text"
    flush $out
    if {[expr {$value & $mask}] != $expected} {
      puts $out "${key}_ASSERT_FAILED=1"
      close $out
      error "P6 assertion failed key=$key address=$address value=$value_text mask=[format %08X $mask] expected=[format %08X $expected]"
    }
  } elseif {$op eq "SOAK_CASE"} {
    lappend soak_cases [lrange $fields 1 end]
  } elseif {$op eq "SOAK"} {
    if {[llength $soak_cases] == 0} { close $out; error "P6 SOAK requires at least one SOAK_CASE" }
    scan [lindex $fields 1] %x soak_base
    set soak_runtime_sec [lindex $fields 2]
    set soak_sample_sec [lindex $fields 3]
    set soak_min_frames [lindex $fields 4]
    set soak_start_ms [clock milliseconds]
    set soak_end_ms [expr {$soak_start_ms + 1000 * $soak_runtime_sec}]
    set soak_next_sample_ms [expr {$soak_start_ms + 1000 * $soak_sample_sec}]
    set soak_next_case_ms $soak_start_ms
    set soak_case_index -1
    set soak_transfers 0
    set soak_sample_index 0
    while {[clock milliseconds] < $soak_end_ms} {
      set now_ms [clock milliseconds]
      if {$now_ms >= $soak_next_case_ms} {
        incr soak_case_index
        set soak_case [lindex $soak_cases [expr {$soak_case_index % [llength $soak_cases]}]]
        set soak_length [lindex $soak_case 0]
        set soak_crc_text [lindex $soak_case 1]
        set soak_words [lrange $soak_case 2 end]
        p6_axi_write $hw_axi [format 0x%08X [expr {$soak_base + 0x100}]] 0x00000030 txn_index
        set soak_word_index 0
        foreach soak_word $soak_words {
          p6_axi_write $hw_axi [format 0x%08X [expr {$soak_base + 0x200 + 4*$soak_word_index}]] $soak_word txn_index
          incr soak_word_index
        }
        p6_axi_write $hw_axi [format 0x%08X [expr {$soak_base + 0x108}]] 0x00002201 txn_index
        p6_axi_write $hw_axi [format 0x%08X [expr {$soak_base + 0x10C}]] 0x00000003 txn_index
        p6_axi_write $hw_axi [format 0x%08X [expr {$soak_base + 0x110}]] 0x00000003 txn_index
        p6_axi_write $hw_axi [format 0x%08X [expr {$soak_base + 0x114}]] [format 0x%08X $soak_length] txn_index
        p6_axi_write $hw_axi [format 0x%08X [expr {$soak_base + 0x15C}]] 0x0061A800 txn_index
        p6_axi_write $hw_axi [format 0x%08X [expr {$soak_base + 0x100}]] 0x00000004 txn_index
        set committed 0
        for {set commit_poll 0} {$commit_poll < 2000} {incr commit_poll} {
          set commit_text [p6_axi_read $hw_axi [format 0x%08X [expr {$soak_base + 0x104}]] txn_index]
          scan $commit_text %x commit_value
          if {($commit_value & 0x04) == 0x04} { set committed 1; break }
          after 1
        }
        if {!$committed} { close $out; error "P6 soak commit timeout case=$soak_case_index" }
        set crc_text [p6_axi_read $hw_axi [format 0x%08X [expr {$soak_base + 0x120}]] txn_index]
        scan $crc_text %x crc_value
        scan $soak_crc_text %x expected_crc
        if {$crc_value != $expected_crc} { close $out; error "P6 soak commit CRC mismatch case=$soak_case_index" }
        puts $out "SOAK_CASE_ROTATION_$soak_case_index=LENGTH_$soak_length"
        flush $out
        set soak_next_case_ms [expr {$soak_next_case_ms + 1000 * $soak_sample_sec}]
      }

      p6_axi_write $hw_axi [format 0x%08X [expr {$soak_base + 0x100}]] 0x00000008 txn_index
      set transfer_done 0
      set transfer_status 0
      for {set transfer_poll 0} {$transfer_poll < 10000} {incr transfer_poll} {
        set status_text [p6_axi_read $hw_axi [format 0x%08X [expr {$soak_base + 0x104}]] txn_index]
        scan $status_text %x transfer_status
        if {($transfer_status & 0x10) == 0x10} { set transfer_done 1; break }
        after 1
      }
      if {!$transfer_done || ($transfer_status & 0xE0) != 0} {
        close $out
        error "P6 soak transfer failure status=[format %08X $transfer_status] transfers=$soak_transfers"
      }
      foreach check_spec [list [list 0x138 CRC_BAD] [list 0x13C PAYLOAD_MISMATCH] [list 0x144 RETRY_EXHAUSTED] [list 0x148 TX_FAIL] [list 0x150 DUTY_VIOLATION] [list 0x160 ERROR_CODE] [list 0x164 STICKY_ERROR]] {
        set check_text [p6_axi_read $hw_axi [format 0x%08X [expr {$soak_base + [lindex $check_spec 0]}]] txn_index]
        scan $check_text %x check_value
        if {$check_value != 0} { close $out; error "P6 soak stop condition [lindex $check_spec 1]=$check_text" }
      }
      incr soak_transfers

      set now_ms [clock milliseconds]
      if {$now_ms >= $soak_next_sample_ms || $now_ms >= $soak_end_ms} {
        set tx_text [p6_axi_read $hw_axi [format 0x%08X [expr {$soak_base + 0x12C}]] txn_index]
        set l0_text [p6_axi_read $hw_axi [format 0x%08X [expr {$soak_base + 0x130}]] txn_index]
        set l1_text [p6_axi_read $hw_axi [format 0x%08X [expr {$soak_base + 0x134}]] txn_index]
        scan $tx_text %x tx_value
        scan $l0_text %x l0_value
        scan $l1_text %x l1_value
        if {$tx_value != $l0_value || $tx_value != $l1_value} {
          close $out
          error "P6 soak lane counter mismatch tx=$tx_text l0=$l0_text l1=$l1_text"
        }
        incr soak_sample_index
        set elapsed_sec [expr {([clock milliseconds] - $soak_start_ms) / 1000.0}]
        puts $out "SOAK_SAMPLE_$soak_sample_index=ELAPSED_SEC_[format %.3f $elapsed_sec],TX_$tx_text,L0_$l0_text,L1_$l1_text"
        flush $out
        while {$soak_next_sample_ms <= $now_ms} { set soak_next_sample_ms [expr {$soak_next_sample_ms + 1000 * $soak_sample_sec}] }
      }
    }
    set final_tx_text [p6_axi_read $hw_axi [format 0x%08X [expr {$soak_base + 0x12C}]] txn_index]
    set final_l0_text [p6_axi_read $hw_axi [format 0x%08X [expr {$soak_base + 0x130}]] txn_index]
    set final_l1_text [p6_axi_read $hw_axi [format 0x%08X [expr {$soak_base + 0x134}]] txn_index]
    scan $final_tx_text %x final_tx
    scan $final_l0_text %x final_l0
    scan $final_l1_text %x final_l1
    if {$final_tx < $soak_min_frames || $final_l0 < $soak_min_frames || $final_l1 < $soak_min_frames} {
      close $out
      error "P6 soak minimum frame count not met tx=$final_tx l0=$final_l0 l1=$final_l1 required=$soak_min_frames"
    }
    set soak_elapsed_sec [expr {([clock milliseconds] - $soak_start_ms) / 1000.0}]
    puts $out "P6_SOAK_ELAPSED_SEC=[format %.3f $soak_elapsed_sec]"
    puts $out "P6_SOAK_TX_COUNT=$final_tx_text"
    puts $out "P6_SOAK_RX_GOOD_L0=$final_l0_text"
    puts $out "P6_SOAK_RX_GOOD_L1=$final_l1_text"
    puts $out "P6_SOAK_SAMPLE_COUNT=$soak_sample_index"
    puts $out "P6_SOAK_CASE_ROTATIONS=[expr {$soak_case_index + 1}]"
    puts $out "P6_TWO_LANE_2H_STATIONARY_SOAK=PASS"
    flush $out
    p6_axi_write $hw_axi [format 0x%08X [expr {$soak_base + 0x100}]] 0x00000030 txn_index
  } elseif {$op eq "WAIT"} {
    after [lindex $fields 1]
  } else {
    close $out
    error "P6 unknown transaction operation: $op"
  }
}
puts $out "P6_JTAG_AXI_TRANSACTIONS=PASS"
puts $out "P6_JTAG_AXI_TRANSACTION_COUNT=$txn_index"
close $out
puts "P6_CANDIDATE_PROGRAMMED=1"
puts "P6_JTAG_AXI_TRANSACTIONS=PASS"
