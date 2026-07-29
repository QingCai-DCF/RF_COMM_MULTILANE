set output_path [file normalize [lindex $argv 0]]
connect -url tcp:127.0.0.1:3121
targets -set -nocase -filter {name =~ "*Cortex-A9*#0"}
catch {stop}
set partial "${output_path}.partial"
catch {file delete -force $partial}
mrd -size b -bin -file $partial 0x06000000 24700
if {![file isfile $partial] || [file size $partial] != 24700} {
  error "P9 postmortem DDR read length mismatch"
}
file rename -force $partial $output_path
disconnect
puts "P9_POSTMORTEM_DDR_READ=PASS"
exit
