# Campaign B root-cause finding

Campaign B completed all ten pre-authorized diagnostic runs. Nine runs produced
sparse DDR readback corruption and one run passed. Every run completed both the
shutdown-before and shutdown-after sequences, programmed the frozen shutdown
bitstream after execution, reaped its process tree, and released the hardware
execution lock.

## What the matrix excludes

- B01 and B02 used the same address, fixture, and download path but failed at
  different offsets, so the fault is not a deterministic fixture byte or one
  fixed address.
- B03 moved the transfer window from `0x00900000` to `0x00900100`; sparse
  corruption moved with the window.
- B04 corrupted both `0x5A` and `0xA5`, so the historical `0xC3` signature is
  not a value-specific software transform.
- Download, block-file, byte, halfword, and word writes all produced failures.
  The fault is therefore below any one host write API or packing width.
- B06 reached the real unaligned halfword write and captured readback without
  the old plural-option error. The runner option correction is proven, but it
  is not the DDR root fix.
- B08 reproduced the original Stage 62 first bad address exactly:
  `0x00900009`, expected `0xC3`, observed `0x00`.

## Proven configuration defect

The canonical P6 build creates `processing_system7` with board-preset
application disabled and sets no DDR device part. Vivado therefore generated
the platform for its default `MT41J128M8 JP-125` topology: x8 devices,
1024-Mbit per device, and `tFAW=30.0`.

The AX7010 manufacturer manual states that this board carries two SKHynix
H5TQ2G63FFR-RDC 2-Gbit x16 devices, compatible with
`MT41J128M16 HA-125`, for a 32-bit, 4-Gbit/512-MiB memory system. The imported
legacy PS7 XCI independently selects the same compatible x16 Micron part. Its
72 DDR parameters differ from the generated candidate in exactly four fields:

| Parameter | Current candidate | AX7010 requirement |
| --- | --- | --- |
| `PCW_UIPARAM_DDR_PARTNO` | `MT41J128M8 JP-125` | `MT41J128M16 HA-125` |
| `PCW_UIPARAM_DDR_DRAM_WIDTH` | `8 Bits` | `16 Bits` |
| `PCW_UIPARAM_DDR_DEVICE_CAPACITY` | `1024 MBits` | `2048 MBits` |
| `PCW_UIPARAM_DDR_T_FAW` | `30.0` | `40.0` |

This topology/timing mismatch explains sparse, run-varying corruption across
addresses, values, access widths, and host APIs. The configuration defect is
proven. Hardware confirmation of causality still requires a rebuilt artifact
and a separately authorized new run; Campaign B authorizations are consumed.

## Minimal fix boundary

Set the compatible AX7010 DDR part explicitly in
`scripts/build_p6_ps_candidate.tcl`, then fail the build unless Vivado derives
the expected x16 device width, 2048-Mbit device capacity, and `tFAW=40.0`.
Do not copy or modify the legacy project. Rebuild the bitstream/XSA/platform,
rerun offline gates, freeze every new hash, and request fresh authorization
before touching hardware.

Primary board reference:
<https://alinx.com/public/upload/file/AX7010_User_Manual.pdf>
