param(
    [string]$VivadoBin = "D:\Xilinx\Vivado\2023.1\bin",
    [int]$Jobs = 16,
    [ValidateSet("phy_rate", "payload_budget", "loopback", "impair", "crc", "exhaust", "recover_after_exhaust", "burst", "bidir", "fdx", "fdx_1lane", "fdx_4plus4", "long_packet", "multi", "multi_8lane", "max_fragment_8lane", "multi_impair", "degrade", "route", "autoroute", "autoroute_8lane", "rotating_autoroute", "rotating_soak_model", "rotating_8lane_soak_model", "defensive", "regs", "axi_counters", "axi_rx_microscope", "b0_echo", "sink_speed", "txonly_speed", "rx_hw_ack_wave", "ila_replay", "ila_replay_sweep", "stream_ack_ila_replay", "stream_bidir", "stream_tdm_perf", "stream_bidir_b0", "stream_bidir_b0_g1_hw_smoke", "stream_bidir_b0_2lane_perf", "stream_parallel_asym_2lane_perf", "stream_parallel_top_asym_2lane_perf", "stream_2lane", "stream_2lane_slow", "stream_4lane", "stream_ack_loss", "stream_ack_mask_zero", "stream_axi_bidir", "all")]
    [string]$Test = "loopback",
    [string[]]$GenericTop = @(),
    [string[]]$Define = @(),
    [string[]]$PlusArg = @()
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ($env:IR_SIM_DEFINES) {
    $Define += ($env:IR_SIM_DEFINES -split '[,; ]+' | Where-Object { $_ -ne "" })
}

if ($Test -eq "all") {
    foreach ($case in @("phy_rate", "payload_budget", "loopback", "impair", "crc", "exhaust", "recover_after_exhaust", "burst", "bidir", "fdx", "fdx_1lane", "fdx_4plus4", "long_packet", "multi", "multi_8lane", "max_fragment_8lane", "multi_impair", "degrade", "route", "autoroute", "autoroute_8lane", "rotating_autoroute", "rotating_soak_model", "rotating_8lane_soak_model", "defensive", "regs", "axi_counters", "axi_rx_microscope", "b0_echo", "sink_speed", "txonly_speed", "stream_bidir", "stream_tdm_perf", "stream_bidir_b0", "stream_bidir_b0_g1_hw_smoke", "stream_bidir_b0_2lane_perf", "stream_parallel_asym_2lane_perf", "stream_parallel_top_asym_2lane_perf", "stream_2lane", "stream_2lane_slow", "stream_4lane", "stream_ack_loss", "stream_ack_mask_zero", "stream_axi_bidir")) {
        Write-Host "=== Running $case ==="
        & $PSCommandPath -VivadoBin $VivadoBin -Jobs $Jobs -Test $case
    }
    Write-Host "ALL_IR_ARRAY_TESTS_PASS"
    return
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Args
    )

    & $Exe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $Exe $($Args -join ' ')"
    }
}

function To-XilinxPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Resolve-Path -LiteralPath $Path).Path.Replace('\', '/')
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$srcDir = Join-Path $scriptDir "src"
$simDir = Join-Path $scriptDir "sim"
switch ($Test) {
    "phy_rate" {
        $tbModule = "tb_ir_phy_rate_model"
        $passPattern = "IR_PHY_RATE_MODEL_PASS"
        $laneSuffix = "single_lane"
    }
    "payload_budget" {
        $tbModule = "tb_ir_payload_throughput_budget"
        $passPattern = "IR_PAYLOAD_THROUGHPUT_BUDGET_PASS"
        $laneSuffix = "model"
    }
    "impair" {
        $tbModule = "tb_ir_array_loopback_impair_single_lane"
        $passPattern = "LOOPBACK_IMPAIR_SINGLE_LANE_PASS"
    }
    "crc" {
        $tbModule = "tb_ir_array_loopback_crc_single_lane"
        $passPattern = "LOOPBACK_CRC_SINGLE_LANE_PASS"
    }
    "exhaust" {
        $tbModule = "tb_ir_array_loopback_retry_exhaust_single_lane"
        $passPattern = "LOOPBACK_RETRY_EXHAUST_SINGLE_LANE_PASS"
        $laneSuffix = "single_lane"
    }
    "recover_after_exhaust" {
        $tbModule = "tb_ir_array_loopback_recover_after_exhaust_single_lane"
        $passPattern = "LOOPBACK_RECOVER_AFTER_EXHAUST_SINGLE_LANE_PASS"
        $laneSuffix = "single_lane"
    }
    "burst" {
        $tbModule = "tb_ir_array_loopback_burst_single_lane"
        $passPattern = "LOOPBACK_BURST_SINGLE_LANE_PASS"
        $laneSuffix = "single_lane"
    }
    "bidir" {
        $tbModule = "tb_ir_array_loopback_bidirectional_single_lane"
        $passPattern = "LOOPBACK_BIDIR_SINGLE_LANE_PASS"
        $laneSuffix = "single_lane"
    }
    "fdx" {
        $tbModule = "tb_ir_array_loopback_full_duplex_lane_partition"
        $passPattern = "LOOPBACK_FULL_DUPLEX_LANE_PARTITION_PASS"
        $laneSuffix = "lane_partition"
    }
    "fdx_1lane" {
        $tbModule = "tb_ir_array_loopback_full_duplex_lane_partition"
        $passPattern = "LOOPBACK_FULL_DUPLEX_1PLUS1_LANE_PASS"
        $laneSuffix = "1plus1_lane"
        $Define += "TB_FDX_1PLUS1"
    }
    "fdx_4plus4" {
        $tbModule = "tb_ir_array_loopback_full_duplex_lane_partition"
        $passPattern = "LOOPBACK_FULL_DUPLEX_4PLUS4_LANE_PASS"
        $laneSuffix = "4plus4_lane"
        $Define += "TB_FDX_4PLUS4"
    }
    "long_packet" {
        $tbModule = "tb_ir_array_loopback_long_packet_latency"
        $passPattern = "LOOPBACK_SINGLE_LANE_256B_LATENCY_PASS"
        $laneSuffix = "single_lane"
    }
    "regs" {
        $tbModule = "tb_ir_axi_regs_config_masks"
        $passPattern = "AXI_REGS_CONFIG_MASKS_PASS"
        $laneSuffix = "axi_regs"
    }
    "axi_counters" {
        $tbModule = "tb_ir_array_top_axi_lane_counters"
        $passPattern = "AXI_TOP_LANE_COUNTERS_PASS"
        $laneSuffix = "axi_top"
    }
    "axi_rx_microscope" {
        $tbModule = "tb_ir_array_top_axi_rx_microscope"
        $passPattern = "AXI_RX_MICROSCOPE_SESSION_MISMATCH_PASS"
        $laneSuffix = "axi_top"
    }
    "b0_echo" {
        $tbModule = "tb_ir_loopback_b0_echo_twofrag"
        $passPattern = "LOOPBACK_B0_ECHO_TWOFRAG_PASS"
        $laneSuffix = "single_lane"
    }
    "sink_speed" {
        $tbModule = "tb_ir_sink_b0_halfduplex_speed"
        $passPattern = "IR_SINK_B0_HALFDUPLEX_SPEED_PASS"
        $laneSuffix = "single_lane"
    }
    "txonly_speed" {
        $tbModule = "tb_ir_txonly_ack_axi_speed"
        $passPattern = "IR_TXONLY_ACK_AXI_SPEED_PASS"
        $laneSuffix = "single_lane"
    }
    "rx_hw_ack_wave" {
        $tbModule = "tb_ir_rx_hw_ack_wave"
        $passPattern = "IR_RX_HW_ACK_WAVE_PASS"
        $laneSuffix = "single_lane"
    }
    "ila_replay" {
        $tbModule = "tb_ir_rx_ila_replay"
        $passPattern = "ILA_REPLAY_SUMMARY"
        $laneSuffix = "diagnostic"
    }
    "ila_replay_sweep" {
        $tbModule = "tb_ir_rx_ila_replay_sweep"
        $passPattern = "ILA_REPLAY_SWEEP_BEST"
        $laneSuffix = "diagnostic"
    }
    "stream_ack_ila_replay" {
        $tbModule = "tb_ir_stream_ack_ila_replay"
        $passPattern = "IR_STREAM_ACK_ILA_TOPLEVEL_SUMMARY"
        $laneSuffix = "diagnostic"
    }
    "stream_bidir" {
        $tbModule = "tb_ir_stream_bidir_single_lane"
        $passPattern = "IR_STREAM_BIDIR_SINGLE_LANE_PASS"
        $laneSuffix = "single_lane"
    }
    "stream_tdm_perf" {
        $tbModule = "tb_ir_stream_tdm_perf_single_lane"
        $passPattern = "IR_STREAM_TDM_PERF_SINGLE_LANE_PASS"
        $laneSuffix = "single_lane"
    }
    "stream_bidir_b0" {
        $tbModule = "tb_ir_stream_bidir_b0_bd"
        $passPattern = "IR_STREAM_BIDIR_B0_BD_PASS"
        $laneSuffix = "single_lane"
    }
    "stream_bidir_b0_g1_hw_smoke" {
        $tbModule = "tb_ir_stream_bidir_b0_g1_hw_smoke"
        $passPattern = "IR_STREAM_BIDIR_B0_G1_HW_SMOKE_PASS"
        $laneSuffix = "g1_hw_smoke"
    }
    "stream_bidir_b0_2lane_perf" {
        $tbModule = "tb_ir_stream_bidir_b0_2lane_perf"
        $passPattern = "IR_STREAM_BIDIR_B0_2LANE_PERF_PASS"
        $laneSuffix = "fixed_2lane"
    }
    "stream_parallel_asym_2lane_perf" {
        $tbModule = "tb_ir_stream_parallel_asym_2lane_perf"
        $passPattern = "IR_STREAM_PARALLEL_ASYM_2LANE_PERF_PASS"
        $laneSuffix = "fixed_2lane"
    }
    "stream_parallel_top_asym_2lane_perf" {
        # Legacy case name retained for old reports. The original top-specific
        # bench targeted ir_stream_parallel_2lane_top, which is now a role-based
        # A-data/B-ACK block. Use the maintained asymmetric 2-lane performance
        # bench for the same throughput/half-duplex TDM acceptance objective.
        $tbModule = "tb_ir_stream_parallel_asym_2lane_perf"
        $passPattern = "IR_STREAM_PARALLEL_ASYM_2LANE_PERF_PASS"
        $laneSuffix = "fixed_2lane"
    }
    "stream_2lane" {
        $tbModule = "tb_ir_stream_fixed_2lane"
        $passPattern = "IR_STREAM_FIXED_2LANE_PASS"
        $laneSuffix = "fixed_2lane"
    }
    "stream_2lane_slow" {
        $tbModule = "tb_ir_stream_fixed_2lane"
        $passPattern = "IR_STREAM_FIXED_2LANE_PASS"
        $laneSuffix = "fixed_2lane_slow"
    }
    "stream_4lane" {
        $tbModule = "tb_ir_stream_fixed_4lane"
        $passPattern = "IR_STREAM_FIXED_4LANE_PASS"
        $laneSuffix = "fixed_4lane"
    }
    "stream_ack_loss" {
        $tbModule = "tb_ir_stream_ack_loss_recovery"
        $passPattern = "IR_STREAM_ACK_LOSS_RECOVERY_PASS"
        $laneSuffix = "single_lane"
    }
    "stream_ack_mask_zero" {
        $tbModule = "tb_ir_stream_ack_mask_zero"
        $passPattern = "IR_STREAM_ACK_MASK_ZERO_PASS"
        $laneSuffix = "single_lane"
    }
    "stream_axi_bidir" {
        $tbModule = "tb_ir_stream_axi_bidir_single_lane"
        $passPattern = "IR_STREAM_AXI_BIDIR_SINGLE_LANE_PASS"
        $laneSuffix = "single_lane"
    }
    "multi" {
        $tbModule = "tb_ir_array_loopback_multi_lane"
        $passPattern = "LOOPBACK_MULTI_LANE_PASS"
        $laneSuffix = "multi_lane"
    }
    "multi_8lane" {
        $tbModule = "tb_ir_array_loopback_8lane"
        $passPattern = "LOOPBACK_8LANE_PASS"
        $laneSuffix = "multi_lane"
    }
    "max_fragment_8lane" {
        $tbModule = "tb_ir_array_loopback_8lane_max_fragment"
        $passPattern = "LOOPBACK_8LANE_MAX_FRAGMENT_PASS"
        $laneSuffix = "multi_lane"
    }
    "multi_impair" {
        $tbModule = "tb_ir_array_loopback_multi_lane_impair"
        $passPattern = "LOOPBACK_MULTI_LANE_IMPAIR_PASS"
        $laneSuffix = "multi_lane"
    }
    "degrade" {
        $tbModule = "tb_ir_array_loopback_multi_lane_degrade"
        $passPattern = "LOOPBACK_MULTI_LANE_DEGRADE_PASS"
        $laneSuffix = "multi_lane"
    }
    "route" {
        $tbModule = "tb_ir_array_loopback_multi_lane_route"
        $passPattern = "LOOPBACK_MULTI_LANE_ROUTE_PASS"
        $laneSuffix = "multi_lane"
    }
    "autoroute" {
        $tbModule = "tb_ir_array_loopback_multi_lane_autoroute"
        $passPattern = "LOOPBACK_MULTI_LANE_AUTOROUTE_PASS"
        $laneSuffix = "multi_lane"
    }
    "autoroute_8lane" {
        $tbModule = "tb_ir_array_loopback_8lane_autoroute"
        $passPattern = "LOOPBACK_8LANE_AUTOROUTE_PASS"
        $laneSuffix = "multi_lane"
    }
    "rotating_autoroute" {
        $tbModule = "tb_ir_array_loopback_rotating_autoroute_stress"
        $passPattern = "LOOPBACK_ROTATING_AUTOROUTE_STRESS_PASS"
        $laneSuffix = "multi_lane"
    }
    "rotating_soak_model" {
        $tbModule = "tb_ir_rotating_autoroute_soak_model"
        $passPattern = "ROTATING_AUTOROUTE_2H_SOAK_MODEL_PASS"
        $laneSuffix = "model"
    }
    "rotating_8lane_soak_model" {
        $tbModule = "tb_ir_rotating_autoroute_8lane_soak_model"
        $passPattern = "ROTATING_AUTOROUTE_8LANE_CAPPED_SOAK_MODEL_PASS"
        $laneSuffix = "model"
    }
    "defensive" {
        $tbModule = "tb_ir_protocol_defensive_cases"
        $passPattern = "IR_PROTOCOL_DEFENSIVE_CASES_PASS"
        $laneSuffix = "protocol"
    }
    default {
        $tbModule = "tb_ir_array_loopback_single_lane"
        $passPattern = "LOOPBACK_SINGLE_LANE_PASS"
        $laneSuffix = "single_lane"
    }
}
if ($Test -eq "impair" -or $Test -eq "crc") {
    $laneSuffix = "single_lane"
}
$workDir = Join-Path $repoRoot "sim_work\$Test`_$laneSuffix\$Test`_$laneSuffix.sim\sim_1\behav\xsim"
New-Item -ItemType Directory -Force -Path $workDir | Out-Null

$plusEntries = @()
foreach ($plusGroup in $PlusArg) {
    foreach ($plusRaw in ($plusGroup -split ',')) {
        $plus = $plusRaw.Trim()
        if ($plus -ne "") {
            if ($plus.StartsWith("+")) {
                $plus = $plus.Substring(1)
            }
            $plusEntries += $plus
        }
    }
}
$plusConfig = Join-Path $workDir "xsim_plusargs.cfg"
if ($plusEntries.Count -gt 0) {
    $utf8NoBomForPlus = New-Object System.Text.UTF8Encoding -ArgumentList $false
    [System.IO.File]::WriteAllLines($plusConfig, [string[]]$plusEntries, $utf8NoBomForPlus)
} elseif (Test-Path -LiteralPath $plusConfig) {
    Remove-Item -LiteralPath $plusConfig -Force
}

$vivadoRoot = Split-Path -Parent $VivadoBin
$xvlog = Join-Path $VivadoBin "xvlog.bat"
$xelab = Join-Path $VivadoBin "xelab.bat"
$xsim = Join-Path $VivadoBin "xsim.bat"
$glbl = Join-Path $vivadoRoot "data\verilog\src\glbl.v"

foreach ($tool in @($xvlog, $xelab, $xsim)) {
    if (-not (Test-Path -LiteralPath $tool)) {
        throw "Missing Vivado tool: $tool"
    }
}

$svSources = @(
    "ir_protocol_pkg.sv",
    "crc32_gen.sv",
    "cdc_sync.sv",
    "ir_axis_async_fifo.sv",
    "ir_array_rx_mgr.sv",
    "ir_array_top.sv",
    "ir_array_top_axi.sv",
    "ir_stream_array_top.sv",
    "ir_stream_array_top_axi.sv",
    "ir_txonly_ack_axi.sv",
    "ir_stream_parallel_2lane_top.sv",
    "ir_stream_bidir_b0_bd.sv",
    "ir_stream_bidir_b0_bd.v",
    "ir_stream_bidir_vec_bd.v",
    "ir_fdx_partition_b_bd.sv",
    "ir_fdx_partition_b_bd.v",
    "ir_array_tx_mgr.sv",
    "ir_axi_regs.sv",
    "ir_comm_lane.sv",
    "ir_lane_frame_sink.sv",
    "ir_lane_frame_source.sv",
    "ir_rx_4ppm_frame.sv",
    "ir_tx_4ppm_frame.sv"
) | ForEach-Object { Join-Path $srcDir $_ }
if ($Test -eq "b0_echo") {
    $svSources += Join-Path $srcDir "ir_loopback_b0_bd.v"
    $svSources += Join-Path $srcDir "ir_loopback_b0_completeack_bd.v"
}
if ($Test -eq "sink_speed" -or $Test -eq "txonly_speed") {
    $svSources += Join-Path $srcDir "ir_sink_b0_bd.v"
}
$svSources += Join-Path $simDir "$tbModule.sv"

foreach ($source in $svSources) {
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Missing simulation source: $source"
    }
}

$prj = Join-Path $workDir "$($tbModule)_vlog.prj"
$lines = @()
foreach ($source in $svSources) {
    $lines += 'sv xil_defaultlib "' + (To-XilinxPath $source) + '"'
}

if (Test-Path -LiteralPath $glbl) {
    $lines += 'verilog xil_defaultlib "' + (To-XilinxPath $glbl) + '"'
}

$lines += "NOSORT"
$utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList $false
[System.IO.File]::WriteAllLines($prj, [string[]]$lines, $utf8NoBom)

Push-Location $workDir
try {
    $xvlogArgs = @("--incr", "--relax", "-L", "uvm")
    foreach ($define in $Define) {
        if ($define -ne "") {
            $xvlogArgs += @("-d", $define)
        }
    }
    $xvlogArgs += @("-prj", $prj, "-log", "xvlog.log")
    Invoke-Checked $xvlog $xvlogArgs

    $topUnits = @("xil_defaultlib.$tbModule")
    if (Test-Path -LiteralPath $glbl) {
        $topUnits += "xil_defaultlib.glbl"
    }

    $xelabArgs = @(
        "--incr",
        "--debug", "typical",
        "--relax",
        "--mt", "$Jobs",
        "-L", "xil_defaultlib",
        "-L", "unisims_ver",
        "-L", "unimacro_ver",
        "-L", "xpm",
        "-L", "secureip",
        "--snapshot", "$($tbModule)_behav"
    )
    $xelabArgs += $topUnits
    foreach ($generic in $GenericTop) {
        if ($generic -ne "") {
            $xelabArgs += @("--generic_top", $generic)
        }
    }
    $xelabArgs += @("-log", "elaborate.log")
    Invoke-Checked $xelab $xelabArgs

    $xsimArgs = @("$($tbModule)_behav", "--runall", "--log", "simulate.log")
    Invoke-Checked $xsim $xsimArgs

    $simLog = Get-Content -LiteralPath "simulate.log" -Raw
    if ($simLog -notmatch $passPattern) {
        throw "Simulation finished without $passPattern. See $workDir\simulate.log"
    }

    Write-Host $passPattern
    Write-Host "Log: $workDir\simulate.log"
} finally {
    Pop-Location
}
