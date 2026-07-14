# Stage62 specialist iteration summary

## Iteration 01 / R33

The planned diagnostic suffix was rejected during offline generation because
the wrapper conflated the normal OCM image end with the intentionally separate
fixed diagnostic section. No sequence plan, ledger, Vivado, XSDB, FPGA program,
or ELF start occurred. The ID was retired. Fail-closed section-aware validation
was implemented and tested.

## Iteration 02 / R35

The first isolated Case A launch reached raw terminal markers, but the official
host postprocessor raised a missing-symbol `NameError`; a post-hoc replay also
rejected stale COPY_OK metadata. R35 is diagnostic-invalid and acceptance-
invalid. Both wrapper shutdown barriers and an independent recovery passed.
The host import and successful-record initialization were fixed in separate
commits, then complete suites and a fresh cache-bypassed build ran.

## Iteration 03 / R36

The corrected Case A OCM-to-OCM control passed under a new ID. The official
record classified `COPY_OK`, source-before equaled source-after, final
destination readback matched, wipe verified, and both shutdown barriers passed.
This is a zero-coverage control result only.

## Iteration 04 / R37

Case B planned OCM-to-DDR. Before CPU release, the immutable DDR destination
fixture readback differed at exactly offset 9: expected `0xC3`, actual `0x00`.
The failure at `0x00900009` precedes the intended copy target `0x00900040`.
OCM source/control readbacks were exact. No firmware microtest record or
Stage62 result exists. Wrapper shutdown-after and independent recovery passed.

## Stop decision

The objective explicitly requires the specialist to stop if an independent DDR
microtest also fails and to return the investigation to the main thread for PS
interconnect, DDR controller/init/training, board DDR, or external-master work.
That condition is met. Cases C/D and further specialist hardware launches were
not attempted.
