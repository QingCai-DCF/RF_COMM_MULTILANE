# P11 hardware prerequisites

```text
P11_OFFICIAL_STAGE_STATUS: NOT_STARTED
P11_HARDWARE_READY: false
CURRENT_RUN_HARDWARE_AUTHORIZATION: false
```

P11 is blocked on direct hardware inputs. Offline P10.1 work does not start
P11 and does not promote any rotating, handover, 8×32, 600 rpm, or final
product scope.

Required before a P11 hardware run:

- a fifth compatible TFDU6102 small board with identity, revision, pinout,
  electrical structure, and supply requirements bound to evidence;
- a four-fixed-module fixture at 11.25° spacing and a one-rotating-module
  fixture, referenced to the canonical nominal D200/D600 geometry;
- a selected ABZ encoder and interface with PPR, A/B/Z electrical standard,
  maximum edge rate, filtering, direction behavior, Z/acquisition strategy,
  phase error, uncertainty, data-age, and reacquisition budgets;
- a bounded controllable bidirectional motion source, guard/exclusion zone,
  independent emergency stop, and the single-per-endpoint permit/shutdown
  architecture;
- a P11-specific board profile, wiring record, pinmap, XDC, I/O-bank/VCCO
  audit, clock/reset/CDC constraints, and immutable build artifacts;
- a new explicit current-run authorization and bounded safe runner.

The fifth module, fixtures, ABZ path, motion source, and P11 profile/XDC are
not present as accepted hardware inputs at this checkpoint.
