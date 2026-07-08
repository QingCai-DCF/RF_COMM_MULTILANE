param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$DebugStageSeconds = 24,
    [int]$PostStartSeconds = 55,
    [int]$CaptureSeconds = 100
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "p2_lane0_health_debug_safe_$stamp.summary.txt"
$debugBuildOut = Join-Path $reportsDir "p2_lane0_health_debug_build_$stamp.out.log"
$debugBuildErr = Join-Path $reportsDir "p2_lane0_health_debug_build_$stamp.err.log"
$runOut = Join-Path $reportsDir "p2_lane0_health_debug_run_$stamp.out.log"
$runErr = Join-Path $reportsDir "p2_lane0_health_debug_run_$stamp.err.log"
$restoreBuildOut = Join-Path $reportsDir "p2_lane0_health_debug_restore_p2_build_$stamp.out.log"
$restoreBuildErr = Join-Path $reportsDir "p2_lane0_health_debug_restore_p2_build_$stamp.err.log"
$artifactOut = Join-Path $reportsDir "p2_lane0_health_debug_artifacts_$stamp.out.log"
$artifactErr = Join-Path $reportsDir "p2_lane0_health_debug_artifacts_$stamp.err.log"

$buildScript = Join-Path $repoRoot "tools\build_psps_trigger_elf.ps1"
$runScript = Join-Path $repoRoot "tools\run_lane0_hw_once_safe.ps1"
$artifactScript = Join-Path $repoRoot "tools\build_p2_constrained_operational_artifacts.py"

foreach ($path in @($buildScript, $runScript, $artifactScript)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Invoke-LoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$StdoutPath,
        [string]$StderrPath,
        [int]$TimeoutSeconds
    )

    function ConvertTo-CmdArg {
        param([string]$Value)
        if ($Value -match '[\s&()^|<>"]') {
            return '"' + ($Value -replace '"', '""') + '"'
        }
        return $Value
    }

    $argLine = ($Arguments | ForEach-Object { ConvertTo-CmdArg $_ }) -join " "
    $cmdLine = '"' + $FilePath + '" ' + $argLine + ' > "' + $StdoutPath + '" 2> "' + $StderrPath + '"'
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = "cmd.exe"
    $psi.Arguments = '/d /s /c "' + $cmdLine + '"'
    $psi.WorkingDirectory = $repoRoot
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    $done = $proc.WaitForExit($TimeoutSeconds * 1000)
    if (-not $done) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        return 124
    }
    try {
        $proc.WaitForExit()
    } catch {
    }
    $proc.Refresh()
    if ($null -eq $proc.ExitCode) {
        return 125
    }
    return $proc.ExitCode
}

function Invoke-Lane0Build {
    param(
        [int]$PayloadBytes,
        [int]$StageSeconds,
        [string]$StdoutPath,
        [string]$StderrPath
    )
    return Invoke-LoggedProcess `
        -FilePath "powershell.exe" `
        -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $buildScript,
            "-TriggerMode",
            "a_tx_lane0",
            "-XsctPath",
            $XsctPath,
            "-PayloadBytes",
            [string]$PayloadBytes,
            "-StageSeconds",
            [string]$StageSeconds,
            "-StatsIntervalUs",
            "1000000",
            "-MaxPacketBytes",
            "264",
            "-RxTransferBytes",
            "264"
        ) `
        -StdoutPath $StdoutPath `
        -StderrPath $StderrPath `
        -TimeoutSeconds 300
}

"P2_LANE0_HEALTH_DEBUG_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "DEBUG_STAGE_SECONDS=$DebugStageSeconds"
Write-SummaryLine "POST_START_SECONDS=$PostStartSeconds"
Write-SummaryLine "CAPTURE_SECONDS=$CaptureSeconds"
Write-SummaryLine "P2_REPEATABILITY_EVIDENCE_COUNTED=0"

$debugBuildExit = 125
$runExit = 125
$restoreExit = 125
$artifactExit = 125
$machineryOk = $false

try {
    $debugBuildExit = Invoke-Lane0Build -PayloadBytes 256 -StageSeconds $DebugStageSeconds -StdoutPath $debugBuildOut -StderrPath $debugBuildErr
    Write-SummaryLine "DEBUG_BUILD_EXIT=$debugBuildExit"
    Write-SummaryLine "DEBUG_BUILD_OUT=$debugBuildOut"
    Write-SummaryLine "DEBUG_BUILD_ERR=$debugBuildErr"
    if ($debugBuildExit -ne 0) {
        throw "Debug build failed"
    }

    $runExit = Invoke-LoggedProcess `
        -FilePath "powershell.exe" `
        -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            $runScript,
            "-ComPort",
            $ComPort,
            "-BaudRate",
            [string]$BaudRate,
            "-XsctPath",
            $XsctPath,
            "-VivadoPath",
            $VivadoPath,
            "-HwServerUrl",
            $HwServerUrl,
            "-JtagFrequencyHz",
            [string]$JtagFrequencyHz,
            "-XsctWaitSeconds",
            "90",
            "-PostStartSeconds",
            [string]$PostStartSeconds,
            "-CaptureSeconds",
            [string]$CaptureSeconds
        ) `
        -StdoutPath $runOut `
        -StderrPath $runErr `
        -TimeoutSeconds 420
    Write-SummaryLine "DEBUG_RUN_EXIT=$runExit"
    Write-SummaryLine "DEBUG_RUN_OUT=$runOut"
    Write-SummaryLine "DEBUG_RUN_ERR=$runErr"
    $machineryOk = ($runExit -eq 0)
} finally {
    $restoreExit = Invoke-Lane0Build -PayloadBytes 256 -StageSeconds 300 -StdoutPath $restoreBuildOut -StderrPath $restoreBuildErr
    Write-SummaryLine "RESTORE_P2_BUILD_EXIT=$restoreExit"
    Write-SummaryLine "RESTORE_P2_BUILD_OUT=$restoreBuildOut"
    Write-SummaryLine "RESTORE_P2_BUILD_ERR=$restoreBuildErr"

    $artifactExit = Invoke-LoggedProcess `
        -FilePath "python" `
        -Arguments @($artifactScript) `
        -StdoutPath $artifactOut `
        -StderrPath $artifactErr `
        -TimeoutSeconds 120
    Write-SummaryLine "ARTIFACT_REFRESH_EXIT=$artifactExit"
    Write-SummaryLine "ARTIFACT_REFRESH_OUT=$artifactOut"
    Write-SummaryLine "ARTIFACT_REFRESH_ERR=$artifactErr"
}

$runText = ""
if (Test-Path -LiteralPath $runOut) {
    $runText = Get-Content -LiteralPath $runOut -Raw -ErrorAction SilentlyContinue
    foreach ($line in (($runText -split "`r?`n") | Where-Object {
        $_ -match "SOFT_RECOVERY_MATCH|PREFLIGHT_PASS_PARSED|HW_RUN_START|SHUTDOWN_EXIT|HW_WINDOW_TO_SHUTDOWN_END_SECONDS|UART_LOG=|UART_MATCH=PSPS_STAGE_SUMMARY|LANE0_HW_SAFE_RUN_END"
    })) {
        Write-SummaryLine "DEBUG_RUN_MATCH=$line"
    }
}

$summaryLine = [regex]::Match($runText, "UART_MATCH=PSPS_STAGE_SUMMARY .*")
$debugPass = $false
if ($summaryLine.Success) {
    $line = $summaryLine.Value
    $sent = [regex]::Match($line, "\bsent=(\d+)")
    $rxOk = [regex]::Match($line, "\brx_ok=(\d+)")
    $txFail = [regex]::Match($line, "\btx_fail=(\d+)")
    $lastError = [regex]::Match($line, "\blast_error=([^\s]+)")
    if ($sent.Success -and $rxOk.Success -and $txFail.Success -and $lastError.Success) {
        Write-SummaryLine "DEBUG_SENT=$($sent.Groups[1].Value)"
        Write-SummaryLine "DEBUG_RX_OK=$($rxOk.Groups[1].Value)"
        Write-SummaryLine "DEBUG_TX_FAIL=$($txFail.Groups[1].Value)"
        Write-SummaryLine "DEBUG_LAST_ERROR=$($lastError.Groups[1].Value)"
        $debugPass = (
            [int]$sent.Groups[1].Value -gt 0 -and
            [int]$sent.Groups[1].Value -eq [int]$rxOk.Groups[1].Value -and
            [int]$txFail.Groups[1].Value -eq 0 -and
            $lastError.Groups[1].Value -eq "none"
        )
    }
}

Write-SummaryLine "P2_LANE0_HEALTH_DEBUG_PASS=$([int]$debugPass)"
Write-SummaryLine "P2_LANE0_HEALTH_DEBUG_SAFE_END $(Get-Date -Format o)"

$postArtifactOut = Join-Path $reportsDir "p2_lane0_health_debug_artifacts_post_summary_$stamp.out.log"
$postArtifactErr = Join-Path $reportsDir "p2_lane0_health_debug_artifacts_post_summary_$stamp.err.log"
$postArtifactExit = Invoke-LoggedProcess `
    -FilePath "python" `
    -Arguments @($artifactScript) `
    -StdoutPath $postArtifactOut `
    -StderrPath $postArtifactErr `
    -TimeoutSeconds 120
Write-SummaryLine "POST_SUMMARY_ARTIFACT_REFRESH_EXIT=$postArtifactExit"
Write-SummaryLine "POST_SUMMARY_ARTIFACT_REFRESH_OUT=$postArtifactOut"
Write-SummaryLine "POST_SUMMARY_ARTIFACT_REFRESH_ERR=$postArtifactErr"

if ($restoreExit -ne 0 -or $artifactExit -ne 0 -or $postArtifactExit -ne 0) {
    exit 50
}
if (-not $machineryOk) {
    exit $runExit
}
exit 0
