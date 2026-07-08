# RF_COMM P2 UART Operator

This directory contains the host-side runner for the P2 UART operator control surface.

The UART operator is not Ethernet, TCP, DHCP, or PC-to-PC networking. It is a direct serial control path for the current constrained static baseline:

- payload lane mask: `0x1`
- ACK/RX lane mask: `0x1`
- default payload: `256` bytes
- default stage: `300` seconds
- AB lane 1 remains excluded

## Build Operator ELF

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build_p2_uart_operator_elf.ps1
```

This only builds the PS ELF. It does not program hardware, write UART, or drive TFDU.

## Run Acceptance Transcript

Preferred safe wrapper from the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_p2_uart_operator_control_safe.ps1
```

The wrapper checks hardware preflight, temporarily copies the preserved operator ELF into the Vitis workspace, starts the host transcript runner, programs the board through `software/ps_ps_loopback/run_on_hw.tcl`, runs shutdown afterward, and restores the previous workspace ELF.

Manual mode is also available after programming the operator ELF on hardware and confirming the UART boot log prints `UARTOP_READY`:

```powershell
python .\software\host_uart_operator\rf_comm_uart_operator.py --port COM3 --baud 115200 --transcript .\reports\P2_uart_operator_control_transcript.log
```

The runner sends the required P2 command sequence:

```text
STATUS
CONFIG lane_mask 0x1
CONFIG ack_mask 0x1
CONFIG payload_bytes 256
CONFIG stage_seconds 300
READ counters
CLEAR error
START
STOP
READ counters
SHUTDOWN
```

It writes `UART_OPERATOR_CONTROL_PASS=1` only when every command returns `rc=0` and the `START` result has clean counters (`sent == rx_ok`, no tx/rx failures, `loss=0.0%`, `last_error=none`).

For a quick command-surface smoke test, override the run duration:

```powershell
python .\software\host_uart_operator\rf_comm_uart_operator.py --stage-seconds 5
```

The full P2 claim should use the generated transcript under `reports/P2_uart_operator_control_transcript.log`.

## Run PS-PL Data Exchange Transcript

The PS-PL data-plane verification uses the current workspace ELF and the current bitstream. It does not use the preserved control-only ELF.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_p2_pspl_data_exchange_safe.ps1
```

The wrapper performs JTAG/UART preflight, programs the board, runs the host tool in data-plane mode, and always programs the TFDU shutdown bitstream afterward. The host command equivalent is:

```powershell
python .\software\host_uart_operator\rf_comm_uart_operator.py --mode pspl-data --port COM3 --baud 115200 --payload-bytes 256 --tx-count 100 --rx-stress-count 10000
```

The data-plane mode runs AXI-Lite read/write checks, short TX DMA MM2S checks, and the RX DMA synthetic matrix. It writes `UART_OPERATOR_PSPL_DATA_PASS=1` only when every `RESULT test_id=...` line passes with no TX/RX errors.

## P3 Result Schema

The P3 UART result schema separates TX-only ACK acceptance from S2MM RX payload verification:

```text
RESULT test_id=TX_DMA pass=<0|1> payload_bytes=<N> count=<N> sent=<N> ack_ok=<N> tx_fail=<N> tx_payload_bytes=<N> last_error=<text>
RESULT test_id=RX_DMA_SYNTH pass=<0|1> source=synthetic_internal payload_bytes=<N> count=<N> injected_packets=<N> dma_rx_packets=<N> rx_ok=<N> rx_timeout=<N> rx_bad=<N> rx_mismatch=<N> rx_payload_bytes_verified=<N> first_bad_seq=<N> first_bad_offset=<N> last_error=<text>
RESULT test_id=PSPL_ROUNDTRIP pass=<0|1> payload_bytes=<N> count=<N> seconds=<N> sent=<N> tx_ok=<N> tx_fail=<N> dma_rx_packets=<N> rx_ok=<N> rx_timeout=<N> rx_bad=<N> rx_mismatch=<N> rx_payload_bytes_verified=<N> failure_class=<text> last_error=<text>
```

`TEST pspl_roundtrip` supports either a packet count or a bounded duration:

```text
TEST pspl_roundtrip payload=<N> count=<N>
TEST pspl_roundtrip payload=<N> seconds=<N>
```

`count` and `seconds` are mutually exclusive. `seconds` is capped at 600 seconds by the PS build.

Additional P3 host modes:

```powershell
python .\software\host_uart_operator\rf_comm_uart_operator.py --mode p3-rx-stress --port COM3 --baud 115200
python .\software\host_uart_operator\rf_comm_uart_operator.py --mode p3-negative --port COM3 --baud 115200
python .\software\host_uart_operator\rf_comm_uart_operator.py --mode p3-roundtrip --port COM3 --baud 115200
```
