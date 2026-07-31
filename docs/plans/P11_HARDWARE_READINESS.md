# P11 hardware readiness

P11_HARDWARE_READY: `false`

P11_OFFICIAL_STAGE_STATUS: `NOT_STARTED`

CURRENT_RUN_HARDWARE_AUTHORIZATION: `false`

The current setup has four TFDU modules total: F0/F1/R0/R1. P11 requires at least five simultaneously available modules (one rotating-role module and four fixed modules), so the existing hardware cannot satisfy the proposed P11 topology.

## Missing prerequisites

- At least one additional compatible TFDU module, yielding one rotating plus four fixed modules.
- A mechanically defined four-fixed-module fixture.
- A mechanically defined rotating-module fixture.
- A verified ABZ/phase input path and pin/profile definition.
- A bounded, controllable motion source suitable for handover testing.
- A P11-specific wiring/profile/XDC package and immutable artifact set.
- A new explicit current-run hardware authorization and safe wrapper.

No P11 implementation or hardware execution may be marked in progress until these prerequisites are resolved. P10.1 offline analysis may proceed independently; P10.1 hardware experiments still require their own new authorization.
