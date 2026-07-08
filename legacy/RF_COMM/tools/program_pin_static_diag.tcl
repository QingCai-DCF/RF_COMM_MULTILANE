set repo_root [file normalize [file join [file dirname [info script]] ..]]
set bit_file [file join $repo_root reports pin_static_diag pin_static_diag.bit]

if {![file exists $bit_file]} {
  error "Missing bitstream: $bit_file"
}

connect
after 1000
targets -set -filter {name =~ "xc7z*"}
fpga -file $bit_file
puts "PIN_STATIC_DIAG_PROGRAMMED=$bit_file"
