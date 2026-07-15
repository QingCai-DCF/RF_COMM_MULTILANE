set r41_latencies {
  17875676347
  26957722756
  51321168692
  45147234789
}

set old_rc [catch {lsort -integer $r41_latencies} old_message old_options]
puts "P7_R41_OLD_SORT_RC=$old_rc"
puts "P7_R41_OLD_SORT_ERROR=$old_message"

proc p7_compare_wide_integer {left right} {
  if {$left < $right} { return -1 }
  if {$left > $right} { return 1 }
  return 0
}

set fixed_rc [catch {
  set fixed_values [lsort -command p7_compare_wide_integer $r41_latencies]
} fixed_message fixed_options]
puts "P7_R41_FIXED_SORT_RC=$fixed_rc"
puts "P7_R41_FIXED_SORT_VALUES=$fixed_values"

if {$old_rc != 1} {
  puts stderr "P7_R41_WIDE_LATENCY_REPRODUCER=FAIL_OLD_PATH_DID_NOT_REPRODUCE"
  exit 1
}
if {$old_message ne "integer value too large to represent"} {
  puts stderr "P7_R41_WIDE_LATENCY_REPRODUCER=FAIL_UNEXPECTED_OLD_ERROR"
  exit 1
}
if {$fixed_rc != 0} {
  puts stderr "P7_R41_WIDE_LATENCY_REPRODUCER=FAIL_FIXED_PATH_ERROR"
  exit 1
}
if {$fixed_values ne "17875676347 26957722756 45147234789 51321168692"} {
  puts stderr "P7_R41_WIDE_LATENCY_REPRODUCER=FAIL_FIXED_ORDER"
  exit 1
}
puts "P7_R41_WIDE_LATENCY_REPRODUCER=PASS"
exit 0
