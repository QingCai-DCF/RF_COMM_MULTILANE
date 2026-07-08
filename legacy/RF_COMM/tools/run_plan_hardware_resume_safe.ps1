param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$HwServerUrl = "localhost:3121",
    [string[]]$TriggerModes = @("a_tx_lane0", "a_tx_lane1", "b_tx_nonzero"),
    [int]$JtagFrequencyHz = 1000000,
    [int]$MatrixTimeoutSeconds = 1200,
    [switch]$StopOnFail
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "plan_hw_resume_safe_$stamp.summary.txt"
$preflightLog = Join-Path $reportsDir "plan_hw_resume_safe_$stamp.preflight.log"
$diagLog = Join-Path $reportsDir "plan_hw_resume_safe_$stamp.usb_diag.log"
$repairDryRunLog = Join-Path $reportsDir "plan_hw_resume_safe_$stamp.driver_repair_dry_run.log"
$matrixLog = Join-Path $reportsDir "plan_hw_resume_safe_$stamp.matrix.log"
$auditLog = Join-Path $reportsDir "plan_hw_resume_safe_$stamp.audit.log"
$auditMd = Join-Path $reportsDir "plan_completion_audit_current_20260626.md"
$auditJson = Join-Path $reportsDir "plan_completion_audit_current_20260626.json"

$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$diagScript = Join-Path $repoRoot "tools\diagnose_jtag_usb.ps1"
$repairScript = Join-Path $repoRoot "tools\repair_jtag_drivers_admin.ps1"
$matrixScript = Join-Path $repoRoot "tools\run_2lane_matrix_safe.ps1"
$auditScript = Join-Path $repoRoot "tools\audit_plan_completion.py"

foreach ($path in @($preflightScript, $diagScript, $repairScript, $matrixScript, $auditScript, $VivadoPath, $XsctPath)) {
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
        [string]$LogPath,
        [int]$TimeoutSeconds
    )

    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $LogPath `
        -RedirectStandardError ($LogPath + ".err") `
        -WindowStyle Hidden `
        -PassThru
    $finished = $proc.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        return 124
    }
    $proc.Refresh()
    if ($null -eq $proc.ExitCode) {
        return 0
    }
    return $proc.ExitCode
}

function Normalize-List {
    param([string[]]$Items)
    $out = @()
    foreach ($item in $Items) {
        foreach ($part in ($item -split ",")) {
            $trimmed = $part.Trim()
            if ($trimmed -ne "") {
                $out += $trimmed
            }
        }
    }
    return $out
}

function Run-Audit {
    $code = Invoke-LoggedProcess -FilePath "python.exe" -Arguments @(
        $auditScript,
        "--out",
        $auditMd,
        "--json",
        $auditJson
    ) -LogPath $auditLog -TimeoutSeconds 90
    Write-SummaryLine "AUDIT_EXIT=$code"
    if (Test-Path -LiteralPath $auditLog) {
        foreach ($line in (Get-Content -LiteralPath $auditLog -ErrorAction SilentlyContinue | Where-Object {
            $_ -match "PLAN_AUDIT_SUMMARY|WROTE_"
        })) {
            Write-SummaryLine "AUDIT_MATCH=$line"
        }
    }
    return $code
}

$modes = Normalize-List -Items $TriggerModes

"PLAN_HW_RESUME_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "TRIGGER_MODES=$($modes -join ',')"
Write-SummaryLine "PREFLIGHT_LOG=$preflightLog"
Write-SummaryLine "USB_DIAG_LOG=$diagLog"
Write-SummaryLine "DRIVER_REPAIR_DRY_RUN_LOG=$repairDryRunLog"
Write-SummaryLine "MATRIX_LOG=$matrixLog"
Write-SummaryLine "AUDIT_LOG=$auditLog"

Write-SummaryLine "PREFLIGHT_START=$(Get-Date -Format o)"
$preflightExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $preflightScript,
    "-VivadoPath",
    $VivadoPath,
    "-ComPort",
    $ComPort,
    "-JtagFrequencyHz",
    [string]$JtagFrequencyHz
) -LogPath $preflightLog -TimeoutSeconds 150
Write-SummaryLine "PREFLIGHT_PROCESS_EXIT=$preflightExit"

$preflightText = ""
if (Test-Path -LiteralPath $preflightLog) {
    $preflightText = Get-Content -LiteralPath $preflightLog -Raw -ErrorAction SilentlyContinue
    foreach ($line in (($preflightText -split "`r?`n") | Where-Object {
        $_ -match "COM_PORT_PRESENT|PNP_DEVICE|HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT"
    })) {
        Write-SummaryLine "PREFLIGHT_MATCH=$line"
    }
}

$preflightEffectiveExit = $preflightExit
$vivadoExitMatch = [regex]::Match($preflightText, "VIVADO_PREFLIGHT_EXIT\s*=\s*(\d+)")
if ($vivadoExitMatch.Success) {
    $preflightEffectiveExit = [int]$vivadoExitMatch.Groups[1].Value
}
Write-SummaryLine "PREFLIGHT_EFFECTIVE_EXIT=$preflightEffectiveExit"

$preflightPassed = ($preflightText -match "HW_PREFLIGHT_RESULT PASS" -and $preflightText -match "HW_PREFLIGHT_ZYNQ")
Write-SummaryLine "PREFLIGHT_PASS_PARSED=$([int]$preflightPassed)"

if (-not $preflightPassed) {
    Write-SummaryLine "PREFLIGHT_BLOCKED_NO_PROGRAMMING=1"
    $diagExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $diagScript,
        "-ComPort",
        $ComPort,
        "-SkipVivadoSelfCheck"
    ) -LogPath $diagLog -TimeoutSeconds 90
    Write-SummaryLine "USB_DIAG_EXIT=$diagExit"
    if (Test-Path -LiteralPath $diagLog) {
        foreach ($line in (Get-Content -LiteralPath $diagLog -ErrorAction SilentlyContinue | Where-Object {
            $_ -match "IS_ADMIN|COM_PORT_PRESENT|FTDI6014_|PNPUTIL_CONNECTED_MATCH|VIVADO_PREFLIGHT_SKIPPED|ADMIN_NOTE|NO_PROGRAMMING"
        })) {
            Write-SummaryLine "USB_DIAG_MATCH=$line"
        }
    }
    $repairDryRunExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $repairScript,
        "-VivadoPath",
        $VivadoPath,
        "-ComPort",
        $ComPort,
        "-HwServerUrl",
        $HwServerUrl,
        "-JtagFrequencyHz",
        [string]$JtagFrequencyHz,
        "-SkipPreflight"
    ) -LogPath $repairDryRunLog -TimeoutSeconds 90
    Write-SummaryLine "DRIVER_REPAIR_DRY_RUN_EXIT=$repairDryRunExit"
    if (Test-Path -LiteralPath $repairDryRunLog) {
        foreach ($line in (Get-Content -LiteralPath $repairDryRunLog -ErrorAction SilentlyContinue | Where-Object {
            $_ -match "IS_ADMIN|DRY_RUN|NO_SYSTEM_DRIVER_CHANGE|XILINX_.*PRESENT|TO_APPLY_|JTAG_DRIVER_REPAIR_END"
        })) {
            Write-SummaryLine "DRIVER_REPAIR_DRY_RUN_MATCH=$line"
        }
    }
    Run-Audit | Out-Null
    Write-SummaryLine "PLAN_HW_RESUME_SAFE_END $(Get-Date -Format o)"
    exit 20
}

Write-SummaryLine "MATRIX_START=$(Get-Date -Format o)"
$matrixArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $matrixScript,
    "-ComPort",
    $ComPort,
    "-BaudRate",
    [string]$BaudRate,
    "-XsctPath",
    $XsctPath,
    "-VivadoPath",
    $VivadoPath,
    "-TriggerModes"
) + $modes + @(
    "-JtagFrequencyHz",
    [string]$JtagFrequencyHz
)
if ($StopOnFail) {
    $matrixArgs += "-StopOnFail"
}

$matrixExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $matrixArgs -LogPath $matrixLog -TimeoutSeconds $MatrixTimeoutSeconds
Write-SummaryLine "MATRIX_EXIT=$matrixExit"
if (Test-Path -LiteralPath $matrixLog) {
    foreach ($line in (Get-Content -LiteralPath $matrixLog -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "MATRIX_PREFLIGHT|RUN_RESULT|RUN_SAFETY|MATRIX_ANALYSIS|LANE2_MATRIX_SAFE_END"
    })) {
        Write-SummaryLine "MATRIX_MATCH=$line"
    }
}

Run-Audit | Out-Null
Write-SummaryLine "PLAN_HW_RESUME_SAFE_END $(Get-Date -Format o)"
exit $matrixExit
