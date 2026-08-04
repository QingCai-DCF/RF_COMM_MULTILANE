# P10.3 lane2 raw-connectivity retest after R2 replacement

- Result: `PASS`
- Evidence class: `RAW_PHYSICAL_ONLY`
- Run ID: `p10_3_raw_20260804T114152Z_d4eef729_3d8cd207_a8459eef`
- Active pair: `F2=B0001` ↔ `R2=B0023`
- Historical removed R2: `B0015` (historical evidence retained)
- Lane mask used: `0x4`

| Direction / requested pulses | Result | Sender final-path TX count | Remote raw RX count | Max TX-high cycles |
|---|---|---:|---:|---:|
| F2_TO_R2 / 64 | PASS | 64 | 64 | 8 |
| F2_TO_R2 / 1024 | PASS | 1024 | 1024 | 8 |
| R2_TO_F2 / 64 | PASS | 64 | 64 | 8 |
| R2_TO_F2 / 1024 | PASS | 1024 | 1024 | 8 |

Shutdown fixed: `PASS`; rotating: `PASS`.

## Immutable artifacts

- fixed shutdown_bitstream: `027159d3b028aa164ed25858c868b70bc014514c0f220af731c82470cbcafc28` — `artifacts/p10_3/d4eef729e91c60fc7a72fa68c95fcd4a569fcffc/027159d3b028aa164ed25858c868b70bc014514c0f220af731c82470cbcafc28/p10_ax7020_fixed_shutdown.bit`
- fixed functional_bitstream: `3d8cd20747f311c9467f4269bc7b10d7d16ffaeca4e5d888a15a8e883dbf5bcd` — `artifacts/p10_3/d4eef729e91c60fc7a72fa68c95fcd4a569fcffc/3d8cd20747f311c9467f4269bc7b10d7d16ffaeca4e5d888a15a8e883dbf5bcd/p10_ax7020_fixed_functional.bit`
- fixed elf: `f4c9bd6fa8ae8bbbad3a927f19759c8605c253258613d72271c8aa202e27fa3a` — `artifacts/p10_3/d4eef729e91c60fc7a72fa68c95fcd4a569fcffc/f4c9bd6fa8ae8bbbad3a927f19759c8605c253258613d72271c8aa202e27fa3a/p10_fixed_runtime.elf`
- rotating shutdown_bitstream: `204d79b7f01fc6b755316c011d09df958996c0ee9628b68492b842ff28e2847d` — `artifacts/p10_3/d4eef729e91c60fc7a72fa68c95fcd4a569fcffc/204d79b7f01fc6b755316c011d09df958996c0ee9628b68492b842ff28e2847d/p10_ax7020_rotating_shutdown.bit`
- rotating functional_bitstream: `a8459eeff9df4373f80112e5cc5892864900eeb95afd6a5bb949008d52262846` — `artifacts/p10_3/d4eef729e91c60fc7a72fa68c95fcd4a569fcffc/a8459eeff9df4373f80112e5cc5892864900eeb95afd6a5bb949008d52262846/p10_ax7020_rotating_functional.bit`
- rotating elf: `fd2edb95306323e4c8796368d3425487994e7471b115b8543d20053f10d6f01a` — `artifacts/p10_3/d4eef729e91c60fc7a72fa68c95fcd4a569fcffc/fd2edb95306323e4c8796368d3425487994e7471b115b8543d20053f10d6f01a/p10_rotating_runtime.elf`

## Scope boundary

This result concerns only bidirectional lane2 raw pulse connectivity. It does not constitute framed-data, ARQ/SACK, DMA, streaming, four-lane, external electrical, module-health, P11, rotating, or final-product acceptance. The module identity and replacement are user-provided; Codex did not independently read the small-board marking or perform the replacement.
