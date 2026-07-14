# Iteration 04 conclusion

R37 failed before the Case B firmware copy. The external prestart write/readback
of the DDR destination fixture at `0x00900000` contained exactly one mismatch:
offset 9 (`0x00900009`) expected `0xC3`, observed `0x00`. The intended copy
target begins at offset 64. OCM source and control readbacks were exact.

The run therefore does not support a firmware Case B result. It does establish
a lower-level DDR/external-master boundary failure before application code. The
precise mechanism is unresolved and is outside the specialist scope. Per the
hard stop rule, Cases C/D and all further hardware runs are prohibited here.
Shutdown-after and independent recovery-only both passed.
