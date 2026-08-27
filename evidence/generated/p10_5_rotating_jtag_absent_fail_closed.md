# P10.5 rotating JTAG target absent — fail-closed audit

- Status: `FAIL_CLOSED`
- Current R3 identity: `B0011`
- Fixed target: `210249855178` — present; shutdown `PASS`
- Rotating target: `210512180081` — absent from both Windows PnP enumeration and Hardware Manager; shutdown `UNCONFIRMED`
- P10.5 stages executed: `0`
- TX executed: `false`

Two separately authorized immutable runs stopped at their initial shutdown-before gate. In both runs the fixed endpoint was found exactly once and programmed with the frozen shutdown bitstream, while the rotating endpoint had zero exact Hardware Manager targets. A subsequent read-only Windows device enumeration also listed only Digilent/FTDI serial `210249855178`; `210512180081` was absent. This rules against a target-filtering-only explanation and provides no optical or connectivity result for R3=`B0011`.

No new transmitting run may start while the rotating endpoint cannot be uniquely found and its shutdown cannot be confirmed. Existing B0025 evidence and all B0011 pending status remain unchanged.
