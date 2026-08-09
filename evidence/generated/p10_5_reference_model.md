# P10.5 dual-direction offline reference model

- Status: `PASS`
- Hardware actions executed: `false`
- Protocol events: `100000`
- ACK/control events: `50000`
- DMA/backpressure events: `50000`
- Role/reset events: `25000`
- 1+1 ordered pairs: `12`
- 2+1 / 1+2 cases: `12` / `12`
- Directed 2+2 partitions: `6`
- Modeled per-direction goodput: `4537313` bit/s
- 4.0 Mbit/s feasibility: `PASS`
- 4.8 Mbit/s stretch: `FAIL_NONBLOCKING`

All safety, direction-isolation, stale-generation, unique-commit,
descriptor-ownership, bounded-ACK, and no-deadlock invariants passed.
