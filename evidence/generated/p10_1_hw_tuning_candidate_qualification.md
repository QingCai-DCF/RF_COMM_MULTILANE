# P10.1 tuning candidate qualification

Status: **PASS** for qualifying the current artifact's supported descriptor
batch set. The remaining nine-candidate tuning plan still requires a hardware
retry.

Two independently authorized runs rejected `descriptor_batch=1`:

- `ring8 + batch1 + 64 KiB object` entered active transfer, then the fixed
  sender reported PL object error `0x50090004` (TX retry exhausted) and the
  rotating receiver reported DMA completion failure. No application commit
  or integrity error occurred.
- `ring16 + batch1 + 256 KiB object` held the default configuration constant
  except for batch size. The rotating receiver faulted while priming, before
  source launch.

Both runs ended with `SHUTDOWN_FIXED=PASS` and
`SHUTDOWN_ROTATING=PASS`; both current-run authorizations are consumed.

The direct evidence supports this bounded conclusion:

```text
artifact source: bfff483663e51862a0e1e4aed31940bd84d80cdb
descriptor_batch=1: unsupported for this artifact
supported hardware tuning set: [4, 8, 16, 32]
```

This is not extrapolated to a future rebuilt artifact or to product hardware.
Batch one may be reintroduced only after a new artifact and direct
requalification.

The active tuning plan removes the batch-one candidate. The XSDB receiver
prime error path now captures P10.1 state/status diagnostics before returning
a main-state fault. No bitstream or ELF changed.

Machine-readable evidence is in
`evidence/generated/p10_1_hw_tuning_candidate_qualification.json`.
