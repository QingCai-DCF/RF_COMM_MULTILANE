# P7 PS application executor for XSDB.
#
# The execution plan is a fixed data grammar.  It is never sourced, evaluated,
# or passed to exec.  This script must only be launched by the Python safe
# wrapper, which independently owns process-tree timeout and shutdown-after.
# require-user-hw-authorization: outer safe wrapper validates authorization,
# immutable hashes, exact live target identity, bounded runtime, and shutdown.

proc p7_auth_value {text key} {
  foreach raw_line [split $text "\n"] {
    set line [string trim $raw_line]
    if {$line eq "" || [string match "#*" $line]} { continue }
    set separator [string first "=" $line]
    if {$separator < 1} { continue }
    if {[string trim [string range $line 0 [expr {$separator - 1}]]] eq $key} {
      return [string trim [string range $line [expr {$separator + 1}] end]]
    }
  }
  return ""
}

proc p7_has_marker {text marker} {
  foreach raw_line [split $text "\n"] {
    if {[string trim $raw_line] eq $marker} { return 1 }
  }
  return 0
}

proc p7_require_value {text key expected} {
  set observed [p7_auth_value $text $key]
  if {![string equal -nocase $observed $expected]} {
    error "P7 authorization mismatch for $key expected=$expected observed=$observed"
  }
}

proc p7_normal_path {path} {
  return [string tolower [string map {\ /} [file normalize $path]]]
}

proc p7_require_path {text key expected} {
  set observed [p7_auth_value $text $key]
  if {$observed eq "" || [p7_normal_path $observed] ne [p7_normal_path $expected]} {
    error "P7 authorization path mismatch for $key expected=$expected observed=$observed"
  }
}

proc p7_marker_value {text key} {
  foreach raw_line [split $text "\n"] {
    set line [string trim $raw_line]
    set separator [string first "=" $line]
    if {$separator < 1} { continue }
    if {[string trim [string range $line 0 [expr {$separator - 1}]]] eq $key} {
      return [string trim [string range $line [expr {$separator + 1}] end]]
    }
  }
  return ""
}

proc p7_parse_hex32 {text label} {
  if {![regexp -nocase {^0x[0-9a-f]{8}$} $text]} {
    error "$label must be exactly 0x plus eight hex digits: $text"
  }
  scan [string range $text 2 end] %x value
  return $value
}

proc p7_normal_idcode {value} {
  set normalized [string tolower [string trim $value]]
  if {[string match "0x*" $normalized]} { set normalized [string range $normalized 2 end] }
  set normalized [string trimleft $normalized 0]
  if {$normalized eq ""} { set normalized 0 }
  return $normalized
}

proc p7_read32 {address} {
  set value [mrd -value $address]
  return [expr {$value & 0xFFFFFFFF}]
}

set ::p7_last_runtime_elapsed_ticks 0
set ::p7_runtime_elapsed_request 0
set ::p7_terminal_unacknowledged_refresh 0
set ::p7_terminal_unacknowledged_request 0
set ::p7_terminal_unacknowledged_ack 0

proc p7_read_runtime_elapsed_ticks {{refresh 1}} {
  global p7_last_runtime_elapsed_ticks
  global p7_runtime_elapsed_request
  global p7_terminal_unacknowledged_refresh
  global p7_terminal_unacknowledged_request
  global p7_terminal_unacknowledged_ack
  if {$refresh} {
    set state_before [p7_read32 0x00020008]
    if {$state_before != 4 && $state_before != 5} {
      set p7_runtime_elapsed_request [expr {($p7_runtime_elapsed_request + 1) & 0xFFFFFFFF}]
      if {$p7_runtime_elapsed_request == 0} { set p7_runtime_elapsed_request 1 }
      mwr 0x0002008C $p7_runtime_elapsed_request
      set acknowledged 0
      set terminal_release 0
      for {set poll 0} {$poll < 10000} {incr poll} {
        set observed_ack [p7_read32 0x00020090]
        if {$observed_ack == $p7_runtime_elapsed_request} {
          set acknowledged 1
          break
        }
        set observed_state [p7_read32 0x00020008]
        if {$observed_state == 4 || $observed_state == 5} {
          # Firmware publishes the final stable seqlock/ACK before the
          # terminal state.  A request written after its final request read
          # can honestly remain unacknowledged; terminal state releases the
          # immutable final snapshot without fabricating an ACK.
          set terminal_ack [p7_read32 0x00020090]
          if {$terminal_ack == $p7_runtime_elapsed_request} {
            set acknowledged 1
          } else {
            set terminal_release 1
            set p7_terminal_unacknowledged_refresh 1
            set p7_terminal_unacknowledged_request $p7_runtime_elapsed_request
            set p7_terminal_unacknowledged_ack $terminal_ack
          }
          break
        }
        after 1
      }
      if {!$acknowledged && !$terminal_release} {
        error "P7 mailbox runtime elapsed snapshot request was not acknowledged"
      }
    }
  }
  for {set attempt 0} {$attempt < 8} {incr attempt} {
    set sequence_before [p7_read32 0x00020088]
    if {$sequence_before & 1} { continue }
    set low [p7_read32 0x00020074]
    set high [p7_read32 0x00020078]
    set sequence_after [p7_read32 0x00020088]
    if {$sequence_before == $sequence_after && !($sequence_after & 1)} {
      set value [expr {$low | ($high << 32)}]
      if {$value < $p7_last_runtime_elapsed_ticks} {
        error "P7 mailbox runtime_elapsed_ticks regressed across stable seqlock snapshots"
      }
      set p7_last_runtime_elapsed_ticks $value
      return $value
    }
  }
  error "P7 mailbox runtime_elapsed_ticks was not a stable even seqlock snapshot"
}

proc p7_le32 {data offset} {
  if {$offset < 0 || $offset + 4 > [string length $data]} {
    error "P7 little-endian word read is out of range"
  }
  binary scan [string range $data $offset [expr {$offset + 3}]] c4 octets
  return [expr {([lindex $octets 0] & 0xFF) |
      (([lindex $octets 1] & 0xFF) << 8) |
      (([lindex $octets 2] & 0xFF) << 16) |
      (([lindex $octets 3] & 0xFF) << 24)}]
}

proc p7_say {handle line} {
  puts $handle $line
  flush $handle
  puts $line
  flush stdout
}

set ::p7_stationary_terminal_marker_emitted 0
set ::p7_stationary_terminal_observed_ms 0

proc p7_mark_stationary_terminal {result_handle} {
  global p7_stationary_terminal_marker_emitted
  global p7_stationary_terminal_observed_ms
  if {!$p7_stationary_terminal_marker_emitted} {
    set p7_stationary_terminal_marker_emitted 1
    set p7_stationary_terminal_observed_ms [clock milliseconds]
    p7_say $result_handle "P7_STATIONARY_SERVICE_TERMINAL_OBSERVED=1"
  }
}

proc p7_stationary_chunked_dump {result_handle abort_file path address byte_count} {
  set partial "${path}.write_partial"
  set chunk_path "${partial}.chunk"
  catch {file delete -force $partial $chunk_path}
  set output [open $partial wb]
  fconfigure $output -translation binary
  set chunk_limit 4096
  set offset 0
  while {$offset < $byte_count} {
    p7_check_abort $abort_file
    set chunk_size [expr {min($chunk_limit, $byte_count - $offset)}]
    mrd -size b -bin -file $chunk_path [expr {$address + $offset}] $chunk_size
    set chunk [open $chunk_path rb]
    fconfigure $chunk -translation binary
    set payload [read $chunk]
    close $chunk
    catch {file delete -force $chunk_path}
    if {[string length $payload] != $chunk_size} {
      close $output
      error "P7 stationary chunked dump returned the wrong byte count"
    }
    puts -nonewline $output $payload
    set offset [expr {$offset + $chunk_size}]
    set service_state [p7_read32 0x00020008]
    if {$service_state == 4 || $service_state == 5} {
      p7_mark_stationary_terminal $result_handle
    }
  }
  flush $output
  close $output
  file rename -force $partial $path
}

proc p7_atomic_dump {path address byte_count} {
  set partial "${path}.write_partial"
  catch {file delete -force $partial}
  if {$byte_count == 0} {
    set handle [open $partial w]
    fconfigure $handle -translation binary
    close $handle
  } else {
    # XSDB's count is in values, not bytes.  Force byte-wide reads so the
    # host receives exactly byte_count bytes and exact-size validation is
    # meaningful.
    mrd -size b -bin -file $partial $address $byte_count
  }
  file rename -force $partial $path
}

proc p7_check_abort {abort_file} {
  if {[file exists $abort_file]} {
    catch {mwr 0x0002000C 3}
    after 10
    catch {mwr 0x0002000C 5}
    error "P7 operator abort file appeared"
  }
}

proc p7_wait_service_ready {abort_file result_handle label} {
  for {set poll 0} {$poll < 3000} {incr poll} {
    p7_check_abort $abort_file
    set start_ticks [expr {[p7_read32 0x0002006C] | ([p7_read32 0x00020070] << 32)}]
    if {[p7_read32 0x00020000] == 0x424D3750 && [p7_read32 0x00020008] != 0 &&
        [p7_read32 0x0002004C] > 0 && $start_ticks > 0} {
      p7_say $result_handle "${label}_READY_POLLS=[expr {$poll + 1}]"
      p7_say $result_handle "${label}_HEARTBEAT_AND_START_TICKS=1"
      return
    }
    after 10
  }
  error "$label service readiness timeout"
}

proc p7_wait_descriptor_terminal {abort_file descriptor_address deadline_ms label} {
  while {[clock milliseconds] < $deadline_ms} {
    p7_check_abort $abort_file
    set status [p7_read32 [expr {$descriptor_address + 0x0C}]]
    if {$status >= 3 && $status <= 6} {
      return [list $status [p7_read32 [expr {$descriptor_address + 0x44}]]]
    }
    after 5
  }
  error "$label descriptor terminal timeout"
}

proc p7_wait_service_terminal {abort_file deadline_ms label} {
  while {[clock milliseconds] < $deadline_ms} {
    p7_check_abort $abort_file
    set state [p7_read32 0x00020008]
    if {$state == 4 || $state == 5} { return $state }
    after 10
  }
  error "$label service shutdown timeout"
}

proc p7_load_phase {bundle_dir mailbox_file case_input_name case_output_name \
    case_length_name case_trace_name case_trace_capacity_name} {
  upvar $case_input_name case_input $case_output_name case_output \
      $case_length_name case_length $case_trace_name case_trace \
      $case_trace_capacity_name case_trace_capacity
  foreach slot [lsort -integer [array names case_input]] {
    if {$case_length($slot) > 0} {
      dow -data [file join $bundle_dir "input_${slot}.bin"] $case_input($slot)
      dow -data [file join $bundle_dir "output_zero_${slot}.bin"] $case_output($slot)
    }
    dow -data [file join $bundle_dir "trace_zero_${slot}.bin"] $case_trace($slot)
  }
  dow -data $mailbox_file 0x00020000
  dow -data [file join $bundle_dir descriptors.bin] 0x00020100
}

proc p7_publish_phase_descriptors {bundle_dir publish_slots} {
  foreach slot $publish_slots {
    set descriptor_address [expr {0x00020100 + 0x100 * $slot}]
    # The running service has already completed its stale-descriptor clear.
    # Rewrite the complete FREE body, then publish READY as the final word.
    dow -data [file join $bundle_dir "descriptor_free_${slot}.bin"] $descriptor_address
    mwr [expr {$descriptor_address + 0x0C}] 1
  }
}

proc p7_publish_source_descriptor_to_target {bundle_dir source_slot target_slot} {
  if {$source_slot < 0 || $source_slot >= 8 || $target_slot < 0 || $target_slot >= 8} {
    error "P7 descriptor remap slot is outside 0..7"
  }
  set descriptor_address [expr {0x00020100 + 0x100 * $target_slot}]
  dow -data [file join $bundle_dir "descriptor_free_${source_slot}.bin"] $descriptor_address
  mwr [expr {$descriptor_address + 0x0C}] 1
}

proc p7_queue_admit_candidate {bundle_dir input_address output_address object_length \
    trace_address trace_capacity} {
  set capacity [p7_read32 0x00020010]
  set occupancy [p7_read32 0x00020014]
  set ddr_write_count 0
  if {$occupancy >= $capacity} {
    return [dict create result FULL occupancy $occupancy capacity $capacity \
        ddr_write_count $ddr_write_count]
  }
  set target_slot -1
  for {set slot 0} {$slot < $capacity} {incr slot} {
    if {[p7_read32 [expr {0x00020100 + 0x100 * $slot + 0x0C}]] == 0} {
      set target_slot $slot
      break
    }
  }
  if {$target_slot < 0} { error "P7 queue admission found no FREE slot below reported capacity" }
  if {$object_length > 0} {
    dow -data [file join $bundle_dir queue_overflow_candidate_input.bin] $input_address
    incr ddr_write_count
    dow -data [file join $bundle_dir queue_overflow_candidate_output_zero.bin] $output_address
    incr ddr_write_count
  }
  dow -data [file join $bundle_dir queue_overflow_candidate_trace_zero.bin] $trace_address
  incr ddr_write_count
  set descriptor_address [expr {0x00020100 + 0x100 * $target_slot}]
  dow -data [file join $bundle_dir queue_overflow_candidate_descriptor_free.bin] $descriptor_address
  incr ddr_write_count
  mwr [expr {$descriptor_address + 0x0C}] 1
  incr ddr_write_count
  return [dict create result ADMITTED occupancy $occupancy capacity $capacity \
      ddr_write_count $ddr_write_count target_slot $target_slot]
}

proc p7_dump_case {bundle_dir slot input_address output_address object_length trace_address trace_capacity \
    {prefix ""} {descriptor_slot -1} {stationary_result_handle ""} {abort_file ""}} {
  if {$descriptor_slot < 0} { set descriptor_slot $slot }
  set descriptor_address [expr {0x00020100 + 0x100 * $descriptor_slot}]
  set status_before [p7_read32 [expr {$descriptor_address + 0x0C}]]
  if {$status_before < 3 || $status_before > 6} {
    error "P7 descriptor snapshot requested before terminal publication slot=$slot status=$status_before"
  }
  if {$prefix eq ""} {
    set descriptor_name "descriptor_result_${slot}.bin"
    set output_name "output_result_${slot}.bin"
    set trace_name "trace_result_${slot}.bin"
  } else {
    set descriptor_name "${prefix}_descriptor_result.bin"
    set output_name "${prefix}_output_result.bin"
    set trace_name "${prefix}_trace_result.bin"
  }
  if {$stationary_result_handle eq ""} {
    p7_atomic_dump [file join $bundle_dir $descriptor_name] $descriptor_address 256
  } else {
    p7_stationary_chunked_dump $stationary_result_handle $abort_file \
        [file join $bundle_dir $descriptor_name] $descriptor_address 256
  }
  set status_after [p7_read32 [expr {$descriptor_address + 0x0C}]]
  if {$status_after != $status_before} {
    error "P7 descriptor status changed across terminal snapshot slot=$slot before=$status_before after=$status_after"
  }
  if {$stationary_result_handle eq ""} {
    p7_atomic_dump [file join $bundle_dir $output_name] $output_address $object_length
    p7_atomic_dump [file join $bundle_dir $trace_name] $trace_address [expr {$trace_capacity * 64}]
  } else {
    p7_stationary_chunked_dump $stationary_result_handle $abort_file \
        [file join $bundle_dir $output_name] $output_address $object_length
    p7_stationary_chunked_dump $stationary_result_handle $abort_file \
        [file join $bundle_dir $trace_name] $trace_address [expr {$trace_capacity * 64}]
  }
}

proc p7_prepare_stationary_slot {bundle_dir slot descriptor_address object_id} {
  # Preload the complete body while status remains FREE.  This procedure is
  # intentionally forbidden from publishing READY; admission happens only
  # after a fresh causal PS-time snapshot and cutoff guard.
  dow -data [file join $bundle_dir "descriptor_free_${slot}.bin"] $descriptor_address
  mwr [expr {$descriptor_address + 0x14}] $object_id
  if {[p7_read32 [expr {$descriptor_address + 0x0C}]] != 0} {
    error "P7 stationary prepared descriptor did not remain FREE"
  }
}

proc p7_commit_stationary_slot {descriptor_address} {
  # The only READY publication write for a preloaded stationary descriptor.
  mwr [expr {$descriptor_address + 0x0C}] 1
}

proc p7_record_stationary_terminal {result_handle sequence slot generation descriptor_address} {
  set session [p7_read32 [expr {$descriptor_address + 0x10}]]
  set object_id [p7_read32 [expr {$descriptor_address + 0x14}]]
  set status [p7_read32 [expr {$descriptor_address + 0x0C}]]
  set error_code [p7_read32 [expr {$descriptor_address + 0x44}]]
  set bytes_completed [p7_read32 [expr {$descriptor_address + 0x48}]]
  set fragments_total [p7_read32 [expr {$descriptor_address + 0x4C}]]
  set fragments_completed [p7_read32 [expr {$descriptor_address + 0x50}]]
  set output_sha ""
  for {set word 40} {$word < 48} {incr word} {
    append output_sha [format %08X [p7_read32 [expr {$descriptor_address + 4 * $word}]]]
  }
  set fragment_attempts [p7_read32 [expr {$descriptor_address + 0x58}]]
  set fallback_count [p7_read32 [expr {$descriptor_address + 0x5C}]]
  set p6_retry_count [p7_read32 [expr {$descriptor_address + 0xC0}]]
  set p6_retry_exhausted [p7_read32 [expr {$descriptor_address + 0xC4}]]
  set p6_tx_fail [p7_read32 [expr {$descriptor_address + 0xC8}]]
  set p6_crc_bad [p7_read32 [expr {$descriptor_address + 0xCC}]]
  set p6_payload_mismatch [p7_read32 [expr {$descriptor_address + 0xD0}]]
  set max_txd_high_cycles [p7_read32 [expr {$descriptor_address + 0xD4}]]
  set duty_violations [p7_read32 [expr {$descriptor_address + 0xD8}]]
  set lane0_fragments [p7_read32 [expr {$descriptor_address + 0xDC}]]
  set lane1_fragments [p7_read32 [expr {$descriptor_address + 0xE0}]]
  set replicated_fragments [p7_read32 [expr {$descriptor_address + 0xE4}]]
  set start_ticks [expr {[p7_read32 [expr {$descriptor_address + 0xE8}]] |
      ([p7_read32 [expr {$descriptor_address + 0xEC}]] << 32)}]
  set end_ticks [expr {[p7_read32 [expr {$descriptor_address + 0xF0}]] |
      ([p7_read32 [expr {$descriptor_address + 0xF4}]] << 32)}]
  set completion_sequence [p7_read32 [expr {$descriptor_address + 0xFC}]]
  p7_say $result_handle [format \
      "P7_STATIONARY_OBJECT_%08u=SLOT_%u,GEN_%u,SESSION_%08X,OBJECT_%u,STATUS_%u,ERROR_%u,BYTES_%u,FRAGMENTS_%u/%u,ATTEMPTS_%u,FALLBACKS_%u,OUTSHA_%s,P6_RETRY_COUNT_%u,P6_RETRY_EXHAUSTED_%u,P6_TX_FAIL_%u,P6_CRC_BAD_%u,P6_PAYLOAD_MISMATCH_%u,MAX_TXD_HIGH_CYCLES_%u,DUTY_VIOLATIONS_%u,LANE0_%u,LANE1_%u,REPLICATED_%u,START_TICKS_%s,END_TICKS_%s,COMPLETION_SEQUENCE_%u" \
      $sequence $slot $generation $session $object_id $status $error_code $bytes_completed \
      $fragments_completed $fragments_total $fragment_attempts $fallback_count $output_sha \
      $p6_retry_count $p6_retry_exhausted $p6_tx_fail $p6_crc_bad $p6_payload_mismatch \
      $max_txd_high_cycles $duty_violations $lane0_fragments $lane1_fragments \
      $replicated_fragments $start_ticks $end_ticks $completion_sequence]
  return [dict create object_id $object_id bytes_completed $bytes_completed \
      fragments_completed $fragments_completed fragment_attempts $fragment_attempts \
      fallback_count $fallback_count p6_retry_count $p6_retry_count \
      p6_retry_exhausted $p6_retry_exhausted p6_tx_fail $p6_tx_fail \
      p6_crc_bad $p6_crc_bad p6_payload_mismatch $p6_payload_mismatch \
      max_txd_high_cycles $max_txd_high_cycles duty_violations $duty_violations \
      lane0_fragments $lane0_fragments lane1_fragments $lane1_fragments \
      replicated_fragments $replicated_fragments start_ticks $start_ticks end_ticks $end_ticks \
      completion_sequence $completion_sequence]
}

proc p7_percentile {sorted_values numerator denominator} {
  set count [llength $sorted_values]
  if {$count == 0} { return 0 }
  set rank [expr {int(ceil(double($numerator * $count) / double($denominator))) - 1}]
  if {$rank < 0} { set rank 0 }
  if {$rank >= $count} { set rank [expr {$count - 1}] }
  return [lindex $sorted_values $rank]
}

proc p7_latency_summary {values} {
  if {[llength $values] == 0} {
    return [dict create count 0 min 0 mean 0 p50 0 p95 0 p99 0 max 0]
  }
  set sorted [lsort -integer $values]
  set sum 0
  foreach value $sorted { set sum [expr {$sum + $value}] }
  set count [llength $sorted]
  return [dict create count $count min [lindex $sorted 0] mean [expr {$sum / $count}] \
      p50 [p7_percentile $sorted 50 100] p95 [p7_percentile $sorted 95 100] \
      p99 [p7_percentile $sorted 99 100] max [lindex $sorted end]]
}

proc p7_stationary_sample_from_ledger {records runtime_start_ticks threshold_ticks \
    previous_threshold_ticks counts_per_second} {
  set objects 0
  set bytes 0
  set fragments 0
  set lane0 0
  set lane1 0
  set replicated 0
  set fallbacks 0
  set p6_retries 0
  set p6_retry_exhausted 0
  set p6_tx_fail 0
  set p6_crc_bad 0
  set p6_payload_mismatch 0
  set duty_violations 0
  set max_txd_high 0
  set last_object 0
  set interval_latencies {}
  foreach terminal $records {
    set relative_end [expr {[dict get $terminal end_ticks] - $runtime_start_ticks}]
    if {$relative_end < 0} {
      error "P7 stationary terminal end precedes runtime start"
    }
    if {$relative_end <= $threshold_ticks} {
      incr objects
      set bytes [expr {$bytes + [dict get $terminal bytes_completed]}]
      set fragments [expr {$fragments + [dict get $terminal fragments_completed]}]
      set lane0 [expr {$lane0 + [dict get $terminal lane0_fragments]}]
      set lane1 [expr {$lane1 + [dict get $terminal lane1_fragments]}]
      set replicated [expr {$replicated + [dict get $terminal replicated_fragments]}]
      set fallbacks [expr {$fallbacks + [dict get $terminal fallback_count]}]
      set p6_retries [expr {$p6_retries + [dict get $terminal p6_retry_count]}]
      set p6_retry_exhausted [expr {$p6_retry_exhausted + [dict get $terminal p6_retry_exhausted]}]
      set p6_tx_fail [expr {$p6_tx_fail + [dict get $terminal p6_tx_fail]}]
      set p6_crc_bad [expr {$p6_crc_bad + [dict get $terminal p6_crc_bad]}]
      set p6_payload_mismatch [expr {$p6_payload_mismatch + [dict get $terminal p6_payload_mismatch]}]
      set duty_violations [expr {$duty_violations + [dict get $terminal duty_violations]}]
      if {[dict get $terminal max_txd_high_cycles] > $max_txd_high} {
        set max_txd_high [dict get $terminal max_txd_high_cycles]
      }
      set last_object [dict get $terminal object_id]
      if {$relative_end > $previous_threshold_ticks} {
        lappend interval_latencies [expr {[dict get $terminal end_ticks] - [dict get $terminal start_ticks]}]
      }
    }
  }
  set previous_bytes 0
  foreach terminal $records {
    set relative_end [expr {[dict get $terminal end_ticks] - $runtime_start_ticks}]
    if {$relative_end <= $previous_threshold_ticks} {
      set previous_bytes [expr {$previous_bytes + [dict get $terminal bytes_completed]}]
    }
  }
  set interval_ticks [expr {$threshold_ticks - $previous_threshold_ticks}]
  if {$interval_ticks <= 0} { error "P7 stationary canonical sample interval is not positive" }
  set rolling_bps [expr {(($bytes - $previous_bytes) * 8 * $counts_per_second) / $interval_ticks}]
  set current_bps [expr {$threshold_ticks > 0 ? ($bytes * 8 * $counts_per_second) / $threshold_ticks : 0}]
  return [dict create objects $objects bytes $bytes fragments $fragments lane0 $lane0 lane1 $lane1 \
      replicated $replicated fallbacks $fallbacks p6_retries $p6_retries \
      p6_retry_exhausted $p6_retry_exhausted p6_tx_fail $p6_tx_fail p6_crc_bad $p6_crc_bad \
      p6_payload_mismatch $p6_payload_mismatch duty_violations $duty_violations \
      max_txd_high $max_txd_high last_object $last_object rolling_bps $rolling_bps \
      current_bps $current_bps latency [p7_latency_summary $interval_latencies]]
}

proc p7_emit_stationary_sample {result_handle sequence records runtime_start_ticks \
    threshold_ticks observation_not_before_ticks interval_ticks counts_per_second calibration_ticks} {
  set previous_threshold_ticks [expr {$threshold_ticks - $interval_ticks}]
  set canonical [p7_stationary_sample_from_ledger $records $runtime_start_ticks \
      $threshold_ticks $previous_threshold_ticks $counts_per_second]
  set sample_elapsed_sec [expr {double($threshold_ticks) / double($counts_per_second)}]
  set bytes_completed [dict get $canonical bytes]
  set bytes_low [expr {$bytes_completed & 0xFFFFFFFF}]
  set bytes_high [expr {($bytes_completed >> 32) & 0xFFFFFFFF}]
  set queue_occupancy [p7_read32 0x00020014]
  set queue_high_watermark [p7_read32 0x00020018]
  set backpressure_events [p7_read32 0x0002001C]
  set window [expr {$threshold_ticks <= $calibration_ticks ? "CALIBRATION" : "ACCEPTANCE"}]
  set latency [dict get $canonical latency]
  set sample_fields [list \
      [format "ELAPSED_%.3f" $sample_elapsed_sec] "ELAPSED_TICKS_$threshold_ticks" \
      "WINDOW_$window" "OBJECTS_[dict get $canonical objects]" "FAILED_0" \
      [format "BYTES_HI_%08X" $bytes_high] [format "BYTES_LO_%08X" $bytes_low] \
      "FRAGMENTS_[dict get $canonical fragments]" "LANE0_[dict get $canonical lane0]" \
      "LANE1_[dict get $canonical lane1]" "REPLICATED_[dict get $canonical replicated]" \
      "FALLBACKS_[dict get $canonical fallbacks]" "P6_RETRIES_[dict get $canonical p6_retries]" \
      "P6_RETRY_EXHAUSTED_[dict get $canonical p6_retry_exhausted]" \
      "P6_TX_FAIL_[dict get $canonical p6_tx_fail]" "P6_CRC_BAD_[dict get $canonical p6_crc_bad]" \
      "P6_PAYLOAD_MISMATCH_[dict get $canonical p6_payload_mismatch]" \
      "MAX_TXD_HIGH_[dict get $canonical max_txd_high]" \
      "DUTY_VIOLATIONS_[dict get $canonical duty_violations]" \
      "QUEUE_OCCUPANCY_$queue_occupancy" "QUEUE_HIGH_$queue_high_watermark" \
      "BACKPRESSURE_$backpressure_events" \
      "QUEUE_OBS_NOT_BEFORE_TICKS_$observation_not_before_ticks" \
      "CURRENT_BPS_[dict get $canonical current_bps]" \
      "ROLLING_BPS_[dict get $canonical rolling_bps]" \
      "LATENCY_COUNT_[dict get $latency count]" \
      "LATENCY_MIN_TICKS_[dict get $latency min]" "LATENCY_MEAN_TICKS_[dict get $latency mean]" \
      "LATENCY_P50_TICKS_[dict get $latency p50]" "LATENCY_P95_TICKS_[dict get $latency p95]" \
      "LATENCY_P99_TICKS_[dict get $latency p99]" "LATENCY_MAX_TICKS_[dict get $latency max]" \
      "LAST_OBJECT_[dict get $canonical last_object]"]
  p7_say $result_handle [format "P7_SAMPLE_%05d=%s" $sequence [join $sample_fields ,]]
  return $canonical
}

set result_file ""
set result_partial ""
set result_handle ""
set connected 0
set candidate_programmed 0
set processor_started 0
set mode UNKNOWN

set rc [catch {
  if {[llength $argv] != 18} { error "P7 PS executor requires exactly 18 arguments" }
  set root_dir [file normalize [lindex $argv 0]]
  set authorization_file [file normalize [lindex $argv 1]]
  set preflight_file [file normalize [lindex $argv 2]]
  set bit_file [file normalize [lindex $argv 3]]
  set elf_file [file normalize [lindex $argv 4]]
  set ps7_init_file [file normalize [lindex $argv 5]]
  set bundle_dir [file normalize [lindex $argv 6]]
  set plan_file [file normalize [lindex $argv 7]]
  set result_file [file normalize [lindex $argv 8]]
  set hw_server_url [lindex $argv 9]
  set expected_board_id [lindex $argv 10]
  set expected_part [lindex $argv 11]
  set expected_target [lindex $argv 12]
  set max_runtime_sec [lindex $argv 13]
  set mode [lindex $argv 14]
  set idle_margin_sec [lindex $argv 15]
  set shutdown_bit [file normalize [lindex $argv 16]]
  set counts_per_second [lindex $argv 17]
  set result_partial "${result_file}.write_partial"

  if {![info exists ::env(RF_COMM_HW_AUTH)] ||
      $::env(RF_COMM_HW_AUTH) ne "P7_STATIONARY_APP_LAYER_APPROVED"} {
    error "RF_COMM_HW_AUTH=P7_STATIONARY_APP_LAYER_APPROVED required"
  }
  if {$mode ni {functional fault-fallback queue abort-restart stationary}} {
    error "unsupported P7 PS mode: $mode"
  }
  if {![string is integer -strict $max_runtime_sec] ||
      $max_runtime_sec < 1 || $max_runtime_sec > 1800} {
    error "P7 service runtime must be in 1..1800 seconds"
  }
  if {![string is integer -strict $idle_margin_sec] ||
      $idle_margin_sec < 5 || $idle_margin_sec > 60} {
    error "P7 idle deadline margin must be in 5..60 seconds"
  }
  if {![string is integer -strict $counts_per_second] || $counts_per_second != 333333343} {
    error "P7 PS COUNTS_PER_SECOND must equal the authorized BSP value 333333343"
  }
  set local_server_ok 0
  if {[regexp -nocase {^(tcp:)?(localhost|127[.]0[.]0[.]1):([0-9]+)$} \
      $hw_server_url all protocol host server_port]} {
    if {$server_port >= 1 && $server_port <= 65535} { set local_server_ok 1 }
  }
  if {!$local_server_ok} { error "P7 XSDB server URL must be local with a valid port" }
  set xsdb_url $hw_server_url
  if {![string match -nocase "tcp:*" $xsdb_url]} { set xsdb_url "tcp:$xsdb_url" }

  set authorization_root [file normalize [file join $root_dir .hardware_authorization]]
  set auth_slash [string map {\ /} $authorization_file]
  set auth_root_slash [string trimright [string map {\ /} $authorization_root] "/"]
  if {![string match -nocase "${auth_root_slash}/*" $auth_slash]} {
    error "P7 authorization file must be under .hardware_authorization"
  }
  set abort_file [file join $authorization_root ABORT_NOW.txt]
  if {[file exists $abort_file]} { error "P7 abort file is present" }
  foreach required [list $authorization_file $preflight_file $bit_file $elf_file \
      $ps7_init_file $plan_file $shutdown_bit \
      [file join $bundle_dir mailbox.bin] [file join $bundle_dir descriptors.bin]] {
    if {![file isfile $required]} { error "P7 PS required file missing: $required" }
  }
  if {![file isdirectory [file dirname $result_file]]} { error "P7 result directory missing" }
  if {[file dirname $plan_file] ne $bundle_dir} { error "P7 plan must be inside the fixed bundle directory" }
  if {[file size [file join $bundle_dir mailbox.bin]] != 256} {
    error "P7 mailbox image must contain exactly 256 bytes"
  }
  if {[file size [file join $bundle_dir descriptors.bin]] != 2048} {
    error "P7 descriptor table must contain exactly 2048 bytes"
  }
  if {$mode eq "queue"} {
    foreach queue_mailbox [list [file join $bundle_dir mailbox_queue_depth_1.bin] \
        [file join $bundle_dir mailbox_queue_depth_8_stop.bin]] {
      if {![file isfile $queue_mailbox] || [file size $queue_mailbox] != 256} {
        error "P7 queue phase mailbox is missing or not exactly 256 bytes"
      }
    }
    foreach {candidate_name candidate_size} [list \
        queue_overflow_candidate_input.bin 777 \
        queue_overflow_candidate_output_zero.bin 777 \
        queue_overflow_candidate_trace_zero.bin 256 \
        queue_overflow_candidate_descriptor_free.bin 256] {
      set candidate_path [file join $bundle_dir $candidate_name]
      if {![file isfile $candidate_path] || [file size $candidate_path] != $candidate_size} {
        error "P7 queue overflow candidate artifact is missing or has wrong size: $candidate_name"
      }
    }
    set candidate_handle [open [file join $bundle_dir queue_overflow_candidate_descriptor_free.bin] rb]
    fconfigure $candidate_handle -translation binary
    set candidate_descriptor [read $candidate_handle]
    close $candidate_handle
    if {[p7_le32 $candidate_descriptor 0] != 0x53443750 ||
        [p7_le32 $candidate_descriptor 4] != 1 ||
        [p7_le32 $candidate_descriptor 8] != 1 ||
        [p7_le32 $candidate_descriptor 12] != 0 ||
        [p7_le32 $candidate_descriptor 16] != 0x50370001 ||
        [p7_le32 $candidate_descriptor 20] != 9 ||
        [p7_le32 $candidate_descriptor 24] != 0x10100000 ||
        [p7_le32 $candidate_descriptor 28] != 0x10900000 ||
        [p7_le32 $candidate_descriptor 32] != 777 ||
        [p7_le32 $candidate_descriptor 40] != 3 ||
        [p7_le32 $candidate_descriptor 60] != 0x11100000 ||
        [p7_le32 $candidate_descriptor 64] != 4} {
      error "P7 queue overflow candidate descriptor is not the valid distinct object 9"
    }
  }
  if {$mode eq "functional"} {
    foreach {checkpoint_name checkpoint_size} [list \
        functional_checkpoint_4k_input.bin 4096 \
        functional_checkpoint_4k_output_zero.bin 4096 \
        functional_checkpoint_4k_trace_zero.bin 1280 \
        functional_checkpoint_4k_descriptor_free.bin 256] {
      set checkpoint_path [file join $bundle_dir $checkpoint_name]
      if {![file isfile $checkpoint_path] || [file size $checkpoint_path] != $checkpoint_size} {
        error "P7 functional 4KiB checkpoint artifact is missing/invalid: $checkpoint_name"
      }
    }
    set checkpoint_handle [open [file join $bundle_dir functional_checkpoint_4k_descriptor_free.bin] rb]
    fconfigure $checkpoint_handle -translation binary
    set checkpoint_descriptor [read $checkpoint_handle]
    close $checkpoint_handle
    if {[p7_le32 $checkpoint_descriptor 0] != 0x53443750 ||
        [p7_le32 $checkpoint_descriptor 4] != 1 ||
        [p7_le32 $checkpoint_descriptor 8] != 1 ||
        [p7_le32 $checkpoint_descriptor 12] != 0 ||
        [p7_le32 $checkpoint_descriptor 16] != 0x50370001 ||
        [p7_le32 $checkpoint_descriptor 20] != 49 ||
        [p7_le32 $checkpoint_descriptor 24] != 0x00100000 ||
        [p7_le32 $checkpoint_descriptor 28] != 0x00900000 ||
        [p7_le32 $checkpoint_descriptor 32] != 4096 ||
        [p7_le32 $checkpoint_descriptor 40] != 3 ||
        [p7_le32 $checkpoint_descriptor 60] != 0x01100000 ||
        [p7_le32 $checkpoint_descriptor 64] != 20} {
      error "P7 functional 4KiB stripe checkpoint descriptor identity is invalid"
    }
  }

  set auth_handle [open $authorization_file r]
  set auth_text [read $auth_handle]
  close $auth_handle
  if {![p7_has_marker $auth_text P7_STATIONARY_APP_LAYER_APPROVED]} { error "P7 authorization marker missing" }
  p7_require_value $auth_text AUTHORIZED_STAGE P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET
  p7_require_value $auth_text USER_HARDWARE_AUTHORIZATION_FOR_P7 GRANTED
  p7_require_value $auth_text BOARD_ID $expected_board_id
  p7_require_value $auth_text EXPECTED_PART $expected_part
  p7_require_value $auth_text EXPECTED_TARGET $expected_target
  p7_require_value $auth_text SHUTDOWN_ON_EXIT required
  p7_require_value $auth_text NO_ETHERNET true
  p7_require_value $auth_text NO_MOTION true
  p7_require_value $auth_text LANE_COUNT 2
  p7_require_value $auth_text MAX_LANE_MASK 0x3
  p7_require_value $auth_text P7_PS_MODE $mode
  p7_require_value $auth_text P7_PS_CORE_READINESS PASS
  p7_require_value $auth_text P7_COUNTS_PER_SECOND $counts_per_second
  p7_require_path $auth_text BITSTREAM_PATH $bit_file
  p7_require_path $auth_text ELF_PATH $elf_file
  p7_require_path $auth_text PS7_INIT_PATH $ps7_init_file
  p7_require_path $auth_text SHUTDOWN_BITSTREAM_PATH $shutdown_bit
  set auth_runtime [p7_auth_value $auth_text MAX_RUNTIME_SEC]
  if {![string is integer -strict $auth_runtime] ||
      $auth_runtime < $max_runtime_sec || $auth_runtime > 1800} {
    error "P7 authorization runtime is invalid or lower than requested"
  }

  set preflight_handle [open $preflight_file r]
  set preflight_text [read $preflight_handle]
  close $preflight_handle
  foreach {key expected} [list \
      P7_HW_PREFLIGHT_RESULT PASS \
      P7_HW_PREFLIGHT_AUTHORIZED 1 \
      P7_HW_PREFLIGHT_READ_ONLY 1 \
      P7_HW_PREFLIGHT_BOARD_ID $expected_board_id \
      P7_HW_PREFLIGHT_PART $expected_part \
      P7_HW_PREFLIGHT_TARGET $expected_target] {
    if {[p7_marker_value $preflight_text $key] ne $expected} {
      error "P7 preflight attestation mismatch: $key"
    }
  }

  # Parse the fixed execution-plan grammar before any XSDB connection.
  set plan_handle [open $plan_file r]
  set plan_lines [split [read $plan_handle] "\n"]
  close $plan_handle
  set meaningful {}
  foreach raw_line $plan_lines {
    set line [string trim $raw_line]
    if {$line eq "" || [string match "#*" $line]} { continue }
    if {![regexp {^[ -~]+$} $line]} { error "P7 plan contains non-ASCII/non-printable data" }
    lappend meaningful $line
  }
  if {[llength $meaningful] < 10 || [lindex $meaningful 0] ne "P7_PS_EXECUTION_PLAN_V1" ||
      [lindex $meaningful end] ne "END"} {
    error "P7 execution plan magic/END boundary invalid"
  }
  array set plan_value {}
  array set case_input {}
  array set case_output {}
  array set case_length {}
  array set case_trace {}
  array set case_trace_capacity {}
  array set case_session {}
  array set case_object {}
  array set case_expected_status {}
  array set case_expected_error {}
  array set case_lane_policy {}
  array set case_unavailable_mask {}
  array set case_unavailable_after {}
  array set boundary_input {}
  array set boundary_output {}
  array set boundary_length {}
  array set boundary_trace {}
  array set boundary_trace_capacity {}
  array set boundary_session {}
  array set boundary_object {}
  array set boundary_expected_status {}
  array set boundary_expected_error {}
  array set boundary_lane_policy {}
  array set boundary_ring_slot {}
  set parsed_cases 0
  set parsed_boundaries 0
  foreach line [lrange $meaningful 1 end-1] {
    set fields [regexp -all -inline {\S+} $line]
    set key [lindex $fields 0]
    if {$key eq "CASE" || $key eq "BOUNDARY"} {
      if {[llength $fields] != 14} { error "P7 CASE line must contain exactly 14 fields" }
      set slot [lindex $fields 1]
      set expected_slot [expr {$key eq "CASE" ? $parsed_cases : $parsed_boundaries}]
      set slot_limit [expr {$key eq "CASE" ? 8 : 48}]
      if {![string is integer -strict $slot] || $slot != $expected_slot || $slot < 0 || $slot >= $slot_limit} {
        error "P7 CASE/BOUNDARY logical slots are not contiguous/in range"
      }
      set ring_slot [expr {$key eq "CASE" ? $slot : $slot % 8}]
      set input_address [p7_parse_hex32 [lindex $fields 2] input_address]
      set output_address [p7_parse_hex32 [lindex $fields 3] output_address]
      set length [lindex $fields 4]
      set trace_address [p7_parse_hex32 [lindex $fields 5] trace_address]
      set trace_capacity [lindex $fields 6]
      set session [p7_parse_hex32 [lindex $fields 7] session_epoch]
      set object_id [lindex $fields 8]
      set expected_status [lindex $fields 9]
      set expected_error [lindex $fields 10]
      set lane_policy [lindex $fields 11]
      set unavailable_mask [lindex $fields 12]
      set unavailable_after [lindex $fields 13]
      foreach value [list $length $trace_capacity $object_id $expected_status $expected_error \
          $lane_policy $unavailable_mask $unavailable_after] {
        if {![string is integer -strict $value]} { error "P7 CASE decimal field is invalid" }
      }
      if {$length < 0 || $length > 8388608 || $trace_capacity < 1 ||
          $expected_status < 3 || $expected_status > 6 || $expected_error < 0 ||
          $lane_policy < 1 || $lane_policy > 4 || $unavailable_mask < 0 ||
          $unavailable_mask > 3 || $unavailable_after < 0 ||
          $unavailable_after > $trace_capacity} {
        error "P7 CASE bounds are invalid"
      }
      foreach address [list $input_address $output_address $trace_address] {
        if {$address < 0x00100000 || $address >= 0x20000000 || $address % 64 != 0} {
          error "P7 CASE DDR address is out of range/alignment"
        }
      }
      set slot_base [expr {0x00100000 + 0x02000000 * $ring_slot}]
      set slot_end [expr {$slot_base + 0x02000000}]
      set expected_input $slot_base
      set expected_output [expr {$slot_base + 0x00800000}]
      set expected_trace [expr {$slot_base + 0x01000000}]
      if {$input_address != $expected_input || $output_address != $expected_output ||
          $trace_address != $expected_trace} {
        error "P7 CASE address does not match fixed slot geometry"
      }
      set input_end [expr {$input_address + $length}]
      set output_end [expr {$output_address + $length}]
      set trace_bytes [expr {$trace_capacity * 64}]
      set trace_end [expr {$trace_address + $trace_bytes}]
      if {$input_end < $input_address || $output_end < $output_address ||
          $trace_end < $trace_address || $input_end > $output_address ||
          $output_end > $trace_address || $trace_end > $slot_end ||
          $trace_end > 0x20000000} {
        error "P7 CASE range crosses or overlaps its fixed DDR slot"
      }
      if {$key eq "CASE"} {
        set input_file [file join $bundle_dir "input_${slot}.bin"]
        set output_file [file join $bundle_dir "output_zero_${slot}.bin"]
        set trace_file [file join $bundle_dir "trace_zero_${slot}.bin"]
        set free_file [file join $bundle_dir "descriptor_free_${slot}.bin"]
      } else {
        set input_file [file join $bundle_dir "boundary_${slot}_input.bin"]
        set output_file [file join $bundle_dir "boundary_${slot}_output_zero.bin"]
        set trace_file [file join $bundle_dir "boundary_${slot}_trace_zero.bin"]
        set free_file [file join $bundle_dir "boundary_${slot}_descriptor_free.bin"]
      }
      foreach required [list $input_file $output_file $trace_file $free_file] {
        if {![file isfile $required]} { error "P7 bundle case file missing: $required" }
      }
      if {[file size $input_file] != $length || [file size $output_file] != $length ||
          [file size $trace_file] != $trace_bytes || [file size $free_file] != 256} {
        error "P7 bundle case file size does not match the fixed plan"
      }
      if {$key eq "CASE"} {
        set case_input($slot) $input_address
        set case_output($slot) $output_address
        set case_length($slot) $length
        set case_trace($slot) $trace_address
        set case_trace_capacity($slot) $trace_capacity
        set case_session($slot) $session
        set case_object($slot) $object_id
        set case_expected_status($slot) $expected_status
        set case_expected_error($slot) $expected_error
        set case_lane_policy($slot) $lane_policy
        set case_unavailable_mask($slot) $unavailable_mask
        set case_unavailable_after($slot) $unavailable_after
        incr parsed_cases
      } else {
        set boundary_input($slot) $input_address
        set boundary_output($slot) $output_address
        set boundary_length($slot) $length
        set boundary_trace($slot) $trace_address
        set boundary_trace_capacity($slot) $trace_capacity
        set boundary_session($slot) $session
        set boundary_object($slot) $object_id
        set boundary_expected_status($slot) $expected_status
        set boundary_expected_error($slot) $expected_error
        set boundary_lane_policy($slot) $lane_policy
        set boundary_ring_slot($slot) $ring_slot
        incr parsed_boundaries
      }
    } else {
      if {[llength $fields] != 2 || [info exists plan_value($key)]} {
        error "P7 plan key is duplicate or malformed: $key"
      }
      if {$key ni {MODE MAX_RUNTIME_SECONDS CALIBRATION_SECONDS ACCEPTANCE_SECONDS \
          SAMPLE_INTERVAL_SECONDS IDLE_MARGIN_SECONDS SCHEDULING_CUTOFF_SECONDS COUNTS_PER_SECOND CASE_COUNT BOUNDARY_COUNT CHECKPOINT_COUNT}} {
        error "unsupported P7 plan key: $key"
      }
      set plan_value($key) [lindex $fields 1]
    }
  }
  foreach key {MODE MAX_RUNTIME_SECONDS CALIBRATION_SECONDS ACCEPTANCE_SECONDS SAMPLE_INTERVAL_SECONDS IDLE_MARGIN_SECONDS SCHEDULING_CUTOFF_SECONDS COUNTS_PER_SECOND CASE_COUNT BOUNDARY_COUNT CHECKPOINT_COUNT} {
    if {![info exists plan_value($key)]} { error "P7 plan field missing: $key" }
  }
  foreach key {MAX_RUNTIME_SECONDS CALIBRATION_SECONDS ACCEPTANCE_SECONDS SAMPLE_INTERVAL_SECONDS IDLE_MARGIN_SECONDS SCHEDULING_CUTOFF_SECONDS COUNTS_PER_SECOND CASE_COUNT BOUNDARY_COUNT CHECKPOINT_COUNT} {
    if {![string is integer -strict $plan_value($key)]} {
      error "P7 plan numeric field is invalid: $key"
    }
  }
  if {$plan_value(MODE) ne $mode || $plan_value(MAX_RUNTIME_SECONDS) != $max_runtime_sec ||
      $plan_value(IDLE_MARGIN_SECONDS) != $idle_margin_sec ||
      $plan_value(COUNTS_PER_SECOND) != $counts_per_second ||
      $plan_value(CASE_COUNT) != $parsed_cases || $plan_value(BOUNDARY_COUNT) != $parsed_boundaries ||
      $plan_value(CHECKPOINT_COUNT) != [expr {$mode eq "functional" ? 1 : 0}]} {
    error "P7 plan does not match authorized wrapper controls"
  }
  if {$parsed_cases < 1 || $parsed_cases > 8} { error "P7 plan case count must be in 1..8" }
  if {$mode eq "stationary"} {
    if {$max_runtime_sec != 1800 || $plan_value(CALIBRATION_SECONDS) != 300 ||
        $plan_value(ACCEPTANCE_SECONDS) != 1500 ||
        $plan_value(SAMPLE_INTERVAL_SECONDS) != 30 ||
        $idle_margin_sec != 60 ||
        $plan_value(CALIBRATION_SECONDS) + $plan_value(ACCEPTANCE_SECONDS) != 1800 ||
        $plan_value(SCHEDULING_CUTOFF_SECONDS) != 1800 - $idle_margin_sec} {
      error "P7 stationary schedule must be 300+1500 with an idle deadline margin"
    }
    if {$parsed_cases != 8} { error "P7 stationary mode requires exactly eight slots" }
    set required_stationary_policies {1 3 3 2 4 3 1 2}
    foreach slot [lsort -integer [array names case_lane_policy]] {
      if {$case_lane_policy($slot) != [lindex $required_stationary_policies $slot]} {
        error "P7 stationary lane0/lane1/stripe/replicate policy matrix is incomplete"
      }
      if {$slot == 1} {
        if {$case_unavailable_mask($slot) != 1 || $case_unavailable_after($slot) != 2} {
          error "P7 stationary lane0 controlled-fallback case is missing"
        }
      } elseif {$slot == 2} {
        if {$case_unavailable_mask($slot) != 2 || $case_unavailable_after($slot) != 2} {
          error "P7 stationary lane1 controlled-fallback case is missing"
        }
      } elseif {$case_unavailable_mask($slot) != 0} {
        error "P7 stationary unexpected fault-injection slot"
      }
    }
  } elseif {$plan_value(CALIBRATION_SECONDS) != 0 || $plan_value(ACCEPTANCE_SECONDS) != 0} {
    error "non-stationary plan cannot claim calibration/acceptance windows"
  }
  if {$mode eq "functional"} {
    if {$parsed_cases != 8 || $case_lane_policy(0) != 1 || $case_lane_policy(1) != 2 ||
        $case_lane_policy(2) != 3 || $case_lane_policy(3) != 4} {
      error "P7 functional lane0/lane1/stripe/replicate matrix is incomplete"
    }
    foreach slot {0 1 2 3 4 5 6 7} {
      set expected_length [expr {$slot < 4 ? 1048576 : 65536}]
      set expected_object [expr {$slot < 4 ? 54 + $slot : 50 + $slot - 4}]
      if {$case_length($slot) != $expected_length || $case_object($slot) != $expected_object ||
          $case_session($slot) != 0x50370001} {
        error "P7 functional 64KiB/1MiB risk-order identity matrix mismatch"
      }
    }
    if {$parsed_boundaries != 48} {
      error "P7 functional hardware boundary descriptor phase is incomplete"
    }
    for {set batch 0} {$batch < 6} {incr batch} {
      set batch_path [file join $bundle_dir "boundary_batch_${batch}_descriptors.bin"]
      if {![file isfile $batch_path] || [file size $batch_path] != 2048} {
        error "P7 functional boundary descriptor batch is missing/invalid: $batch"
      }
    }
    set required_boundary_lengths {0 1 30 214 215 216 247 248 430 431 432 1024}
    for {set boundary_index 0} {$boundary_index < 48} {incr boundary_index} {
      set size_index [expr {$boundary_index / 4}]
      set expected_policy [expr {1 + ($boundary_index % 4)}]
      if {$boundary_length($boundary_index) != [lindex $required_boundary_lengths $size_index] ||
          $boundary_lane_policy($boundary_index) != $expected_policy ||
          $boundary_ring_slot($boundary_index) != $boundary_index % 8 ||
          $boundary_object($boundary_index) != 1 + $boundary_index ||
          $boundary_session($boundary_index) != 0x50370001} {
        error "P7 functional 12-size x 4-policy boundary matrix mismatch"
      }
    }
  } elseif {$parsed_boundaries != 0} {
    error "P7 non-functional mode cannot carry functional boundary cases"
  } elseif {$mode eq "fault-fallback"} {
    if {$parsed_cases != 7 || $case_lane_policy(0) != 3 || $case_unavailable_mask(0) != 1 ||
        $case_lane_policy(1) != 3 || $case_unavailable_mask(1) != 2 ||
        $case_lane_policy(2) != 4 || $case_unavailable_mask(2) != 1 ||
        $case_lane_policy(3) != 4 || $case_unavailable_mask(3) != 2 ||
        $case_lane_policy(4) != 1 || $case_unavailable_mask(4) != 1 ||
        $case_lane_policy(5) != 2 || $case_unavailable_mask(5) != 2 ||
        $case_unavailable_mask(6) != 3} {
      error "P7 fault/fallback positive and strict-policy negative matrix is incomplete"
    }
  } elseif {$mode eq "queue" && $parsed_cases != 8} {
    error "P7 queue mode requires the full eight-entry queue"
  } elseif {$mode eq "abort-restart" && $parsed_cases != 3} {
    error "P7 abort/restart mode requires abort, new-epoch retransmit, and duplicate replay cases"
  }

  set preflight_device [p7_marker_value $preflight_text P7_HW_PREFLIGHT_DEVICE]
  set preflight_idcode [p7_marker_value $preflight_text P7_HW_PREFLIGHT_IDCODE]
  if {![regexp -nocase {^[a-z0-9_.-]+$} $preflight_device] ||
      ![regexp -nocase {^(0x)?[0-9a-f]+$} $preflight_idcode]} {
    error "P7 preflight device/IDCODE identity is missing or malformed"
  }

  catch {file delete -force $result_partial}
  set result_handle [open $result_partial w]
  p7_say $result_handle "P7_PS_MODE=$mode"
  if {$mode eq "fault-fallback"} {
    p7_say $result_handle "P7_FAULT_MODEL=SOFTWARE_INJECTED_SCHEDULER_FAULT"
  }
  if {$mode eq "stationary"} {
    p7_say $result_handle "P7_STATIONARY_FAULT_MODEL=SOFTWARE_INJECTED_BIDIRECTIONAL_CONTROLLED_FALLBACK"
  }

  # No XSDB connection or hardware command may occur before the checks above.
  connect -url $xsdb_url
  set connected 1
  set device_root [lindex [split $preflight_device _] 0]
  if {![string match -nocase "${device_root}*" $expected_part]} {
    error "P7 expected part is inconsistent with the preflight device root"
  }
  if {[string first [string tolower $expected_board_id] [string tolower $expected_target]] < 0} {
    error "P7 exact target does not contain the authorized board serial"
  }

  # Use the structured low-level JTAG target properties to bind the live
  # cable serial, device name and actual IDCODE.  Do not infer identity from
  # the human-readable `targets` listing.
  set live_jtag_properties [jtag targets -target-properties]
  set cable_matches {}
  set device_matches {}
  set expected_idcode_normal [p7_normal_idcode $preflight_idcode]
  foreach props $live_jtag_properties {
    if {[dict exists $props jtag_cable_serial] &&
        [string equal -nocase [dict get $props jtag_cable_serial] $expected_board_id] &&
        [dict exists $props level] && [dict get $props level] == 0} {
      lappend cable_matches $props
    }
    if {![dict exists $props idcode] || ![dict exists $props name]} { continue }
    if {[string equal -nocase [dict get $props name] $device_root] &&
        [p7_normal_idcode [dict get $props idcode]] eq $expected_idcode_normal} {
      lappend device_matches $props
    }
  }
  if {[llength $cable_matches] != 1} {
    error "P7 XSDB live chain must contain exactly one authorized cable serial; found [llength $cable_matches]"
  }
  if {[llength $device_matches] != 1} {
    error "P7 XSDB live chain must contain exactly one exact device/IDCODE match; found [llength $device_matches]"
  }
  set live_device [lindex $device_matches 0]
  set live_cable [lindex $cable_matches 0]
  set live_jtag_device_id [dict get $live_device node_id]
  set live_device_name [dict get $live_device name]
  set live_board_serial [dict get $live_cable jtag_cable_serial]
  set live_idcode [p7_normal_idcode [dict get $live_device idcode]]

  # Resolve every high-level XSDB node once, require uniqueness on the exact
  # verified JTAG device/cable, and subsequently select by numeric target ID.
  set debug_properties [targets -target-properties]
  set dap_matches {}
  set apu_matches {}
  set fpga_matches {}
  set cpu_matches {}
  foreach props $debug_properties {
    if {![dict exists $props jtag_device_id] ||
        [dict get $props jtag_device_id] != $live_jtag_device_id ||
        ![dict exists $props jtag_cable_serial] ||
        ![string equal -nocase [dict get $props jtag_cable_serial] $expected_board_id] ||
        ![dict exists $props name] || ![dict exists $props target_id]} { continue }
    set live_name [dict get $props name]
    if {[string match -nocase "*DAP*" $live_name]} { lappend dap_matches $props }
    if {[string equal -nocase $live_name APU]} { lappend apu_matches $props }
    if {[string equal -nocase $live_name $device_root]} { lappend fpga_matches $props }
    if {[string match -nocase "*Cortex-A9*#0" $live_name]} { lappend cpu_matches $props }
  }
  if {[llength $dap_matches] == 1} {
    set reset_target [lindex $dap_matches 0]
    set reset_target_name DAP
  } elseif {[llength $dap_matches] == 0 && [llength $apu_matches] == 1} {
    set reset_target [lindex $apu_matches 0]
    set reset_target_name APU
  } else {
    error "P7 XSDB reset target is not unique on the exact authorized device"
  }
  if {[llength $fpga_matches] != 1 || [llength $cpu_matches] != 1} {
    error "P7 XSDB FPGA/CPU#0 targets are not unique on the exact authorized device"
  }
  set fpga_target [lindex $fpga_matches 0]
  set cpu_target [lindex $cpu_matches 0]

  targets [dict get $reset_target target_id]
  p7_say $result_handle "P7_PS_RESET_TARGET=$reset_target_name"
  rst -system
  after 1000
  targets [dict get $fpga_target target_id]
  p7_say $result_handle "P7_HW_TARGET=$expected_target"
  p7_say $result_handle "P7_HW_PART=$expected_part"
  p7_say $result_handle "P7_HW_BOARD_ID=$expected_board_id"
  p7_say $result_handle "P7_XSDB_LIVE_DEVICE=$live_device_name"
  p7_say $result_handle "P7_XSDB_LIVE_DEVICE_MATCH=1"
  p7_say $result_handle "P7_XSDB_LIVE_BOARD_ID=$live_board_serial"
  p7_say $result_handle "P7_XSDB_LIVE_IDCODE=0x[string toupper $live_idcode]"
  p7_say $result_handle "P7_XSDB_PREFLIGHT_IDCODE=$preflight_idcode"
  p7_say $result_handle "P7_XSDB_TARGET_SELECTION=EXACT_CABLE_DEVICE_IDCODE_AND_UNIQUE_NODE_IDS"
  fpga -file $bit_file
  set candidate_programmed 1
  p7_say $result_handle "P7_PS_CANDIDATE_PROGRAMMED=1"
  after 1000

  targets [dict get $cpu_target target_id]
  source $ps7_init_file
  ps7_init
  ps7_post_config
  rst -processor

  set host_input_start_ms [clock milliseconds]
  set host_input_bytes 0
  foreach slot [lsort -integer [array names case_input]] {
    set input_file [file join $bundle_dir "input_${slot}.bin"]
    if {$case_length($slot) > 0} {
      dow -data $input_file $case_input($slot)
      set host_input_bytes [expr {$host_input_bytes + $case_length($slot)}]
    }
  }
  set host_input_duration_ms [expr {[clock milliseconds] - $host_input_start_ms}]
  if {$host_input_duration_ms < 1} { set host_input_duration_ms 1 }
  set host_input_bytes_per_sec [expr {($host_input_bytes * 1000) / $host_input_duration_ms}]
  set host_input_bps [expr {($host_input_bytes * 8000) / $host_input_duration_ms}]
  p7_say $result_handle "P7_HOST_TO_PS_INPUT_BYTES=$host_input_bytes"
  p7_say $result_handle "P7_HOST_TO_PS_INPUT_DURATION_MS=$host_input_duration_ms"
  p7_say $result_handle "P7_HOST_TO_PS_INPUT_BYTES_PER_SEC=$host_input_bytes_per_sec"
  p7_say $result_handle "P7_HOST_TO_PS_INPUT_BPS=$host_input_bps"
  foreach slot [lsort -integer [array names case_input]] {
    if {$case_length($slot) > 0} {
      dow -data [file join $bundle_dir "output_zero_${slot}.bin"] $case_output($slot)
    }
    dow -data [file join $bundle_dir "trace_zero_${slot}.bin"] $case_trace($slot)
  }
  set initial_mailbox [file join $bundle_dir mailbox.bin]
  if {$mode eq "queue"} { set initial_mailbox [file join $bundle_dir mailbox_queue_depth_1.bin] }
  dow -data $initial_mailbox 0x00020000
  dow -data [file join $bundle_dir descriptors.bin] 0x00020100
  dow $elf_file
  p7_say $result_handle "P7_PS_ELF_DOWNLOADED=1"
  con
  set processor_started 1
  set service_start_ms [clock milliseconds]
  p7_wait_service_ready $abort_file $result_handle P7_PS_SERVICE
  if {$mode eq "stationary"} {
    p7_say $result_handle "P7_STATIONARY_SERVICE_READY_ACTIVE=1"
  }
  if {$mode eq "functional"} {
    # Risk-increasing functional order is handled below: boundary -> 4KiB -> 64KiB -> 1MiB.
  } elseif {$mode eq "queue" || $mode eq "abort-restart"} {
    p7_publish_phase_descriptors $bundle_dir {0}
  } elseif {$mode eq "fault-fallback"} {
    p7_publish_phase_descriptors $bundle_dir {0 1 2 3}
  } else {
    p7_publish_phase_descriptors $bundle_dir [lsort -integer [array names case_input]]
  }

  set requeue_after_cutoff 0
  set calibration_complete 0
    set acceptance_complete 0
    set drain_complete 0
  if {$mode eq "stationary"} {
    array set generation {}
    array set last_terminal {}
    foreach slot [array names case_input] {
      set generation($slot) 0
      set last_terminal($slot) 0
    }
    set next_object_id 1000
    set total_terminal 0
    set total_bytes_completed 0
    set total_fragments_completed 0
    set total_lane0_fragments 0
    set total_lane1_fragments 0
    set total_replicated_fragments 0
    set total_fallbacks 0
    set total_p6_retry_count 0
    set total_p6_retry_exhausted 0
    set total_p6_tx_fail 0
    set total_p6_crc_bad 0
    set total_p6_payload_mismatch 0
    set total_duty_violations 0
    set max_txd_high_cycles 0
    set last_completed_object_id 0
    set stationary_terminal_records {}
    set sample_index 0
    set sample_interval_ticks [expr {$plan_value(SAMPLE_INTERVAL_SECONDS) * $counts_per_second}]
    set next_sample_ticks $sample_interval_ticks
    set scheduling_cutoff_ticks [expr {$plan_value(SCHEDULING_CUTOFF_SECONDS) * $counts_per_second}]
    set ready_publish_guard_ticks $counts_per_second
    set drain_deadline_ticks [expr {1790 * $counts_per_second}]
    set calibration_ticks [expr {$plan_value(CALIBRATION_SECONDS) * $counts_per_second}]
    set required_runtime_ticks [expr {$max_runtime_sec * $counts_per_second}]
    set requeue_publish_count 0
    set requeue_blocked_at_cutoff_count 0
    set last_requeue_pre_ticks 0
    set last_requeue_post_ticks 0
    set runtime_start_ticks [expr {[p7_read32 0x0002006C] | ([p7_read32 0x00020070] << 32)}]
    if {$runtime_start_ticks <= 0} { error "P7 stationary runtime start tick is missing" }
    p7_say $result_handle "P7_STATIONARY_PRIMARY_TIME_SOURCE=PS_RUNTIME_ELAPSED_TICKS"
    p7_say $result_handle "P7_STATIONARY_HOST_TIME_ROLE=INDEPENDENT_WATCHDOG_AND_INPUT_PRELOAD"
    p7_say $result_handle "P7_STATIONARY_RUNTIME_START_TICKS=$runtime_start_ticks"
    p7_say $result_handle "P7_STATIONARY_READY_PUBLISH_GUARD_TICKS=$ready_publish_guard_ticks"
    p7_say $result_handle "P7_STATIONARY_SAMPLE_SEMANTICS=FIXED_PS_THRESHOLDS_FROM_IMMUTABLE_TERMINAL_END_TICKS"
    set wall_deadline_ms [expr {$service_start_ms + 1000 * $max_runtime_sec + 2000}]
    while {1} {
      p7_check_abort $abort_file
      set now_ms [clock milliseconds]
      set service_state [p7_read32 0x00020008]
      if {$service_state == 4 || $service_state == 5} {
        p7_mark_stationary_terminal $result_handle
        break
      }
      if {$now_ms >= $wall_deadline_ms} { error "P7 stationary service did not reach terminal state" }

      # Drain immutable terminal records before sampling.  No descriptor is
      # republished until a causal snapshot has been captured and a second
      # post-snapshot status scan proves that every completion at or before
      # that snapshot is represented in the ledger.
      set prepared_slots {}
      set terminal_during_snapshot 0
      while {1} {
        set terminal_candidates {}
        foreach slot [lsort -integer [array names case_input]] {
          set descriptor_address [expr {0x00020100 + 0x100 * $slot}]
          set status [p7_read32 [expr {$descriptor_address + 0x0C}]]
          if {$status >= 3 && $status <= 6 && !$last_terminal($slot)} {
            set completion_sequence [p7_read32 [expr {$descriptor_address + 0xFC}]]
            lappend terminal_candidates [list $completion_sequence $slot]
          }
        }
        foreach terminal_candidate [lsort -integer -index 0 $terminal_candidates] {
          lassign $terminal_candidate completion_sequence slot
          set descriptor_address [expr {0x00020100 + 0x100 * $slot}]
          if {$completion_sequence != $total_terminal + 1} {
            error "P7 stationary firmware completion sequence is not contiguous expected=[expr {$total_terminal + 1}] observed=$completion_sequence"
          }
          set error_code [p7_read32 [expr {$descriptor_address + 0x44}]]
          set status [p7_read32 [expr {$descriptor_address + 0x0C}]]
          if {$status != 3 || $error_code != 0} {
            error "P7 stationary descriptor failed slot=$slot status=$status error=$error_code"
          }
          incr total_terminal
          set terminal [p7_record_stationary_terminal $result_handle $total_terminal $slot \
              $generation($slot) $descriptor_address]
          if {[dict get $terminal completion_sequence] != $total_terminal} {
            error "P7 stationary terminal ledger sequence differs from descriptor completion sequence"
          }
          set terminal_prefix [format "stationary_%08u" $total_terminal]
          p7_dump_case $bundle_dir $slot $case_input($slot) $case_output($slot) \
              $case_length($slot) $case_trace($slot) $case_trace_capacity($slot) \
              $terminal_prefix $slot $result_handle $abort_file
          p7_say $result_handle [format "P7_STATIONARY_TERMINAL_BUNDLE_%08u_CAPTURED=1" $total_terminal]
          lappend stationary_terminal_records $terminal
          set total_bytes_completed [expr {$total_bytes_completed + [dict get $terminal bytes_completed]}]
          set total_fragments_completed [expr {$total_fragments_completed + [dict get $terminal fragments_completed]}]
          set total_lane0_fragments [expr {$total_lane0_fragments + [dict get $terminal lane0_fragments]}]
          set total_lane1_fragments [expr {$total_lane1_fragments + [dict get $terminal lane1_fragments]}]
          set total_replicated_fragments [expr {$total_replicated_fragments + [dict get $terminal replicated_fragments]}]
          set total_fallbacks [expr {$total_fallbacks + [dict get $terminal fallback_count]}]
          set total_p6_retry_count [expr {$total_p6_retry_count + [dict get $terminal p6_retry_count]}]
          set total_p6_retry_exhausted [expr {$total_p6_retry_exhausted + [dict get $terminal p6_retry_exhausted]}]
          set total_p6_tx_fail [expr {$total_p6_tx_fail + [dict get $terminal p6_tx_fail]}]
          set total_p6_crc_bad [expr {$total_p6_crc_bad + [dict get $terminal p6_crc_bad]}]
          set total_p6_payload_mismatch [expr {$total_p6_payload_mismatch + [dict get $terminal p6_payload_mismatch]}]
          set total_duty_violations [expr {$total_duty_violations + [dict get $terminal duty_violations]}]
          if {[dict get $terminal max_txd_high_cycles] > $max_txd_high_cycles} {
            set max_txd_high_cycles [dict get $terminal max_txd_high_cycles]
          }
          set last_completed_object_id [dict get $terminal object_id]
          set object_latency [expr {[dict get $terminal end_ticks] - [dict get $terminal start_ticks]}]
          if {$object_latency <= 0} { error "P7 stationary object latency is not positive" }
          set last_terminal($slot) 1
          set proposed_object_id [expr {$next_object_id + [llength $prepared_slots] + 1}]
          p7_prepare_stationary_slot $bundle_dir $slot $descriptor_address $proposed_object_id
          lappend prepared_slots [list $slot $descriptor_address $proposed_object_id $terminal_prefix]
        }

        set elapsed_ticks [p7_read_runtime_elapsed_ticks]
        set service_state [p7_read32 0x00020008]
        if {$service_state == 4 || $service_state == 5} {
          p7_mark_stationary_terminal $result_handle
          set terminal_during_snapshot 1
          break
        }
        set late_terminal 0
        foreach slot [lsort -integer [array names case_input]] {
          if {$last_terminal($slot)} { continue }
          set descriptor_address [expr {0x00020100 + 0x100 * $slot}]
          set status [p7_read32 [expr {$descriptor_address + 0x0C}]]
          if {$status >= 3 && $status <= 6} {
            set late_terminal 1
            break
          }
        }
        if {!$late_terminal} { break }
      }
      if {$terminal_during_snapshot} {
        foreach prepared $prepared_slots {
          lassign $prepared slot descriptor_address proposed_object_id terminal_prefix
          dow -data [file join $bundle_dir "${terminal_prefix}_descriptor_result.bin"] $descriptor_address
        }
        break
      }

      set committed_this_iteration 0
      foreach prepared $prepared_slots {
        lassign $prepared slot descriptor_address proposed_object_id terminal_prefix
        if {$elapsed_ticks + $ready_publish_guard_ticks < $scheduling_cutoff_ticks} {
          if {$committed_this_iteration == 0} {
            set last_requeue_pre_ticks $elapsed_ticks
          }
          p7_commit_stationary_slot $descriptor_address
          set next_object_id $proposed_object_id
          incr requeue_publish_count
          incr committed_this_iteration
          incr generation($slot)
          set last_terminal($slot) 0
        } else {
          # Preserve a terminal descriptor for final readback when the
          # preloaded FREE body is not admitted by the guarded cutoff check.
          dow -data [file join $bundle_dir "${terminal_prefix}_descriptor_result.bin"] $descriptor_address
          incr requeue_blocked_at_cutoff_count
        }
      }
      if {$committed_this_iteration > 0} {
        set last_requeue_post_ticks [p7_read_runtime_elapsed_ticks]
        if {$last_requeue_post_ticks >= $scheduling_cutoff_ticks} {
          set requeue_after_cutoff 1
          p7_say $result_handle "P7_STATIONARY_REQUEUE_CUTOFF_VIOLATION=1"
          p7_say $result_handle "P7_STATIONARY_REQUEUE_PRE_TICKS=$last_requeue_pre_ticks"
          p7_say $result_handle "P7_STATIONARY_REQUEUE_POST_TICKS=$last_requeue_post_ticks"
          error "P7 stationary READY publication crossed the PS-time scheduling cutoff"
        }
        set elapsed_ticks $last_requeue_post_ticks
      }

      set drain_elapsed_ticks $elapsed_ticks
      if {!$drain_complete && $drain_elapsed_ticks >= $scheduling_cutoff_ticks} {
        set all_drained 1
        foreach slot [array names case_input] {
          if {!$last_terminal($slot)} {
            set all_drained 0
            break
          }
        }
        if {$all_drained} {
          set drain_complete 1
          if {$drain_elapsed_ticks > $drain_deadline_ticks} {
            error "P7 stationary queue did not drain by 1790 seconds"
          }
          set drain_elapsed_sec [expr {double($drain_elapsed_ticks) / double($counts_per_second)}]
          p7_say $result_handle [format "P7_STATIONARY_DRAIN_COMPLETE_ELAPSED=%.3f" $drain_elapsed_sec]
          p7_say $result_handle "P7_STATIONARY_DRAIN_COMPLETE_TICKS=$drain_elapsed_ticks"
        }
      }
      while {$elapsed_ticks >= $next_sample_ticks && $sample_index < 59} {
        set sample_threshold_ticks $next_sample_ticks
        incr sample_index
        p7_emit_stationary_sample $result_handle $sample_index $stationary_terminal_records \
            $runtime_start_ticks $sample_threshold_ticks $elapsed_ticks $sample_interval_ticks \
            $counts_per_second $calibration_ticks
        set next_sample_ticks [expr {$next_sample_ticks + $sample_interval_ticks}]
      }
      if {!$calibration_complete && $elapsed_ticks >= $calibration_ticks} {
        set calibration_complete 1
        p7_say $result_handle "P7_CALIBRATION_WINDOW_COMPLETE=1"
      }
      after 5
    }
    if {!$::p7_stationary_terminal_marker_emitted} {
      p7_mark_stationary_terminal $result_handle
    }
    set stationary_terminal_observed_ms $::p7_stationary_terminal_observed_ms

    # Firmware is terminal and can no longer mutate descriptors.  Capture
    # every completion that may have occurred during a long XSDB dump, in
    # firmware completion-sequence order, without preparing or committing any
    # new work.
    set terminal_freeze_capture_count 0
    while {1} {
      set terminal_candidates {}
      foreach slot [lsort -integer [array names case_input]] {
        if {$last_terminal($slot)} { continue }
        set descriptor_address [expr {0x00020100 + 0x100 * $slot}]
        set status [p7_read32 [expr {$descriptor_address + 0x0C}]]
        if {$status >= 3 && $status <= 6} {
          set completion_sequence [p7_read32 [expr {$descriptor_address + 0xFC}]]
          lappend terminal_candidates [list $completion_sequence $slot]
        }
      }
      if {[llength $terminal_candidates] == 0} { break }
      foreach terminal_candidate [lsort -integer -index 0 $terminal_candidates] {
        lassign $terminal_candidate completion_sequence slot
        set descriptor_address [expr {0x00020100 + 0x100 * $slot}]
        if {$completion_sequence != $total_terminal + 1} {
          error "P7 terminal-freeze completion sequence is not contiguous"
        }
        set status [p7_read32 [expr {$descriptor_address + 0x0C}]]
        set error_code [p7_read32 [expr {$descriptor_address + 0x44}]]
        if {$status != 3 || $error_code != 0} {
          error "P7 terminal-freeze descriptor is not a clean COMPLETE slot=$slot"
        }
        incr total_terminal
        incr terminal_freeze_capture_count
        set terminal [p7_record_stationary_terminal $result_handle $total_terminal $slot \
            $generation($slot) $descriptor_address]
        set terminal_prefix [format "stationary_%08u" $total_terminal]
        p7_dump_case $bundle_dir $slot $case_input($slot) $case_output($slot) \
            $case_length($slot) $case_trace($slot) $case_trace_capacity($slot) \
            $terminal_prefix $slot $result_handle $abort_file
        p7_say $result_handle [format "P7_STATIONARY_TERMINAL_BUNDLE_%08u_CAPTURED=1" $total_terminal]
        lappend stationary_terminal_records $terminal
        set total_bytes_completed [expr {$total_bytes_completed + [dict get $terminal bytes_completed]}]
        set total_fragments_completed [expr {$total_fragments_completed + [dict get $terminal fragments_completed]}]
        set total_lane0_fragments [expr {$total_lane0_fragments + [dict get $terminal lane0_fragments]}]
        set total_lane1_fragments [expr {$total_lane1_fragments + [dict get $terminal lane1_fragments]}]
        set total_replicated_fragments [expr {$total_replicated_fragments + [dict get $terminal replicated_fragments]}]
        set total_fallbacks [expr {$total_fallbacks + [dict get $terminal fallback_count]}]
        set total_p6_retry_count [expr {$total_p6_retry_count + [dict get $terminal p6_retry_count]}]
        set total_p6_retry_exhausted [expr {$total_p6_retry_exhausted + [dict get $terminal p6_retry_exhausted]}]
        set total_p6_tx_fail [expr {$total_p6_tx_fail + [dict get $terminal p6_tx_fail]}]
        set total_p6_crc_bad [expr {$total_p6_crc_bad + [dict get $terminal p6_crc_bad]}]
        set total_p6_payload_mismatch [expr {$total_p6_payload_mismatch + [dict get $terminal p6_payload_mismatch]}]
        set total_duty_violations [expr {$total_duty_violations + [dict get $terminal duty_violations]}]
        if {[dict get $terminal max_txd_high_cycles] > $max_txd_high_cycles} {
          set max_txd_high_cycles [dict get $terminal max_txd_high_cycles]
        }
        set last_completed_object_id [dict get $terminal object_id]
        set last_terminal($slot) 1
      }
    }
    p7_say $result_handle "P7_STATIONARY_TERMINAL_FREEZE_CAPTURES=$terminal_freeze_capture_count"
    set all_drained 1
    foreach slot [array names case_input] {
      if {!$last_terminal($slot)} {
        set all_drained 0
        break
      }
    }
    set final_completion_sequence [p7_read32 0x0002005C]
    set final_objects_completed [p7_read32 0x00020024]
    set final_objects_failed [p7_read32 0x00020028]
    if {!$all_drained || $final_objects_failed != 0 ||
        $final_completion_sequence != $total_terminal ||
        $final_objects_completed != $total_terminal} {
      error "P7 terminal-freeze ledger does not reconcile to the final mailbox"
    }
    set max_terminal_relative_end 0
    foreach terminal $stationary_terminal_records {
      set relative_end [expr {[dict get $terminal end_ticks] - $runtime_start_ticks}]
      if {$relative_end > $max_terminal_relative_end} {
        set max_terminal_relative_end $relative_end
      }
    }
    if {!$drain_complete && $max_terminal_relative_end <= $drain_deadline_ticks} {
      set drain_complete 1
      set reconstructed_drain_ticks [expr {max($scheduling_cutoff_ticks, $max_terminal_relative_end)}]
      set reconstructed_drain_sec [expr {double($reconstructed_drain_ticks) / double($counts_per_second)}]
      p7_say $result_handle [format "P7_STATIONARY_DRAIN_COMPLETE_ELAPSED=%.3f" $reconstructed_drain_sec]
      p7_say $result_handle "P7_STATIONARY_DRAIN_COMPLETE_TICKS=$reconstructed_drain_ticks"
      p7_say $result_handle "P7_STATIONARY_DRAIN_RECONSTRUCTED_FROM_TERMINAL_END_TICKS=1"
    }
    if {!$calibration_complete} {
      set calibration_complete 1
      p7_say $result_handle "P7_CALIBRATION_WINDOW_COMPLETE=1"
      p7_say $result_handle "P7_CALIBRATION_RECONSTRUCTED_FROM_FINAL_PS_TIME=1"
    }
    # Host time is an independent duration/watchdog corroboration only.  PS
    # runtime_elapsed_ticks remains authoritative for samples and acceptance.
    set stationary_wall_seconds [expr {($stationary_terminal_observed_ms - $service_start_ms) / 1000.0}]
    if {$stationary_wall_seconds < 1800.0 || $stationary_wall_seconds > 1801.5} {
      error "P7 stationary independent host duration corroboration is outside 1800.0..1801.5 seconds"
    }
    p7_say $result_handle [format "P7_STATIONARY_WALL_SECONDS=%.3f" $stationary_wall_seconds]
    p7_say $result_handle "P7_STATIONARY_HOST_WATCHDOG_CORROBORATION=PASS"
    set final_elapsed_ticks [p7_read_runtime_elapsed_ticks 0]
    set final_elapsed_sec [expr {double($final_elapsed_ticks) / double($counts_per_second)}]
    if {$final_elapsed_ticks < $required_runtime_ticks} {
      error "P7 stationary PS runtime_elapsed_ticks is below the authorized 1800-second runtime"
    }
    p7_say $result_handle "P7_STATIONARY_PS_ELAPSED_TICKS=$final_elapsed_ticks"
    p7_say $result_handle [format "P7_STATIONARY_PS_ELAPSED_SECONDS=%.6f" $final_elapsed_sec]
    set runtime_flags [p7_read32 0x00020068]
    set service_state [p7_read32 0x00020008]
    if {$service_state != 4 || ($runtime_flags & 0x2) == 0} {
      error "P7 stationary service did not auto-shutdown at its deadline"
    }
    set final_runtime_request [p7_read32 0x0002008C]
    set final_runtime_ack [p7_read32 0x00020090]
    if {$final_runtime_request != $final_runtime_ack} {
      if {!$::p7_terminal_unacknowledged_refresh ||
          $::p7_terminal_unacknowledged_request != $final_runtime_request ||
          $::p7_terminal_unacknowledged_ack != $final_runtime_ack} {
        error "P7 terminal runtime request/ACK mismatch lacks an exact observed terminal release tuple"
      }
    } elseif {$::p7_terminal_unacknowledged_refresh} {
      error "P7 terminal-unacknowledged flag contradicts equal final request/ACK"
    }
    p7_say $result_handle "P7_TERMINAL_UNACKNOWLEDGED_REFRESH=$::p7_terminal_unacknowledged_refresh"
    p7_say $result_handle "P7_TERMINAL_UNACKNOWLEDGED_CAPTURED_REQUEST=$::p7_terminal_unacknowledged_request"
    p7_say $result_handle "P7_TERMINAL_UNACKNOWLEDGED_CAPTURED_ACK=$::p7_terminal_unacknowledged_ack"
    p7_say $result_handle "P7_TERMINAL_FINAL_REQUEST=$final_runtime_request"
    p7_say $result_handle "P7_TERMINAL_FINAL_ACK=$final_runtime_ack"
    set post_terminal_reconstructed_samples 0
    while {$sample_index < 59} {
      incr sample_index
      p7_emit_stationary_sample $result_handle $sample_index $stationary_terminal_records \
          $runtime_start_ticks $next_sample_ticks $final_elapsed_ticks $sample_interval_ticks \
          $counts_per_second $calibration_ticks
      set next_sample_ticks [expr {$next_sample_ticks + $sample_interval_ticks}]
      incr post_terminal_reconstructed_samples
    }
    p7_say $result_handle "P7_STATIONARY_POST_TERMINAL_RECONSTRUCTED_SAMPLES=$post_terminal_reconstructed_samples"
    incr sample_index
    p7_emit_stationary_sample $result_handle $sample_index $stationary_terminal_records \
        $runtime_start_ticks $required_runtime_ticks $final_elapsed_ticks $sample_interval_ticks \
        $counts_per_second $calibration_ticks
    p7_say $result_handle "P7_SAMPLE_00060_SAFE_TERMINAL_STATE=1"
    mwr 0x00020084 $sample_index
    if {[p7_read32 0x00020084] != 60} { error "P7 final sample sequence mailbox readback failed" }
    p7_say $result_handle "P7_SAMPLE_SEQUENCE_WRITER=HOST_POST_TERMINAL"
    p7_say $result_handle "P7_STATIONARY_REQUEUE_PUBLISH_COUNT=$requeue_publish_count"
    p7_say $result_handle "P7_STATIONARY_REQUEUE_BLOCKED_AT_CUTOFF_COUNT=$requeue_blocked_at_cutoff_count"
    p7_say $result_handle "P7_STATIONARY_REQUEUE_CUTOFF_TICKS=$scheduling_cutoff_ticks"
    p7_say $result_handle "P7_STATIONARY_REQUEUE_LAST_PRE_TICKS=$last_requeue_pre_ticks"
    p7_say $result_handle "P7_STATIONARY_REQUEUE_LAST_POST_TICKS=$last_requeue_post_ticks"
    p7_say $result_handle "P7_STATIONARY_REQUEUE_CUTOFF_VIOLATION=0"
    if {!$calibration_complete} { error "P7 stationary calibration window incomplete" }
    if {!$drain_complete} { error "P7 stationary descriptors were not fully drained before deadline" }
    set acceptance_complete 1
    p7_say $result_handle "P7_ACCEPTANCE_WINDOW_COMPLETE=1"
    p7_say $result_handle "P7_STATIONARY_TERMINAL_DESCRIPTORS=$total_terminal"
  } elseif {$mode eq "functional"} {
    set phase_deadline [expr {$service_start_ms + 1000 * $max_runtime_sec}]
    for {set batch 0} {$batch < 6} {incr batch} {
      set first_index [expr {$batch * 8}]
      foreach ring_slot {0 1 2 3 4 5 6 7} {
        set boundary_index [expr {$first_index + $ring_slot}]
        if {$boundary_length($boundary_index) > 0} {
          dow -data [file join $bundle_dir "boundary_${boundary_index}_input.bin"] \
              $boundary_input($boundary_index)
          dow -data [file join $bundle_dir "boundary_${boundary_index}_output_zero.bin"] \
              $boundary_output($boundary_index)
        }
        dow -data [file join $bundle_dir "boundary_${boundary_index}_trace_zero.bin"] \
            $boundary_trace($boundary_index)
        dow -data [file join $bundle_dir "boundary_${boundary_index}_descriptor_free.bin"] \
            [expr {0x00020100 + 0x100 * $ring_slot}]
      }
      foreach ring_slot {0 1 2 3 4 5 6 7} {
        mwr [expr {0x00020100 + 0x100 * $ring_slot + 0x0C}] 1
      }
      foreach ring_slot {0 1 2 3 4 5 6 7} {
        set boundary_index [expr {$first_index + $ring_slot}]
        set descriptor_address [expr {0x00020100 + 0x100 * $ring_slot}]
        lassign [p7_wait_descriptor_terminal $abort_file $descriptor_address $phase_deadline \
            "P7_FUNCTIONAL_BOUNDARY_$boundary_index"] status error_code
        if {$status != 3 || $error_code != 0} {
          error "P7 functional boundary case failed: index=$boundary_index length=$boundary_length($boundary_index)"
        }
        p7_dump_case $bundle_dir $boundary_index $boundary_input($boundary_index) \
            $boundary_output($boundary_index) $boundary_length($boundary_index) \
            $boundary_trace($boundary_index) $boundary_trace_capacity($boundary_index) \
            "boundary_${boundary_index}" $ring_slot
      }
    }

    dow -data [file join $bundle_dir functional_checkpoint_4k_input.bin] 0x00100000
    dow -data [file join $bundle_dir functional_checkpoint_4k_output_zero.bin] 0x00900000
    dow -data [file join $bundle_dir functional_checkpoint_4k_trace_zero.bin] 0x01100000
    dow -data [file join $bundle_dir functional_checkpoint_4k_descriptor_free.bin] 0x00020100
    mwr 0x0002010C 1
    lassign [p7_wait_descriptor_terminal $abort_file 0x00020100 $phase_deadline \
        P7_FUNCTIONAL_CHECKPOINT_4K] checkpoint_status checkpoint_error
    if {$checkpoint_status != 3 || $checkpoint_error != 0} {
      error "P7 functional 4KiB stripe checkpoint failed"
    }
    p7_dump_case $bundle_dir 0 0x00100000 0x00900000 4096 0x01100000 20 \
        functional_checkpoint_4k 0
    p7_say $result_handle "P7_FUNCTIONAL_CHECKPOINT_4K_COMPLETE=1"

    foreach source_slot {4 5 6 7} {
      dow -data [file join $bundle_dir "input_${source_slot}.bin"] $case_input($source_slot)
      dow -data [file join $bundle_dir "output_zero_${source_slot}.bin"] $case_output($source_slot)
      dow -data [file join $bundle_dir "trace_zero_${source_slot}.bin"] $case_trace($source_slot)
    }
    foreach source_slot {4 5 6 7} target_slot {1 2 3 4} {
      p7_publish_source_descriptor_to_target $bundle_dir $source_slot $target_slot
    }
    foreach source_slot {4 5 6 7} target_slot {1 2 3 4} {
      set descriptor_address [expr {0x00020100 + 0x100 * $target_slot}]
      lassign [p7_wait_descriptor_terminal $abort_file $descriptor_address $phase_deadline \
          "P7_FUNCTIONAL_64K_$source_slot"] status error_code
      if {$status != 3 || $error_code != 0} {
        error "P7 functional 64KiB pattern case failed: source_slot=$source_slot"
      }
      p7_dump_case $bundle_dir $source_slot $case_input($source_slot) $case_output($source_slot) \
          $case_length($source_slot) $case_trace($source_slot) $case_trace_capacity($source_slot) "" $target_slot
    }

    foreach source_slot {0 1 2 3} {
      dow -data [file join $bundle_dir "input_${source_slot}.bin"] $case_input($source_slot)
      dow -data [file join $bundle_dir "output_zero_${source_slot}.bin"] $case_output($source_slot)
      dow -data [file join $bundle_dir "trace_zero_${source_slot}.bin"] $case_trace($source_slot)
    }
    foreach source_slot {0 1 2 3} target_slot {5 6 7 0} {
      p7_publish_source_descriptor_to_target $bundle_dir $source_slot $target_slot
    }
    foreach source_slot {0 1 2 3} target_slot {5 6 7 0} {
      set descriptor_address [expr {0x00020100 + 0x100 * $target_slot}]
      lassign [p7_wait_descriptor_terminal $abort_file $descriptor_address $phase_deadline \
          "P7_FUNCTIONAL_1M_$source_slot"] status error_code
      if {$status != 3 || $error_code != 0} {
        error "P7 functional 1MiB lane-policy case failed: source_slot=$source_slot"
      }
      p7_dump_case $bundle_dir $source_slot $case_input($source_slot) $case_output($source_slot) \
          $case_length($source_slot) $case_trace($source_slot) $case_trace_capacity($source_slot) "" $target_slot
    }
    mwr 0x0002000C 5
    if {[p7_wait_service_terminal $abort_file $phase_deadline P7_FUNCTIONAL_EXIT] != 4 ||
        [p7_read32 0x00020048] != 0} {
      error "P7 functional large/boundary phases did not shutdown cleanly"
    }
    p7_say $result_handle "P7_FUNCTIONAL_LARGE_POLICY_MATRIX_COMPLETE=1"
    p7_say $result_handle "P7_FUNCTIONAL_BOUNDARY_MATRIX_COMPLETE=1"
    p7_say $result_handle "P7_FUNCTIONAL_BOUNDARY_BATCHES=6"
    p7_say $result_handle "P7_FUNCTIONAL_BOUNDARY_CASES=48"
    p7_say $result_handle "P7_FUNCTIONAL_EXECUTION_ORDER=BOUNDARY48_THEN_4K_THEN_64K4_THEN_1M4"
  } elseif {$mode eq "fault-fallback"} {
    set phase_deadline [expr {$service_start_ms + 1000 * $max_runtime_sec}]
    foreach slot {0 1 2 3} {
      set descriptor_address [expr {0x00020100 + 0x100 * $slot}]
      lassign [p7_wait_descriptor_terminal $abort_file $descriptor_address $phase_deadline \
          "P7_FAULT_POSITIVE_$slot"] status error_code
      if {$status != 3 || $error_code != 0} {
        error "P7 controlled fallback positive case failed: slot=$slot"
      }
      p7_dump_case $bundle_dir $slot $case_input($slot) $case_output($slot) \
          $case_length($slot) $case_trace($slot) $case_trace_capacity($slot)
    }
    mwr 0x0002000C 5
    if {[p7_wait_service_terminal $abort_file $phase_deadline P7_FAULT_POSITIVE_EXIT] != 4 ||
        [p7_read32 0x00020048] != 0} {
      error "P7 controlled fallback positive phase did not shutdown cleanly"
    }

    set fault_negative_phases 0
    foreach slot {4 5 6} {
      incr fault_negative_phases
      catch {stop}
      targets [dict get $fpga_target target_id]
      fpga -file $shutdown_bit
      p7_say $result_handle "P7_FAULT_NEGATIVE_${slot}_INTERPHASE_SHUTDOWN=1"
      fpga -file $bit_file
      targets [dict get $cpu_target target_id]
      ps7_init
      ps7_post_config
      rst -processor
      p7_load_phase $bundle_dir [file join $bundle_dir mailbox.bin] \
          case_input case_output case_length case_trace case_trace_capacity
      dow $elf_file
      con
      p7_wait_service_ready $abort_file $result_handle "P7_FAULT_NEGATIVE_$slot"
      p7_publish_source_descriptor_to_target $bundle_dir $slot 0
      set descriptor_address 0x00020100
      lassign [p7_wait_descriptor_terminal $abort_file $descriptor_address $phase_deadline \
          "P7_FAULT_NEGATIVE_$slot"] status error_code
      if {$status != 4 || $error_code != 8} {
        error "P7 strict-policy unavailable negative case did not fail bounded: slot=$slot"
      }
      p7_dump_case $bundle_dir $slot $case_input($slot) $case_output($slot) \
          $case_length($slot) $case_trace($slot) $case_trace_capacity($slot) "" 0
      set negative_stopped 0
      while {[clock milliseconds] < $phase_deadline} {
        p7_check_abort $abort_file
        if {[p7_read32 0x00020008] == 3} {
          set negative_stopped 1
          break
        }
        after 10
      }
      if {!$negative_stopped || [p7_read32 0x00020048] != 0} {
        error "P7 strict-policy negative did not latch STOPPED after safe shutdown"
      }
      mwr 0x0002000C 5
      if {[p7_wait_service_terminal $abort_file $phase_deadline \
          "P7_FAULT_NEGATIVE_${slot}_EXIT"] != 4} {
        error "P7 strict-policy negative did not honor explicit SHUTDOWN exit"
      }
    }
    p7_say $result_handle "P7_FAULT_STRICT_NEGATIVE_PHASES=$fault_negative_phases"
  } elseif {$mode eq "abort-restart"} {
    set phase_deadline [expr {$service_start_ms + 1000 * $max_runtime_sec}]
    lassign [p7_wait_descriptor_terminal $abort_file 0x00020100 $phase_deadline P7_ABORT_PHASE] \
        abort_status abort_error
    if {$abort_status != 5 || $abort_error != 15} {
      error "P7 deterministic abort phase did not publish ABORTED/error15"
    }
    p7_dump_case $bundle_dir 0 $case_input(0) $case_output(0) $case_length(0) \
        $case_trace(0) $case_trace_capacity(0)
    set abort_stopped 0
    while {[clock milliseconds] < $phase_deadline} {
      p7_check_abort $abort_file
      if {[p7_read32 0x00020008] == 3} {
        set abort_stopped 1
        break
      }
      after 10
    }
    set abort_shutdown_result [p7_read32 0x00020048]
    set abort_count [p7_read32 0x00020054]
    if {!$abort_stopped || $abort_shutdown_result != 0 || $abort_count < 1} {
      error "P7 abort phase did not latch STOPPED after safe shutdown"
    }
    p7_say $result_handle "P7_ABORT_PHASE_ABORT_COUNT=$abort_count"
    p7_say $result_handle "P7_ABORT_PHASE_SHUTDOWN_RESULT=$abort_shutdown_result"
    mwr 0x0002000C 5
    if {[p7_wait_service_terminal $abort_file $phase_deadline P7_ABORT_PHASE_EXIT] != 4} {
      error "P7 abort phase did not honor explicit SHUTDOWN exit"
    }

    catch {stop}
    targets [dict get $fpga_target target_id]
    fpga -file $shutdown_bit
    p7_say $result_handle "P7_ABORT_INTERPHASE_SHUTDOWN_PROGRAMMED=1"
    fpga -file $bit_file
    p7_say $result_handle "P7_ABORT_RESTART_CANDIDATE_REPROGRAMMED=1"
    targets [dict get $cpu_target target_id]
    ps7_init
    ps7_post_config
    rst -processor
    p7_load_phase $bundle_dir [file join $bundle_dir mailbox.bin] \
        case_input case_output case_length case_trace case_trace_capacity
    dow $elf_file
    con
    p7_wait_service_ready $abort_file $result_handle P7_ABORT_RESTART
    p7_publish_source_descriptor_to_target $bundle_dir 1 0

    lassign [p7_wait_descriptor_terminal $abort_file 0x00020100 $phase_deadline P7_RETRANSMIT] \
        retransmit_status retransmit_error
    if {$retransmit_status != 3 || $retransmit_error != 0} {
      error "P7 new-epoch retransmit did not complete"
    }
    p7_dump_case $bundle_dir 1 $case_input(1) $case_output(1) $case_length(1) \
        $case_trace(1) $case_trace_capacity(1) "" 0
    p7_publish_source_descriptor_to_target $bundle_dir 2 1
    lassign [p7_wait_descriptor_terminal $abort_file 0x00020200 $phase_deadline P7_DUPLICATE_REPLAY] \
        replay_status replay_error
    if {$replay_status != 6 || $replay_error != 19} {
      error "P7 duplicate replay policy did not reject the completed object ID"
    }
    p7_dump_case $bundle_dir 2 $case_input(2) $case_output(2) $case_length(2) \
        $case_trace(2) $case_trace_capacity(2) "" 1
    mwr 0x0002000C 5
    set restart_service_state [p7_wait_service_terminal $abort_file $phase_deadline P7_ABORT_RESTART]
    if {$restart_service_state != 4 || [p7_read32 0x00020048] != 0} {
      error "P7 restarted service did not shutdown cleanly"
    }
    p7_say $result_handle "P7_ABORT_RESTART_NEW_EPOCH=1"
    p7_say $result_handle "P7_ABORT_RESTART_REPLAY_REJECTED=1"
  } elseif {$mode eq "queue"} {
    set phase_deadline [expr {$service_start_ms + 1000 * $max_runtime_sec}]
    lassign [p7_wait_descriptor_terminal $abort_file 0x00020100 $phase_deadline P7_QUEUE_DEPTH1] \
        depth1_status depth1_error
    if {$depth1_status != 3 || $depth1_error != 0} {
      error "P7 queue depth-1 positive object did not complete"
    }
    p7_dump_case $bundle_dir 0 $case_input(0) $case_output(0) $case_length(0) \
        $case_trace(0) $case_trace_capacity(0)
    foreach {source_name target_name} [list \
        descriptor_result_0.bin queue_depth1_descriptor_result.bin \
        output_result_0.bin queue_depth1_output_result.bin \
        trace_result_0.bin queue_depth1_trace_result.bin] {
      file rename -force [file join $bundle_dir $source_name] [file join $bundle_dir $target_name]
    }
    mwr 0x0002000C 5
    if {[p7_wait_service_terminal $abort_file $phase_deadline P7_QUEUE_DEPTH1] != 4 ||
        [p7_read32 0x00020048] != 0} {
      error "P7 queue depth-1 phase did not shutdown cleanly"
    }
    p7_atomic_dump [file join $bundle_dir queue_depth1_mailbox.bin] 0x00020000 256
    p7_say $result_handle "P7_QUEUE_DEPTH1_COMPLETE=1"

    catch {stop}
    targets [dict get $fpga_target target_id]
    fpga -file $shutdown_bit
    p7_say $result_handle "P7_QUEUE_INTERPHASE_SHUTDOWN_1_PROGRAMMED=1"
    fpga -file $bit_file
    p7_say $result_handle "P7_QUEUE_INTERPHASE_CANDIDATE_REPROGRAM_1=1"
    targets [dict get $cpu_target target_id]
    ps7_init
    ps7_post_config
    rst -processor
    p7_load_phase $bundle_dir [file join $bundle_dir mailbox_queue_depth_8_stop.bin] \
        case_input case_output case_length case_trace case_trace_capacity
    dow $elf_file
    con
    p7_wait_service_ready $abort_file $result_handle P7_QUEUE_MAX
    p7_publish_phase_descriptors $bundle_dir {0 1 2 3 4 5 6 7}
    set stopped 0
    for {set poll 0} {$poll < 1000} {incr poll} {
      p7_check_abort $abort_file
      if {[p7_read32 0x00020008] == 3 && [p7_read32 0x00020014] == 8} {
        set stopped 1
        break
      }
      after 10
    }
    if {!$stopped} { error "P7 max queue did not publish STOPPED with occupancy 8" }
    set overflow_ring_before [file join $bundle_dir queue_overflow_ring_before.bin]
    set overflow_ring_after [file join $bundle_dir queue_overflow_ring_after.bin]
    p7_atomic_dump $overflow_ring_before 0x00020100 2048
    set admission [p7_queue_admit_candidate $bundle_dir 0x10100000 0x10900000 777 0x11100000 4]
    if {[dict get $admission result] ne "FULL" ||
        [dict get $admission occupancy] != 8 ||
        [dict get $admission capacity] != 8 ||
        [dict get $admission ddr_write_count] != 0} {
      error "P7 ninth producer candidate was not rejected FULL before every DDR write"
    }
    p7_atomic_dump $overflow_ring_after 0x00020100 2048
    set before_handle [open $overflow_ring_before rb]
    fconfigure $before_handle -translation binary
    set before_ring [read $before_handle]
    close $before_handle
    set after_handle [open $overflow_ring_after rb]
    fconfigure $after_handle -translation binary
    set after_ring [read $after_handle]
    close $after_handle
    if {$before_ring ne $after_ring} {
      error "P7 rejected overflow admission changed the descriptor ring"
    }
    p7_say $result_handle "P7_QUEUE_FULL_BEFORE_RUN=1"
    p7_say $result_handle "P7_QUEUE_STOP_WHILE_QUEUED=1"
    p7_say $result_handle "P7_QUEUE_OVERFLOW_REJECTED_BEFORE_DDR_WRITE=1"
    p7_say $result_handle "P7_QUEUE_OVERFLOW_ADMISSION=FULL"
    p7_say $result_handle "P7_QUEUE_OVERFLOW_OCCUPANCY=[dict get $admission occupancy]"
    p7_say $result_handle "P7_QUEUE_OVERFLOW_CAPACITY=[dict get $admission capacity]"
    p7_say $result_handle "P7_QUEUE_OVERFLOW_DDR_WRITE=0"
    p7_say $result_handle "P7_QUEUE_OVERFLOW_DDR_WRITE_COUNT=[dict get $admission ddr_write_count]"
    p7_say $result_handle "P7_QUEUE_OVERFLOW_CANDIDATE_OBJECT_ID=9"
    p7_say $result_handle "P7_QUEUE_PRODUCER_FASTER_THAN_CONSUMER=1"
    mwr 0x0002000C 1
    foreach slot {0 1 2 3 4 5 6 7} {
      set descriptor_address [expr {0x00020100 + 0x100 * $slot}]
      lassign [p7_wait_descriptor_terminal $abort_file $descriptor_address $phase_deadline \
          "P7_QUEUE_MAX_SLOT_$slot"] status error_code
      if {$status != 3 || $error_code != 0} {
        error "P7 max-queue positive slot failed: $slot"
      }
      p7_dump_case $bundle_dir $slot $case_input($slot) $case_output($slot) \
          $case_length($slot) $case_trace($slot) $case_trace_capacity($slot)
    }
    mwr 0x0002000C 5
    if {[p7_wait_service_terminal $abort_file $phase_deadline P7_QUEUE_MAX] != 4 ||
        [p7_read32 0x00020048] != 0} {
      error "P7 max-queue positive phase did not shutdown cleanly"
    }
    p7_atomic_dump [file join $bundle_dir queue_max_mailbox.bin] 0x00020000 256
    p7_say $result_handle "P7_QUEUE_MAX_FIFO_COMPLETE=1"

    catch {stop}
    targets [dict get $fpga_target target_id]
    fpga -file $shutdown_bit
    p7_say $result_handle "P7_QUEUE_INTERPHASE_SHUTDOWN_2_PROGRAMMED=1"
    fpga -file $bit_file
    p7_say $result_handle "P7_QUEUE_INTERPHASE_CANDIDATE_REPROGRAM_2=1"
    targets [dict get $cpu_target target_id]
    ps7_init
    ps7_post_config
    rst -processor
    p7_load_phase $bundle_dir [file join $bundle_dir mailbox_queue_depth_8_stop.bin] \
        case_input case_output case_length case_trace case_trace_capacity
    dow $elf_file
    con
    p7_wait_service_ready $abort_file $result_handle P7_QUEUE_ABORT
    p7_publish_phase_descriptors $bundle_dir {0 1 2 3 4 5 6 7}
    set stopped 0
    for {set poll 0} {$poll < 1000} {incr poll} {
      p7_check_abort $abort_file
      if {[p7_read32 0x00020008] == 3 && [p7_read32 0x00020014] == 8} {
        set stopped 1
        break
      }
      after 10
    }
    if {!$stopped} { error "P7 queue abort phase did not retain eight queued objects" }
    mwr 0x0002000C 3
    set queue_abort_stopped 0
    while {[clock milliseconds] < $phase_deadline} {
      p7_check_abort $abort_file
      if {[p7_read32 0x00020008] == 3 && [p7_read32 0x00020054] >= 1} {
        set queue_abort_stopped 1
        break
      }
      after 10
    }
    if {!$queue_abort_stopped || [p7_read32 0x00020048] != 0} {
      error "P7 queue ABORT-while-queued did not latch STOPPED after safe shutdown"
    }
    p7_atomic_dump [file join $bundle_dir queue_abort_descriptors_final.bin] 0x00020100 2048
    mwr 0x0002000C 5
    if {[p7_wait_service_terminal $abort_file $phase_deadline P7_QUEUE_ABORT_EXIT] != 4} {
      error "P7 queue ABORT phase did not honor explicit SHUTDOWN exit"
    }
    p7_say $result_handle "P7_QUEUE_ABORT_WHILE_QUEUED=1"
    p7_say $result_handle "P7_QUEUE_INTERPHASE_SHUTDOWN_COUNT=2"
  } else {
    array set done {}
    foreach slot [array names case_input] { set done($slot) 0 }
    set terminal_count 0
    set deadline_ms [expr {$service_start_ms + 1000 * $max_runtime_sec}]
    while {$terminal_count < $parsed_cases} {
      p7_check_abort $abort_file
      if {[clock milliseconds] >= $deadline_ms} { error "P7 PS functional stage runtime exceeded" }
      foreach slot [lsort -integer [array names case_input]] {
        if {$done($slot)} { continue }
        set descriptor_address [expr {0x00020100 + 0x100 * $slot}]
        set status [p7_read32 [expr {$descriptor_address + 0x0C}]]
        if {$status >= 3 && $status <= 6} {
          set error_code [p7_read32 [expr {$descriptor_address + 0x44}]]
          p7_say $result_handle "P7_CASE_${slot}_STATUS=$status"
          p7_say $result_handle "P7_CASE_${slot}_ERROR=$error_code"
          if {$status != $case_expected_status($slot) || $error_code != $case_expected_error($slot)} {
            error "P7 case terminal mismatch slot=$slot status=$status error=$error_code"
          }
          p7_dump_case $bundle_dir $slot $case_input($slot) $case_output($slot) \
              $case_length($slot) $case_trace($slot) $case_trace_capacity($slot)
          set done($slot) 1
          incr terminal_count
        }
      }
      after 5
    }
    mwr 0x0002000C 5
    set shutdown_seen 0
    for {set poll 0} {$poll < 3000} {incr poll} {
      set state [p7_read32 0x00020008]
      if {$state == 4 || $state == 5} {
        set shutdown_seen 1
        break
      }
      after 10
    }
    if {!$shutdown_seen} { error "P7 PS service shutdown command timeout" }
  }

  p7_atomic_dump [file join $bundle_dir mailbox_final.bin] 0x00020000 256
  if {$mode ni {queue abort-restart fault-fallback functional}} {
    foreach slot [lsort -integer [array names case_input]] {
      p7_dump_case $bundle_dir $slot $case_input($slot) $case_output($slot) \
          $case_length($slot) $case_trace($slot) $case_trace_capacity($slot) \
          "" -1 $result_handle $abort_file
    }
  }
  p7_say $result_handle "P7_REQUEUE_AFTER_CUTOFF=$requeue_after_cutoff"
  p7_say $result_handle "P7_PS_STAGE_RESULT=PASS"
  close $result_handle
  set result_handle ""
  file rename -force $result_partial $result_file
  catch {stop}
  disconnect
  set connected 0
} error_text error_options]

if {$rc != 0} {
  if {$processor_started} {
    catch {mwr 0x0002000C 3}
    after 10
    catch {mwr 0x0002000C 5}
    catch {stop}
  }
  if {$result_handle ne ""} {
    catch {
      p7_say $result_handle "P7_PS_STAGE_RESULT=FAIL"
      p7_say $result_handle "P7_PS_STAGE_ERROR=[string map [list \n " " \r " "] $error_text]"
      close $result_handle
      set result_handle ""
      file rename -force $result_partial $result_file
    }
  } elseif {$result_file ne ""} {
    catch {
      set failure_handle [open $result_partial w]
      puts $failure_handle "P7_PS_STAGE_RESULT=FAIL"
      puts $failure_handle "P7_PS_STAGE_ERROR=[string map [list \n " " \r " "] $error_text]"
      close $failure_handle
      file rename -force $result_partial $result_file
    }
  }
  if {$connected} { catch {disconnect} }
  puts stderr "P7_PS_STAGE_RESULT=FAIL"
  puts stderr "P7_PS_STAGE_ERROR=$error_text"
  exit 42
}
exit 0
