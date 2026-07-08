param(
    [string]$Status = "SIM_OFFLINE_CAPPED_10MIN_SOAK_PASS"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$reports = Join-Path $repoRoot "reports"
$out = Join-Path $reports "G1_artifacts_hashes.txt"

function Add-Section {
    param([System.Collections.Generic.List[string]]$Lines, [string]$Title)
    $Lines.Add("")
    $Lines.Add($Title)
}

function Add-Hash {
    param([System.Collections.Generic.List[string]]$Lines, [string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        $Lines.Add($Path)
        $Lines.Add("SHA256 MISSING")
        $Lines.Add("")
        return
    }
    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolved).Hash
    $Lines.Add($resolved)
    $Lines.Add("SHA256 $hash")
    $Lines.Add("")
}

function Get-LatestPath {
    param([string]$Pattern)
    $match = Get-ChildItem -LiteralPath $reports -File -Filter $Pattern -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($match) {
        return $match.FullName
    }
    return ""
}

$expectedConstraintSha256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
$constraint = Get-ChildItem -LiteralPath $repoRoot -File -Filter "*.txt" |
    Where-Object {
        try {
            (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash -eq $expectedConstraintSha256
        } catch {
            $false
        }
    } |
    Select-Object -First 1

$files = [ordered]@{
    "Hard constraint:" = @(
        $(if ($constraint) { $constraint.FullName } else { Join-Path $repoRoot "HARD_CONSTRAINT_NOT_FOUND.txt" })
    )
    "Stage target:" = @(
        "C:\Users\user\Downloads\G0_G1_targets.md"
    )
    "Generated G1 report artifacts:" = @(
        (Join-Path $reports "G1_acceptance_report.md"),
        (Join-Path $reports "G1_uart.log"),
        (Join-Path $reports "G1_pc_client.log"),
        (Join-Path $reports "G1_throughput.csv"),
        (Join-Path $reports "G1_error_counters.csv"),
        (Join-Path $reports "G1_test_config.json"),
        (Join-Path $reports "G1_hw_smoke_analysis_20260626.md"),
        (Join-Path $reports "g0_g1_target_audit_current_20260626.md"),
        (Join-Path $reports "g0_g1_target_audit_current_20260626.json")
    )
    "Latest short-pass build and hardware smoke evidence:" = @(
        (Join-Path $reports "g1_lane0_smoke_build_validated_20260626_212420.summary.txt"),
        (Join-Path $reports "g1_lane0_smoke_build_20260626_211700_792_15836.summary.txt"),
        (Join-Path $reports "g0_lane0_build_20260626_211701_216_42492.summary.txt"),
        (Join-Path $reports "g0_lane0_build_20260626_211701_216_42492.configure.log"),
        (Join-Path $reports "g1_lane0_hw_smoke_safe_20260626_212425.summary.txt"),
        (Join-Path $reports "uart_lane0_hw_loopback_safe_20260626_212425.log"),
        (Join-Path $reports "program_tfdu_shutdown_after_lane0_loopback_20260626_212425.out.log")
    )
    "Capped 10-minute soak evidence:" = @(
        (Join-Path $reports "g1_lane0_smoke_build_validated_20260626_220513.summary.txt"),
        (Join-Path $reports "g1_lane0_smoke_build_20260626_215731_575_14752.summary.txt"),
        (Join-Path $reports "g0_lane0_build_20260626_215731_996_6268.summary.txt"),
        (Join-Path $reports "g1_lane0_hw_smoke_safe_20260626_220812.summary.txt"),
        (Join-Path $reports "uart_lane0_hw_loopback_safe_20260626_220813.log"),
        (Join-Path $reports "program_tfdu_shutdown_after_lane0_loopback_20260626_220813.out.log")
    )
    "Segmented regression wrapper evidence:" = @(
        (Get-LatestPath "g1_segmented_smoke_regression_*.summary.txt"),
        (Get-LatestPath "g1_segmented_smoke_regression_*.cycles.csv")
    )
    "Previous post-fix build and hardware smoke evidence:" = @(
        (Join-Path $reports "g1_lane0_smoke_build_validated_20260626_163849.summary.txt"),
        (Join-Path $reports "g1_lane0_smoke_build_20260626_163137_760_32492.summary.txt"),
        (Join-Path $reports "g0_lane0_build_20260626_163138_132_41372.summary.txt"),
        (Join-Path $reports "g0_lane0_build_20260626_163138_132_41372.configure.log"),
        (Join-Path $reports "g1_lane0_hw_smoke_safe_20260626_163900.summary.txt"),
        (Join-Path $reports "uart_lane0_hw_loopback_safe_20260626_163900.log"),
        (Join-Path $reports "program_tfdu_shutdown_after_lane0_loopback_20260626_163900.out.log")
    )
    "Post-fix simulation evidence:" = @(
        (Join-Path $reports "g1_hw_smoke_default_fixed_20260626.log"),
        (Join-Path $reports "simulation_gates_after_g1_rx_fix_20260626.log"),
        (Join-Path $reports "g1_hw_smoke_matrix_default_direct.log"),
        (Join-Path $reports "g1_hw_smoke_matrix_realign_off_direct.log"),
        (Join-Path $reports "g1_hw_smoke_matrix_default_window_realign_off_direct.log"),
        (Join-Path $reports "g1_hw_smoke_matrix_default_window_realign_off_edge.log"),
        (Join-Path $reports "g1_hw_smoke_matrix_default_window_realign_on_direct.log"),
        (Join-Path $reports "g1_hw_smoke_matrix_default_window_realign_on_edge.log")
    )
    "Previous simulation and PC/offline gates:" = @(
        (Join-Path $reports "g1_sim_gate_20260626_153050.log"),
        (Join-Path $reports "ps_pc_offline_gates_20260626_154209.summary.txt"),
        (Join-Path $reports "ps_pc_offline_acceptance_20260626_154209\offline_mock_single_lane_20260626_154212.csv")
    )
    "Previous failed G1 hardware smoke evidence before RX-fix retest:" = @(
        (Join-Path $reports "g1_lane0_hw_smoke_safe_20260626_155612.summary.txt"),
        (Join-Path $reports "uart_lane0_hw_loopback_safe_20260626_155612.log"),
        (Join-Path $reports "program_tfdu_shutdown_after_lane0_loopback_20260626_155612.out.log"),
        (Join-Path $reports "g1_lane0_smoke_build_validated_20260626_155538.summary.txt")
    )
    "Current generated hardware/software artifacts:" = @(
        (Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"),
        (Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.ltx"),
        (Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.xsa"),
        (Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf")
    )
    "Relevant scripts and implementation files:" = @(
        (Join-Path $repoRoot "IPs\ip_ir_array\run_loopback_single_lane.ps1"),
        (Join-Path $repoRoot "IPs\ip_ir_array\sim\tb_ir_stream_bidir_b0_g1_hw_smoke.sv"),
        (Join-Path $repoRoot "tools\build_g0_lane0_artifacts.ps1"),
        (Join-Path $repoRoot "tools\build_g1_lane0_smoke_artifacts.ps1"),
        (Join-Path $repoRoot "tools\validate_g1_lane0_smoke_build.ps1"),
        (Join-Path $repoRoot "tools\run_g1_segmented_smoke_regression_safe.ps1"),
        (Join-Path $repoRoot "tools\audit_g0_g1_targets.py"),
        (Join-Path $repoRoot "tools\update_g1_artifact_hashes.ps1"),
        (Join-Path $repoRoot "tools\configure_lane0_ab_hw_loopback.tcl"),
        (Join-Path $repoRoot "software\ps_ps_loopback\src\main.c"),
        (Join-Path $repoRoot "software\ps_lwip_bridge\src\ir_hw.c"),
        (Join-Path $repoRoot "software\ps_lwip_bridge\src\ir_hw.h")
    )
    "Safety artifact:" = @(
        (Join-Path $repoRoot "shutdown_bitstream\tfdu_shutdown_j10_j11.bit")
    )
}

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("G1 artifact hashes captured $(Get-Date -Format o)")
$lines.Add("")
$lines.Add("Current G1 status:")
$lines.Add($Status)

foreach ($section in $files.GetEnumerator()) {
    Add-Section -Lines $lines -Title $section.Key
    foreach ($path in $section.Value) {
        Add-Hash -Lines $lines -Path $path
    }
}

Set-Content -LiteralPath $out -Value $lines -Encoding UTF8
Write-Output "WROTE_G1_ARTIFACT_HASHES=$out"
