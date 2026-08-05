# P10.3F DMA-reset priming failure diagnosis

Status: `DIAGNOSED_NOT_PROMOTED`

The immutable run `p10_3f_full_20260805T015904Z_6f7063e9_1ff0885f_82ef5093` passed through the 64 MiB streaming stage, then failed closed before launching the selected sender in `stream_dma_reset_fault`. Both final shutdown verifications passed (`TFDU_SHUTDOWN_PROGRAMMED=1`, `SHUTDOWN_EXIT=0`).

The failed vector contained one 256 KiB internal object. Both endpoints received the role-selected `EXPECT_DMA_RESET_SENDER` flag. Because the runtime chooses `recovery_ordinal=object_count/2`, the receiver reached object 0, published only a transient primed state, and immediately completed its expected-abort path before XSDB could publish the fixed sender command. The final receiver observation was main state 4, P10.1 state 7 (`EXPECTED_ABORT`), sequence 1001, status 0.

The correction uses a 512 KiB aggregate made of two unchanged 256 KiB protocol objects. Object 0 establishes the receiver-first paired transfer. The reset remains on object 1, so the test retains real in-flight traffic, zero application commit, immediate PL kill/full shutdown, frozen evidence, and bounded execution. This changes the immutable host plan only; frozen bitstream/XSA/BSP/ELF hashes are not inherited as a new PASS and the complete campaign must run again under a new authorization and run ID.

Exact source evidence and SHA256 values are recorded in `p10_3f_dma_reset_prime_failure_diagnosis.json`.
