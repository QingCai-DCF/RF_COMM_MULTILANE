# P10.4 protocol-fault priming remediation

## Direct failure evidence

The immutable hardware run
`p10_4_20260805T144037Z_a32afe5b_6f915067_ace48b07` ended fail-closed at
`duplicate_fault`. Both role-bound shutdown images were programmed and verified
PASS. The stage preserved frozen first-fault evidence before independent
shutdown.

The only stage-validation error was
`duplicate_segment:rotating:injected fault not observed`. The sender read back
protocol fault flags `0x00000008`, while the rotating receiver reported zero
for the injected-fault observation, duplicate, old-sequence, and protocol-error
counters. Both endpoints produced the expected no-commit abort result, with no
CRC/SHA, partial-commit, duplicate-commit, stale-commit, retry-exhaustion, duty,
continuous-high, or hard-safety failure.

## Cause

The autonomous fault command contains two 256 KiB objects. Generic recovery
selection chose object 1. The host directly primes and verifies the receiver
only for object 0 before publishing the sender command. Normal streaming then
uses the intentionally handshake-free object pipeline. The receiver performs
object-0 integrity work, while the sender can reach object 1 earlier and spend
the three-attempt corrupt-sequence budget before the receiver has changed to
object 1. Those frames therefore cannot increment the intended object-1
duplicate counter. Clean attempts that follow can still be received, explaining
the observed traffic without the required injected-fault counter edge.

## Repair

Duplicate-segment and stale-segment diagnostics now select recovery object 0.
For object 0, `p10_dual_xsdb_stage.tcl` already enforces this order:

1. publish the receiver command;
2. directly verify receiver runtime state `PRIMED` and PL object-active;
3. publish the sender command.

The repair is diagnostic-only. It does not add a normal-stream host or optical
ready exchange, does not change the selective-repeat data path, and does not
change `GLOBAL_PERMIT`, SD, Mode, final Txd kill, rolling-duty, continuous-high,
first-fault freeze, or shutdown behavior.

## Acceptance boundary

The firmware change requires a new immutable P10.4 artifact bundle and a fresh
full hardware campaign. No result from the superseded bundle is inherited. The
new campaign must again execute every mandatory stage, archive all evidence,
and verify both endpoints shut down on every exit.
