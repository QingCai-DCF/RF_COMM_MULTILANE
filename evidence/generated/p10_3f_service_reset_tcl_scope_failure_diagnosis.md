# P10.3F service-reset Tcl scope failure diagnosis

- Status: `PASS` (diagnosis only; no hardware action)
- Immutable failed run: `p10_3f_full_20260805T045828Z_d6e55e3d_1ff0885f_82ef5093`
- Artifact source: `7fc3a7cb03f9ee19793403f9f1deaef139b11d7d`
- Host source: `d6e55e3d55812c28b776b3dee8480b1fe4e13c8b`
- Old run reclassified: `false`

All stages preceding the controlled service-reset stage passed. The service-reset
stage established the expected board identities and safe boot, then failed before
reset execution with `can't read "p10_dump_dir": no such variable`.

The direct cause is a Tcl scope omission: `p10_execute_ps_service_reset` writes
its shutdown-before-reset evidence beneath `p10_dump_dir`, but the procedure did
not declare that top-level variable as global. This is a host/Tcl runtime defect;
it is not evidence of a link, module, FPGA artifact, or TFDU safety failure.

Both forensic archives correctly remained `NO_FAULT`, and the runner subsequently
programmed and verified the independent shutdown bitstreams on both boards. The
complete run remains `FAIL`; its earlier stage results are preserved as partial
evidence and are not inherited by a retry.

The fix must declare `p10_dump_dir` global in the service-reset procedure and add
a regression check that would catch the missing binding. The immutable
bitstream/XSA/BSP/ELF bundle remains unchanged, but a new host-source checkpoint,
offline freeze, current-run authorization, complete campaign, and verified final
shutdown are required.
