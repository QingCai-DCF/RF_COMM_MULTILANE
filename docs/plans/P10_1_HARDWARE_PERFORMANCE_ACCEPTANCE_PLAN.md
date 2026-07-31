# P10.1 hardware performance acceptance plan

Status: `PENDING_CURRENT_RUN_AUTHORIZATION`

This plan is not a hardware authorization. The offline checkpoint keeps
`NO_HARDWARE=1`, executes no JTAG operation, does not program either FPGA,
does not start either PS ELF, does not drive a TFDU, and does not use Ethernet
or motion.

## Immutable admission inputs

A future run must bind, by exact value and SHA-256:

- fixed board `AX7020-F/JTAG:210249855178`, fixed-role profile/XDC, bitstream,
  and fixed-role performance ELF;
- rotating-role board `AX7020-R/JTAG:210512180081`, rotating-role profile/XDC,
  bitstream, and rotating-role performance ELF;
- P10.1 register map, measurement contract, pipeline/streaming configuration,
  lane mask no wider than `0x3`, and a bounded maximum runtime;
- a new current-run authorization naming the run and immutable artifacts.

Cable enumeration order is not an identity. A mismatch in either serial,
artifact hash, role, profile, XDC, lane mask, or register-map version rejects
the run before any hardware service is opened.

## Bounded sequence

1. Validate authorization and all immutable hashes offline.
2. Resolve both exact board identities.
3. Execute shutdown-before and record both endpoint acknowledgements.
4. Safe boot with TFDU shutdown asserted and Txd low.
5. Run a bounded raw smoke, then a bounded object-integrity smoke.
6. Cross-calibrate PL and PS timers on both endpoints.
7. Run sustained F→R and R→F independently with host absent from the segment
   fast path.
8. Run the 64 MiB atomic-stream case only after both short cases pass.
9. Run the 30-minute formal performance window only after all earlier gates
   pass.
10. Stop, collect immutable evidence, and execute shutdown-after.

Shutdown is mandatory before the run and on error, timeout, Ctrl+C, normal
exit, and final completion. Missing `SHUTDOWN_EXIT=0`,
`TFDU_SHUTDOWN_PROGRAMMED`, or a stage-approved equivalent makes the run
incomplete.

## Formal acceptance

Application goodput uses only remotely verified and atomically committed
application bytes from first formal application admission to final remote
commit. Warm-up, initialization, host staging, JTAG setup, evidence export,
diagnostic microtransfers, headers, CRC/SACK/padding, retries, and failed or
partial objects are excluded exactly as defined by
`config/performance/p10_1_measurement_contract.yaml`.

Both half-duplex directions must independently meet `>=4,000,000 bit/s`,
integrity errors and retry exhaustion must be zero, the timer crosscheck must
pass, and all TFDU safety/shutdown gates must remain PASS. The 4.8 Mbit/s
value is a stretch target, not a substitute for the hard target.

## Current offline dry-run

`scripts/run_p10_1_hardware_performance.py` validates the admission contract
and the required rejection vectors. It has no hardware execution path in this
checkpoint. Real AX7020 goodput and real 64 MiB streaming remain pending.
