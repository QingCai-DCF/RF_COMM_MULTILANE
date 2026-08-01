# P10.1 deterministic duplicate-DATA hardware checkpoint

Stage status: **PASS (`faults` only)**  
Campaign status: **not complete / finalizer FAIL**  
Run ID: `p10_1_hw_20260801T062855Z_bb6ce78a_1585d1ad_9ad4f85f`

The current AX7020 pair directly observed the deterministic duplicate-DATA vector. The rotating receiver counted three injected duplicate events, committed zero bytes during the fault vector, and recorded no duplicate commit, CRC error, integrity error, or retry exhaustion. Its 64 MiB clean successor then completed one atomic commit at `2,585,496.21 bit/s` with all integrity counters zero.

The complete faults stage passed 19 observations: nine recovery vectors and nine post-recovery clean successors, plus endpoint shutdown. XSDB returned zero after `2635.68 s` without timeout.

Both boards were shut down successfully on all exit paths. The verified post-shutdown state has `active_tx_mask=0`, `endpoint_armed=0`, `SD_REQUEST_ACTIVE=1`, and `TXD_OUTPUT_INTENT=0`. No Ethernet, network data path, movement, rotation, or rewiring was used; the maximum lane mask was `0x3`.

The final campaign gate correctly remains FAIL because this immutable run contained only `faults`; the new ELF hashes have not yet rerun preflight, smoke, baseline, tuning, pipeline, streaming, crosstalk, half-duplex, 1+1, or formal. Historical results from the old ELF bundle are not inherited.

Machine-readable evidence: `evidence/generated/p10_1_hw_duplicate_past_sequence_hardware_checkpoint.json`.
