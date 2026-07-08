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
M4_AXI_REGS_TB_CREATED=1
M4_AXI_REGS_SIM=PENDING_TOOL
M4_PS_DRIVER_C_COMPILE=PENDING_TOOL
NO_HARDWARE_ACTIONS_EXECUTED=1

`scripts/check_m4_static.py` verifies that every register in
`config/register_map/ir_axi_regs.yaml` appears in the generated C/Python/Markdown
outputs and in `rtl/ir_axi_regs_new.sv`. It also runs a Python reference
write/readback/commit/profile-id model and checks the PS driver uses readback
verification plus commit. SystemVerilog and C compilation remain unclaimed
because no supported SV simulator or C compiler is available on PATH.
