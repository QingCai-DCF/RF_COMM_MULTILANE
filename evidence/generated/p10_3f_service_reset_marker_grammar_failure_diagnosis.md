# P10.3F service-reset marker grammar failure diagnosis

- Status: `PASS` (diagnosis only; no hardware action)
- Immutable failed run: `p10_3f_full_20260805T055527Z_4ae863a8_1ff0885f_82ef5093`
- Artifact source: `7fc3a7cb03f9ee19793403f9f1deaef139b11d7d`
- Host source: `4ae863a86cb07b3a3b176aa7656a1575c5b59cd6`
- Old run reclassified: `false`

The controlled service-reset mechanism itself completed successfully. Both PL
endpoints entered full shutdown before processor reset, the final physical-TX
counters remained stable, the selected and peer services rebooted, and both
endpoints were read back in the safe recovered state. The two forensic archives
correctly remained `NO_FAULT`. The runner then independently programmed and
verified both shutdown bitstreams.

The host-stage failure is a marker namespace mismatch. Tcl emitted keys such as
`P10_SAFE_STATE_FIXED_stream_service_reset_receiver_RECOVERED`. The evidence
parser intentionally accepts only marker keys matching `[A-Z0-9_]+`, so these
lowercase dynamic keys were discarded before evaluation. This made the host
report the recovered status, PHY state, and physical-TX vector as missing even
though all six values are present and safe in the raw XSDB result.

The correction is to emit a stable all-uppercase recovered marker label, make
the evaluator require that exact canonical key, and add a regression that first
parses the raw marker text and then exercises the evaluator. The immutable
bitstream/XSA/BSP/ELF bundle remains unchanged. This run remains `FAIL`; earlier
stage PASS results are preserved only as partial evidence and are not inherited
by a retry. A new offline freeze, current-run authorization, complete campaign,
and verified final shutdown are required.
