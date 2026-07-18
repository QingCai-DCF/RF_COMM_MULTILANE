# P8E AXI DMA static integration

`rtl/platform/axi_dma_adapter.sv` is the vendor isolation boundary. The portable core receives AXI-Stream `TVALID/TREADY/TDATA/TKEEP/TLAST` and explicit descriptor/completion handshakes; a future AXI DMA SG block design remains outside the common core.

The adapter contains independent one-beat skid stages for MM2S and S2MM, holds descriptor commands until accepted, holds completions until reclaimed, increments a generation on abort, and consumes stale completions while discarding them. Consuming a stale vendor record is required: leaving its ready signal low would deadlock a level-valid producer and count one stale record repeatedly. The offline test covers TX/RX backpressure, partial final `TKEEP`, `TLAST`, descriptor completion, abort, stale-generation rejection, and stale-completion forward progress.

PS7 DDR configuration, cache coherency, BSP/runtime ownership, and real vendor-IP execution remain `PENDING_P9_OR_P10`. No real AXI transaction or PS ELF is used by P8E.
