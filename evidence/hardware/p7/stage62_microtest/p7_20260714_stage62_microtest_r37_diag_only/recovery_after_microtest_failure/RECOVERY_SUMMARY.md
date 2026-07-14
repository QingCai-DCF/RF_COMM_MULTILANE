# R37 independent recovery summary

The existing `program_tfdu_shutdown_safe.ps1` recovery-only path was used after
the immutable R37 failure. It validated the existing user P4 authorization at
`C:\Users\user\Documents\RF_COMM_MULTILANE\.hardware_authorization\P4_APPROVED.txt`
(SHA256 `61f676760e875ce2772e2c460e9b3241ebcd013ebacfea715ee79b232316f476`)
and programmed only `shutdown_bitstream/tfdu_shutdown_j10_j11.bit` (SHA256
`bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810`).

The command returned 0. The formal summary records
`TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`, `SHUTDOWN_EXIT=0`, and
`PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`. No candidate ELF or functional test
stage was run during recovery.
