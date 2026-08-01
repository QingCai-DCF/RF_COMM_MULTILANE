# P10.1 retry-limit override authorization audit

## Result

`P10_1-HW-RETRY-LIMIT-OVERRIDE: PASS`

The user explicitly authorized “不设上限” for the Goal section 23 counters covering JTAG connections, programming attempts, and new diagnostic-stage run IDs. This authorization remains restricted to the existing P10.1 hardware campaign.

## Effective policy

The three section 23 retry counters no longer stop the campaign. Every actual attempt must still receive a new, unique, immutable current-run authorization. The campaign-level record is an authorization source only and cannot directly open hardware gates.

The following constraints remain unchanged:

- each formal run is at most 1800 seconds;
- lane masks are only `0x1`, `0x2`, and `0x3`;
- Ethernet, movement, rotation, angle adjustment, obscuration, module exchange, and rewiring remain prohibited;
- board roles remain fixed/JTAG `210249855178` and rotating/JTAG `210512180081`;
- every retry requires shutdown-before;
- error, timeout, Ctrl+C, normal exit, and final exit require verified shutdown of both endpoints.

## Frozen runtime binding

- fixed performance bitstream: `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- fixed ELF: `5dbf7e2668b1ddac9f742085d907c90324b7ca931dc47e932ae70dcd8881f4e6`
- rotating performance bitstream: `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- rotating ELF: `9b9bef44b65b3f08ca9442d2d577bdbdc79db2d2d8da3991eb93a4b1dd5946a0`
- fixed shutdown bitstream: `d849da80c485519ae6300398cdf0b09dc5838941bd14bdf71cb26c01ec9e3fe3`
- rotating shutdown bitstream: `cf269e67f2f7aa246b792d5c378168e10913d2af10ccd5dcd5a97b62f679b148`

The machine-readable source is `config/p10_1_retry_limit_override_authorization.json`; the machine-readable audit is `evidence/generated/p10_1_hw_retry_limit_override_summary.json`.

No hardware action was performed while creating or validating this override.
