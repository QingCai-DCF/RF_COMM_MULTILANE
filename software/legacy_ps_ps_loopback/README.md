PS-PS IR loopback experiment
============================

Purpose
-------

This standalone Zynq PS application is for board bring-up before connecting the
PC upper-computer side. It generates deterministic payloads in PS, sends them
through the existing PL IR AXI/DMA path, waits for the payload to loop back to
PS, and prints live UART statistics.

The test automatically alternates between:

- `lane_mask=0x00000001` for single-lane bring-up.
- `lane_mask=0x00000003` for two-lane bring-up.

UART statistics include packet attempts, verified loopback packets, packet loss
rate, verified payload throughput in Mbit/s, TX/RX failure counts, sticky PL
status, and packed lane-health counters.

Important hardware note
-----------------------

This program can configure one-lane and two-lane masks, but the two-lane stage
requires the programmed bitstream to instantiate and route at least two IR lanes.
If the current PL image only has one lane or lane 1 is not optically looped
back, the two-lane stage should report TX/RX failures or lane counters that do
not advance on lane 1. That is useful bring-up evidence, not a PC-side issue.

Build
-----

From the repository root:

```powershell
& 'D:\Xilinx\Vitis\2023.1\bin\xsct.bat' '.\software\ps_ps_loopback\build_vitis.tcl'
```

The ELF is generated at:

```text
software/_vitis_ws_ps_ps_loopback/rf_comm_ps_ps_loopback/Debug/rf_comm_ps_ps_loopback.elf
```

JTAG run
--------

With the board connected through JTAG:

```powershell
& 'D:\Xilinx\Vitis\2023.1\bin\xsct.bat' '.\software\ps_ps_loopback\run_on_hw.tcl'
```

The script programs the existing bitstream and starts the loopback ELF. Watch
the UART; no Ethernet or PC host client is used.

SD-card BOOT.BIN
----------------

Generate a bootable image:

```powershell
.\software\ps_ps_loopback\build_boot_image.ps1 -RebuildVitis -Force
```

The directly bootable output is:

```text
software/_boot_ps_ps_loopback/BOOT.BIN
```

Copy that file to the SD card FAT partition, set the board boot mode to SD, and
power-cycle the board. The application starts automatically and prints UART
statistics.

