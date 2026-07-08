# M4 AXI Register Contract Status

M4_AXI_REGS_RTL_IMPLEMENTED=1
M4_REGISTER_MAP_SINGLE_SOURCE_VERIFIED=1
M4_GENERATED_C_HEADER_VERIFIED=1
M4_GENERATED_PYTHON_OFFSETS_VERIFIED=1
M4_REGISTER_CONTRACT_DOC_VERIFIED=1
M4_PROFILE_WRITE_READBACK_REFERENCE=PASS
M4_PROFILE_COMMIT_REFERENCE=PASS
M4_PROFILE_ID_REFERENCE=PASS
M4_PS_DRIVER_OFFLINE_CONTRACT=PASS
M4_PS_DRIVER_STARTUP_WAIT=PASS
M4_PS_DRIVER_TRANSACTION_POLL=PASS
M4_PS_DRIVER_FINAL_COUNTER_READBACK=PASS
M4_PS_DRIVER_MMIO_TRACE=PASS
M4_AXI_REGS_TB_CREATED=1
M4_AXI_REGS_SIM=PENDING_TOOL
M4_PS_DRIVER_C_COMPILE=PENDING_TOOL
M4_PS_DRIVER_C_COMPILE_GATE_CREATED=1
NO_HARDWARE_ACTIONS_EXECUTED=1

`scripts/check_m4_static.py` verifies that every register in
`config/register_map/ir_axi_regs.yaml` appears in the generated C/Python/Markdown
outputs and in `rtl/ir_axi_regs_new.sv`. It also runs a Python reference
write/readback/commit/profile-id model and checks the PS driver uses readback
verification plus commit. The MMIO trace report at
`evidence/generated/m4_ps_driver_trace.md` validates the offline
reset/profile/readback/commit/enable/startup/start/poll/stop/counter/shutdown
sequence without needing a C compiler. `scripts/run_offline_gates.py` also tries
to compile and run the PS driver offline stub when `gcc` or `clang` is
available. SystemVerilog and C compilation remain unclaimed when no supported
simulator or C compiler is available on PATH.
