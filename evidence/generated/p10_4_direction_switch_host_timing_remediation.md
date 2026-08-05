# P10.4 direction-switch host timing remediation

- Status: `PASS`
- Classification: `HOST_JTAG_POST_TERMINAL_EVIDENCE_CAPTURE_LATENCY`
- Prior run remains: `PARTIAL`
- Fixed shutdown: `PASS`
- Rotating shutdown: `PASS`
- Hardware actions executed by this remediation: `false`
- Frozen artifact bundle changed: `false`
- Post-terminal observation overrun bound: `15000 ms`
- New hardware run authorization required: `true`
- Offline gates: `14/14 PASS`

The host executor now separates endpoint-terminal board-active time from
mandatory post-terminal evidence-read latency, records both, admits no new case
after the scheduled deadline, and fails closed if evidence latency exceeds the
finite bound. Hardware TX-kill and first-fault logic are unchanged.
