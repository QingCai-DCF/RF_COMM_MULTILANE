# Disassembly check

Status: PASS_OFFLINE_ONLY

- ELF SHA256: `2effbb1d207a2fbbc5940047d8d844a68dd8d82e70709aa9d120c00c4159596f`
- Disassembly SHA256: `75df29490407fe651009b152fef6b415204f64aaa07093a92af74d541704ad58`
- `p7_copy_bytes_verified` contains LDRB, STRB and DSB instructions.
- first-error publication and Stage 62 diagnostic helpers passed the build-time disassembly gates.
- `.p7_stage62_diagnostic` is a 1536-byte SHF_ALLOC/SHT_NOBITS section at `0x00021000`.

No hardware claim is made by this check.
