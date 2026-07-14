# Stage62 specialist disassembly check

Exact clean-checkpoint artifacts:

- ELF:
  `evidence/hardware/p7/artifacts/p7_runtime_9f13ce1e340897fc159f40ac45a66099a70717411a587f922a424f217f0b0570.elf`
- ELF SHA256:
  `9f13ce1e340897fc159f40ac45a66099a70717411a587f922a424f217f0b0570`
- linker map:
  `evidence/hardware/p7/artifacts/p7_runtime_1c384c9520879150e255769f623fbd5e92ffb9db27be09d75ead698d7d1f07e1.map`
- map SHA256:
  `1c384c9520879150e255769f623fbd5e92ffb9db27be09d75ead698d7d1f07e1`

Verified build facts:

- `stage62_microtest_copy`: LDRB count 2, STRB count 2, DSB count 1.
- Forbidden `memcpy`/`memmove` calls in that helper: false.
- `p7_stage62_microtest_try_run` stack usage: 112 bytes.
- Configured microtest stack limit: 1024 bytes.
- Complete build summary SHA256:
  `3da6fa01a45b389545ca7193e3f1e423aa30ae88aa0e4d3399029cfbde19c8f6`.

These checks prove the exact firmware construction only. R37 stopped at the
host/XDSB DDR prestart readback gate before the microtest function ran, so the
disassembly is not evidence that its Case B copy executed or passed.
