# P10.3F service-reset classifier failure diagnosis

- Status: `PASS` (diagnosis only; no hardware action)
- Immutable failed run: `p10_3f_full_20260805T035439Z_d1227f1a_1ff0885f_82ef5093`
- Preservation commit: `bb8a2290b5c5114d5fcb773708d75e9ad22e0588`
- Artifact source: `7fc3a7cb03f9ee19793403f9f1deaef139b11d7d`
- Old run reclassified: `false`

The selected PS service reset and both service reboots completed, and both
endpoints were directly verified in the recovered safe state. Both PL forensic
archives correctly remained `NO_FAULT` with cause zero, TX kill asserted, and
effective full shutdown asserted. The run failed because the shared
`STREAMING_FAULT` classifier incorrectly demanded a fabricated frozen
terminal-object cause for this controlled recovery vector.

The correction leaves the immutable RTL/bitstream/XSA/BSP/ELF bundle unchanged.
Real TFDU safety faults and terminal object failures still require immediate
hardware kill/full shutdown and frozen two-role archives. The service-reset
stage instead must prove PL shutdown before processor reset, zero effective TX,
stable final physical-TX counters, exact two-role `NO_FAULT` archives, both
reboots, and both recovered-safe states. A new offline freeze, authorization,
complete hardware campaign, and final verified shutdown are required.
