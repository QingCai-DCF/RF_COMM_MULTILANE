# P8B crossbar and path-epoch specification

## Explicit 8x8 data paths

`ir_path_mapping_engine` exports lane-to-current/candidate fixed index, bank and slot as complete packed vectors. `ir_bank_lane_crossbar` constructs both inverse owner maps and routes distinguishable `bank_current_rx` and `bank_candidate_rx` data to each logical lane. Reset or an invalid/duplicate owner mapping forces every output valid low. A candidate RX path is observable for acquisition but never becomes a TX owner before commit; TX ownership is derived only from the active current permutation.

The active mapping is one coherent register bank. A prepare writes only the shadow bank after both mappings pass permutation/owner checks. A commit event copies all lane/bank/slot vectors on one clock edge. Per-lane writes and mixed epochs are not interfaces of the module.

## Commit contract

An accepted commit requires all of:

```text
phase_valid
shadow_valid
mapping_checks_pass
quiet_or_frame_boundary
no_fatal_mapping_fault
```

The request is edge-qualified. Holding it high emits one event and increments `path_epoch` once; a rejected edge does not increment. Reset initializes the epoch and both mapping banks deterministically. The epoch counter wraps modulo `2^EPOCH_WIDTH`; matching is exact equality, not signed or ordering comparison. Session epoch remains a separate higher-level responsibility.

Readback, frame, ACK and object/path status metadata each have an explicit current-epoch comparison. Stale metadata cannot complete a current transaction. Active mapping service continues during prepare; reversal, phase-context change or reset invalidates the shadow and cannot alter active service without a new accepted commit.

This P8B ownership/epoch model does not implement P8C physical TX kill, rolling duty, pulse limit, frame admission or the final single `GLOBAL_PERMIT` path.

