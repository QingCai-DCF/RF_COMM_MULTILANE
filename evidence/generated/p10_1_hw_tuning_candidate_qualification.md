# P10.1 tuning candidate qualification

Status: **PASS** for qualifying the current artifact's supported descriptor
batch set and for the resulting nine-candidate hardware tuning plan.

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

Run `p10_1_hw_20260801T033309Z_bfff4836_1585d1ad_9ad4f85f` then completed all
nine supported candidates with both shutdown markers at `PASS`. Its best
candidate was `buffer=4`, `ring=32`, `batch=8`, `object=512 KiB`, with measured
application goodput `2,588,639.5636545448 bit/s`. This measurement selects the
configuration for the subsequent sustained-pipeline stage; it does not satisfy
or weaken the separate 4.0 Mbit/s hardware performance gate.

Machine-readable evidence is in
`evidence/generated/p10_1_hw_tuning_candidate_qualification.json`.
