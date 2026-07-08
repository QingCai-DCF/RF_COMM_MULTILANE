PS lwIP bridge
==============

Purpose
-------

This is the first PS software entry point for the project goal:

- Bring up Zynq-7010 Ethernet using lwIP.
- Prefer DHCP and fall back to a static address when DHCP is not available.
- Accept one TCP client from the PC upper-computer side.
- Bridge PC payloads into the IR PL link through AXI DMA.
- Forward received IR payloads back to the PC over TCP.
- Expose status/sticky and per-lane health counters for robustness testing and
  rotating-side route observation.

Current scope
-------------

The current PL configuration is the single-lane 4 Mbit/s bring-up target. The
default bridge limits one application payload to 248 bytes because the default
PL packet limit is 256 bytes and the PS bridge adds an 8-byte IR application
header to preserve the true received length on the DMA receive side. For the G1
256-byte application-payload target, build the PL with `IR_MAX_PACKET_BYTES=264`
and the PS bridge/PS-PS loopback ELF with `IR_HW_MAX_PACKET_BYTES=264`; keep
`IR_HW_RX_TRANSFER_BYTES` at or below the same raw packet limit.

This is a bring-up bridge, not the final 32 Mbit/s half-duplex or 16 Mbit/s
per-direction full-duplex throughput implementation. The final throughput
target should add larger streaming windows, sustained throughput logging, and
packet-loss statistics. Under the active safety rule, physical continuous
TFDU/TX operation is capped at 600 seconds; longer historical stability goals
are treated as 600-second physical acceptance runs plus offline/equivalent
model evidence until the constraint is explicitly changed.

Vitis 2023.1 setup
------------------

Run the reproducible XSCT build from the repository root:

```powershell
& 'D:\Xilinx\Vitis\2023.1\bin\xsct.bat' '.\software\ps_lwip_bridge\build_vitis.tcl'
```

The script creates a generated workspace at `../_vitis_ws`, builds a platform
from `../../TFDU_VFIR_Client_Array/design_shiboqi_wrapper.xsa`, imports `src`,
and builds:

```text
../_vitis_ws/rf_comm_ps_bridge/Debug/rf_comm_ps_bridge.elf
```

Board run
---------

After the bitstream and ELF exist, connect the board through JTAG and run:

```powershell
& 'D:\Xilinx\Vitis\2023.1\bin\xsct.bat' '.\software\ps_lwip_bridge\run_on_hw.tcl'
```

The script programs:

```text
../../TFDU_VFIR_Client_Array/design_shiboqi_wrapper.bit
../_vitis_ws/rf_comm_ps_bridge/Debug/rf_comm_ps_bridge.elf
```

The run scripts still prefer the Vivado `impl_1` bitstream path when it exists,
and fall back to this copied handoff bitstream for direct-build workflows.

It then starts the PS bridge. Watch the UART log for the DHCP result or static
fallback IP address, then connect from the PC to TCP port 5001.

SD boot image
-------------

For untethered stability runs, generate a Zynq boot image from the current FSBL,
bitstream, and PS bridge ELF:

```powershell
.\tools\build_boot_image.ps1
```

The output is:

```text
software/_boot/BOOT.BIN
```

Copy `BOOT.BIN` to the FAT partition of the SD card, set the Zynq board boot
mode to SD, then power-cycle the board. Use the UART log to confirm DHCP or
static fallback IP before running PC-side acceptance tests.

Manual setup is also possible:

1. Create a Vitis platform from `../../TFDU_VFIR_Client_Array/design_shiboqi_wrapper.xsa`.
2. Use processor `ps7_cortexa9_0`, OS `standalone`.
3. Use the Xilinx `lwIP Echo Server` template or enable the `lwip213` BSP library.
4. Import the files in `src`.
5. Build and run on the board.

Network behavior
----------------

- TCP port: 5001
- DHCP timeout fallback address: `192.168.10.2/24`, gateway `192.168.10.1`
- MAC address default: `00:0A:35:00:01:10`

PC protocol
-----------

TCP frames use this binary header:

```text
byte 0..3  magic: "RFCM"
byte 4     version: 1
byte 5     type
byte 6..7  sequence, little-endian
byte 8..11 payload length, little-endian
byte 12..  payload
```

Frame types:

- `0x01` HELLO
- `0x02` STATUS_REQ
- `0x03` STATUS_RSP
- `0x04` ACK
- `0x05` ERROR
- `0x10` TX_DATA, PC to IR link
- `0x11` RX_DATA, IR link to PC
- `0x20` CLEAR sticky status
- `0x21` CONFIG, update IR link configuration
- `0x22` COMMAND, ASCII N03 command surface

CONFIG payload:

```text
byte 0     mask bits: bit0=enable, bit1=session_id, bit2=tx/legacy lane_mask, bit3=rx_lane_mask, bit4=N03 mode
byte 1     enable value when mask bit0 is set, 0=disable, nonzero=enable
byte 2..3  session_id little-endian when mask bit1 is set
byte 4..7  tx/legacy lane_mask little-endian when mask bit2 is set
byte 8..11 optional rx_lane_mask little-endian when mask bit3 is set
byte 12..15 optional N03 mode little-endian when mask bit4 is set
```

The 8-byte legacy payload remains valid: when bit2 is set and bit3 is clear,
the PS side writes the same lane mask to both TX and RX. The 12-byte extended
payload allows lane partitioning, for example TX mask `0x3` and RX mask `0xc`,
which is needed for later full-duplex hardware bring-up. The PS side applies
session/lane-mask changes by briefly disabling the PL IR link, writing the
AXI-Lite config registers, then committing the requested final enable state.

For N03 network-first work, the 16-byte CONFIG form selects a bridge mode:
`network_memory_echo`, `pspl_synth_loopback`, or `ir_physical`. The first two
paths force the physical IR enable bit off while preserving session/lane
observability. `ir_physical` is intentionally rejected with
`ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE` until an explicit IR physical phase is
reopened.

The `COMMAND` frame carries an ASCII command. Current N03 commands include
`PING`, `GET_VERSION`, `GET_BUILD_ID`, `READ build_id`, `READ counters`,
`READ network_status`, `READ pspl_status`, `CONFIG payload_bytes <N>`,
`CONFIG mode network_memory_echo`, `CONFIG mode pspl_synth_loopback`,
`CLEAR counters`, `CLEAR sticky`, `START`, `STOP`, and `SHUTDOWN_SAFE`.
IR physical commands such as `CONFIG mode ir_physical`, `START ir_tx`, and
`START 2lane` return `ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE`.

STATUS_RSP payload:

```text
u32[0]  live PL status
u32[1]  sticky PL status
u32[2]  TX fragment pending bitmap
u32[3]  TX fragment in-flight bitmap
u32[4]  TX fragment ACKed bitmap
u32[5]  RX fragment received bitmap
u32[6]  PS TX success count
u32[7]  PS TX failure count
u32[8]  PS RX success count
u32[9]  PS RX bad-payload count
u32[10] TX lane mask
u32[11] RX lane mask
u32[12] packed TX lane attempt counts
u32[13] packed RX lane good-frame counts
u32[14] packed RX lane CRC-error counts
u32[15] packed RX lane overflow/overrun-error counts
```

Each packed lane-health counter uses one saturating byte per lane. This lets
the PC side see which optical route is being tried and which receive lane is
actually seeing valid or invalid traffic while the rotating correspondence
changes.

ERROR payloads
--------------

`ERROR` frames carry an ASCII reason string. Current PS-side IR/DMA reasons
include:

- `tx_invalid_payload`: PC payload is empty or larger than the current IR
  application payload limit. The default limit is 248 bytes; G1 builds using
  `IR_HW_MAX_PACKET_BYTES=264` raise it to 256 bytes.
- `tx_dma_busy_timeout`: DMA TX channel did not become idle before a send.
- `tx_dma_start_failed`: DMA rejected the TX transfer.
- `tx_dma_complete_timeout`: DMA TX transfer did not complete in time.
- `tx_retry_exhausted`: PL link exhausted IR fragment retry attempts.
- `tx_done_timeout`: PL did not report TX complete before the PS timeout.
- `rx_dma_start_failed`: RX DMA could not be armed or rearmed.
- `rx_bad_app_header`: received DMA payload did not contain the PS IR app
  header magic.
- `rx_bad_app_length`: received app payload length was invalid.

These strings are intended for PC-side logging and recovery decisions. Detailed
live/sticky PL status remains available through `STATUS_REQ`.

PC-side bring-up commands
-------------------------

From the repository root:

```powershell
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --hello --status --require-clean
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --command PING --command GET_VERSION --command GET_BUILD_ID --require-clean
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --config-session 0x1234 --config-lane-mask 0x1 --config-enable 0 --config-mode network_memory_echo --status --require-clean
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --config-mode pspl_synth_loopback --status --require-clean
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --command 'CONFIG payload_bytes 0' --expect-error ERR_BAD_ARG
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --command 'CONFIG payload_bytes too_large' --expect-error ERR_BAD_ARG
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --command 'START ir_tx' --expect-error ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --clear
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --send-text 'rf_comm_smoke' --listen
```

Continuous single-lane bring-up traffic:

```powershell
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --repeat 1000 --payload-size 32 --window 1 --ack-timeout 3 --status-interval 1 --require-clean
```

For N03 network-first payload matrices, `--payload-size` remains the RFCM
frame payload size and must stay at or below 512 bytes. Use
`--app-payload-size` for the plan-level application payload size; the host
client splits that payload into RFCM `TX_DATA` frames and verifies every echoed
fragment. For example, this sends two 8192-byte application payloads as
32 total 512-byte RFCM frames:

```powershell
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --repeat 2 --app-payload-size 8192 --payload-size 512 --min-rx-frames 32 --require-clean
```

Fixed-duration soak entry for later stability testing:

```powershell
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --duration 600 --payload-size 32 --window 1 --ack-timeout 3 --interval 0.01 --status-interval 5 --csv-log '.\software\host_client\logs\soak_2h.csv' --quiet --require-clean
```

The repeat/soak command prints a final summary with transmitted payload bytes,
ACK count, error count, pending frames, measured TCP/IR command RTT, and
application payload throughput. The CSV log records every received ACK, ERROR,
STATUS_RSP, and RX_DATA frame for later review. It also records final
`SENT_SUMMARY`, `SUMMARY`, and `ACCEPTANCE_PASS` or `ACCEPTANCE_FAIL` marker
rows so long runs can be audited without preserving the terminal scrollback.
Segmented N03 runs additionally record `app_payload_size`,
`fragment_frames`, `app_tx_packets`, `app_tx_bytes`, and `app_tx_fragments` so
large application payloads can be audited separately from the RFCM frame limit.
The historical `soak_2h` name is retained only for compatibility with earlier
scripts; the wrapper caps physical runs at 600 seconds and analyzes against a
600-second minimum.

For repeatable board-level evidence, use the wrapper:

```powershell
.\software\host_client\run_acceptance.ps1 -Mode smoke -TargetHost 192.168.10.2
.\software\host_client\run_acceptance.ps1 -Mode n03_commands -TargetHost 192.168.10.2
.\software\host_client\run_acceptance.ps1 -Mode n03_memory_echo -TargetHost 192.168.10.2
.\software\host_client\run_acceptance.ps1 -Mode n03_pspl_synth -TargetHost 192.168.10.2
.\software\host_client\run_acceptance.ps1 -Mode n03_negative -TargetHost 192.168.10.2
.\software\host_client\run_acceptance.ps1 -Mode reconnect -TargetHost 192.168.10.2
```

For a large N03 application payload smoke through the wrapper:

```powershell
.\software\host_client\run_acceptance.ps1 -Mode n03_memory_echo -TargetHost 192.168.10.2 -Repeat 2 -PayloadSize 512 -AppPayloadSize 8192 -MinRxFrames 32
```

Add `-MinTxMbps`, `-MinRxMbps`, or `-MinRxFrames` when a run should fail
automatically unless the measured throughput or receive evidence reaches the
requested threshold. Traffic modes automatically run the CSV analyzer after the
host client exits, so a run can fail either during live acceptance or during
second-pass log analysis. Add `-DryRun` to print commands without connecting,
or `-SkipLogAnalysis` to defer the second-pass log check.

Analyze a completed CSV log:

```powershell
python '.\software\host_client\analyze_acceptance_log.py' '.\software\host_client\logs\soak_2h.csv' --require-pass --min-duration 600 --max-errors 0 --min-status-frames 1
```

TCP reconnect smoke test:

```powershell
python '.\software\host_client\rf_comm_client.py' --host 192.168.10.2 --reconnect-cycles 20 --reconnect-payload-size 64
```

When `--reconnect-payload-size` is nonzero, every reconnect cycle must complete
HELLO, STATUS, one TX_DATA ACK, and one RX_DATA payload echo with
`payload_mismatch=0`. The wrapper's `reconnect` mode enables this by default so
N03-9 covers "reconnect, then continue STATUS / payload echo" rather than only
opening TCP sessions.

Offline PC protocol regression:

```powershell
python -m unittest '.\software\host_client\test_rf_comm_client.py' -v
```

The offline regression uses a localhost mock RFCM server to exercise normal
HELLO/STATUS/TX/RX flow, extended STATUS lane-health counters, CONFIG updates,
TX error reporting, fragmented TCP frame receive, coalesced TCP frame receive,
missing-ACK timeout accounting, oversize payload rejection, independent TX/RX
lane-mask configuration, and repeated reconnect cycles.

The board-level acceptance wrapper also has an offline mode:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File '.\software\host_client\run_acceptance.ps1' -Mode offline_mock
```

That mode starts the standalone `mock_rfcm_server.py` on an automatically
selected localhost TCP port, runs the same PC-side command path used for
hardware smoke tests, writes a CSV log, analyzes the log, and performs reconnect
checks. It also covers the N03 memory echo, PS/PL synthetic loopback, and
IR-deferred negative command paths. It is a tooling/protocol regression only;
real DHCP/static fallback, TCP port 5001 on the Zynq PS, DMA, PL, and
optical-link behavior still require a board run.

Offline PS bridge source checks:

```powershell
python '.\software\ps_lwip_bridge\check_ps_bridge_static.py'
```

This source-level check is part of the simulation-only gate. It verifies that
DHCP with static fallback, TCP port 5001 listen/accept/close handling, partial
TCP frame parsing, PS-to-PC protocol constants, CONFIG lane masks, and reconnect
state cleanup remain present in the bridge source. It is not a substitute for a
board-level TCP/DHCP run.
