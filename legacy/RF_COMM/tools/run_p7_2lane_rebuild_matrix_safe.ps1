param(
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [int]$JtagFrequencyHz = 1000000,
    [int]$Jobs = 16,
    [int]$WaitPollSeconds = 15,
    [int]$MaxWaitMinutes = 0,
    [switch]$SkipBuild,
    [switch]$SkipMatrix
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = "{0}_pid{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$prefix = "P7_02_2lane_rebuild_matrix_$stamp"
$summaryLog = Join-Path $reportsDir "$prefix.summary.txt"
$backupDir = Join-Path $reportsDir "$prefix.backup"
$buildTcl = Join-Path $scriptDir "build_current_bitstream.tcl"
$matrixScript = Join-Path $scriptDir "run_2lane_matrix_safe.ps1"
$guardScript = Join-Path $scriptDir "check_active_artifact_stage.py"

$activeBit = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"
$activeLtx = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.ltx"
$topBitCopy = Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.bit"
$activeXsa = Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.xsa"
$activeElf = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"

foreach ($path in @($VivadoPath, $XsctPath, $buildTcl, $matrixScript, $guardScript)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Get-Sha256OrMissing {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return "MISSING"
    }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToUpperInvariant()
}

function Copy-IfPresent {
    param(
        [string]$Source,
        [string]$Destination
    )
    if (Test-Path -LiteralPath $Source -PathType Leaf) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        return $true
    }
    return $false
}

function Test-ComPortAvailable {
    param(
        [string]$Port,
        [int]$Rate,
        [ref]$Reason
    )
    try {
        $serial = New-Object System.IO.Ports.SerialPort $Port, $Rate, "None", 8, "One"
        $serial.ReadTimeout = 200
        $serial.WriteTimeout = 200
        $serial.DtrEnable = $false
        $serial.RtsEnable = $false
        $serial.Open()
        $serial.Close()
        $Reason.Value = ""
        return $true
    } catch {
        $Reason.Value = $_.Exception.Message
        return $false
    } finally {
        if ($null -ne $serial -and $serial.IsOpen) {
            $serial.Close()
        }
    }
}

function Get-RepoVivadoXsctProcesses {
    $escapedRoot = [regex]::Escape($repoRoot)
    $currentPid = $PID
    return @(Get-CimInstance Win32_Process | Where-Object {
        $command = [string]$_.CommandLine
        $_.ProcessId -ne $currentPid -and
        $command -and
        $command -match $escapedRoot -and
        $command -notmatch "hw_server(\.bat|\.exe)?" -and
        ($_.Name -match "^(vivado|vivado\.bat|xsct|xsct\.bat|cmd)\.exe$" -or $command -match "(vivado|xsct)")
    } | Select-Object ProcessId, Name, CommandLine)
}

function Wait-ExternalBlockers {
    param(
        [string]$Phase,
        [bool]$NeedComPort
    )

    $start = Get-Date
    while ($true) {
        $blockers = @()
        $procs = Get-RepoVivadoXsctProcesses
        foreach ($proc in $procs) {
            $shortCommand = [string]$proc.CommandLine
            if ($shortCommand.Length -gt 180) {
                $shortCommand = $shortCommand.Substring(0, 180) + "..."
            }
            $blockers += "process pid=$($proc.ProcessId) name=$($proc.Name) command=$shortCommand"
        }

        if ($NeedComPort) {
            $reason = ""
            if (-not (Test-ComPortAvailable -Port $ComPort -Rate $BaudRate -Reason ([ref]$reason))) {
                $blockers += "com_port $ComPort unavailable: $reason"
            }
        }

        if ($blockers.Count -eq 0) {
            Write-SummaryLine "WAIT_CLEAR phase=$Phase elapsed_s=$([int]((Get-Date) - $start).TotalSeconds)"
            return
        }

        $elapsedMinutes = ((Get-Date) - $start).TotalMinutes
        foreach ($blocker in $blockers) {
            Write-SummaryLine "WAIT_BLOCKED phase=$Phase elapsed_min=$([math]::Round($elapsedMinutes, 1)) blocker=$blocker"
        }
        if ($MaxWaitMinutes -gt 0 -and $elapsedMinutes -ge $MaxWaitMinutes) {
            Write-SummaryLine "WAIT_TIMEOUT phase=$Phase max_wait_min=$MaxWaitMinutes"
            exit 40
        }
        Start-Sleep -Seconds $WaitPollSeconds
    }
}

function Invoke-LoggedProcess {
    param(
        [string]$Label,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$OutLog,
        [string]$ErrLog
    )

    Write-SummaryLine "${Label}_COMMAND=$FilePath $($Arguments -join ' ')"
    Write-SummaryLine "${Label}_OUT_LOG=$OutLog"
    Write-SummaryLine "${Label}_ERR_LOG=$ErrLog"
    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -WindowStyle Hidden `
        -PassThru
    $proc.WaitForExit()
    $proc.Refresh()
    $exitCode = if ($null -eq $proc.ExitCode) { 0 } else { [int]$proc.ExitCode }
    Write-SummaryLine "${Label}_EXIT=$exitCode"
    return $exitCode
}

function Restore-Backups {
    param([string]$Reason)
    Write-SummaryLine "RESTORE_BACKUPS_START reason=$Reason"
    Copy-IfPresent -Source (Join-Path $backupDir "design_shiboqi_wrapper.runs_impl_1.bit") -Destination $activeBit | Out-Null
    Copy-IfPresent -Source (Join-Path $backupDir "design_shiboqi_wrapper.runs_impl_1.ltx") -Destination $activeLtx | Out-Null
    Copy-IfPresent -Source (Join-Path $backupDir "design_shiboqi_wrapper.top_copy.bit") -Destination $topBitCopy | Out-Null
    Copy-IfPresent -Source (Join-Path $backupDir "design_shiboqi_wrapper.xsa") -Destination $activeXsa | Out-Null
    Copy-IfPresent -Source (Join-Path $backupDir "rf_comm_ps_ps_loopback.elf") -Destination $activeElf | Out-Null
    Write-SummaryLine "RESTORE_BACKUPS_DONE reason=$Reason"
}

"P7_02_2LANE_REBUILD_MATRIX_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "VIVADO_PATH=$VivadoPath"
Write-SummaryLine "XSCT_PATH=$XsctPath"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "JOBS=$Jobs"
Write-SummaryLine "WAIT_POLL_SECONDS=$WaitPollSeconds"
Write-SummaryLine "MAX_WAIT_MINUTES=$MaxWaitMinutes"
Write-SummaryLine "SKIP_BUILD=$([int]$SkipBuild.IsPresent)"
Write-SummaryLine "SKIP_MATRIX=$([int]$SkipMatrix.IsPresent)"
Write-SummaryLine "BACKUP_DIR=$backupDir"

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$backupMap = @(
    @{ Source = $activeBit; Name = "design_shiboqi_wrapper.runs_impl_1.bit" },
    @{ Source = $activeLtx; Name = "design_shiboqi_wrapper.runs_impl_1.ltx" },
    @{ Source = $topBitCopy; Name = "design_shiboqi_wrapper.top_copy.bit" },
    @{ Source = $activeXsa; Name = "design_shiboqi_wrapper.xsa" },
    @{ Source = $activeElf; Name = "rf_comm_ps_ps_loopback.elf" }
)
foreach ($item in $backupMap) {
    $source = [string]$item.Source
    $name = [string]$item.Name
    $dest = Join-Path $backupDir $name
    $copied = Copy-IfPresent -Source $source -Destination $dest
    Write-SummaryLine "BACKUP_FILE name=$name copied=$([int]$copied) sha256=$(Get-Sha256OrMissing -Path $source) source=$source"
}

$env:VIVADO_MAX_THREADS = [string]$Jobs

if (-not $SkipBuild) {
    Wait-ExternalBlockers -Phase "before_build" -NeedComPort $false
    $buildOut = Join-Path $reportsDir "$prefix.build_current_bitstream.out.log"
    $buildErr = Join-Path $reportsDir "$prefix.build_current_bitstream.err.log"
    $buildLog = Join-Path $reportsDir "$prefix.build_current_bitstream.vivado.log"
    $buildJournal = Join-Path $reportsDir "$prefix.build_current_bitstream.vivado.jou"
    $buildExit = Invoke-LoggedProcess -Label "BUILD_CURRENT_BITSTREAM" -FilePath $VivadoPath -Arguments @(
        "-mode", "batch",
        "-source", $buildTcl,
        "-notrace",
        "-log", $buildLog,
        "-journal", $buildJournal
    ) -OutLog $buildOut -ErrLog $buildErr
    if ($buildExit -ne 0) {
        Write-SummaryLine "BUILD_RESULT=FAIL"
        Restore-Backups -Reason "build_failed"
        Write-SummaryLine "P7_02_2LANE_REBUILD_MATRIX_END $(Get-Date -Format o)"
        exit $buildExit
    }
    Write-SummaryLine "BUILD_RESULT=PASS"
} else {
    Write-SummaryLine "BUILD_RESULT=SKIPPED"
}

foreach ($path in @($activeBit, $activeLtx, $topBitCopy, $activeXsa, $activeElf)) {
    Write-SummaryLine "POST_BUILD_HASH path=$path sha256=$(Get-Sha256OrMissing -Path $path)"
}

$guardOut = Join-Path $reportsDir "$prefix.active_artifact_guard.md"
$guardJson = Join-Path $reportsDir "$prefix.active_artifact_guard.json"
$guardExit = Invoke-LoggedProcess -Label "ACTIVE_ARTIFACT_GUARD" -FilePath "python.exe" -Arguments @(
    $guardScript,
    "--expect", "ANY",
    "--out", $guardOut,
    "--json", $guardJson
) -OutLog (Join-Path $reportsDir "$prefix.active_artifact_guard.out.log") -ErrLog (Join-Path $reportsDir "$prefix.active_artifact_guard.err.log")
Write-SummaryLine "ACTIVE_ARTIFACT_GUARD_NONBLOCKING_EXIT=$guardExit"

$matrixExit = 0
if (-not $SkipMatrix) {
    Copy-IfPresent -Source $activeElf -Destination (Join-Path $backupDir "rf_comm_ps_ps_loopback.before_matrix.elf") | Out-Null
    $attempt = 0
    while ($true) {
        $attempt += 1
        Wait-ExternalBlockers -Phase "before_matrix_attempt_$attempt" -NeedComPort $true
        $matrixOut = Join-Path $reportsDir "$prefix.matrix_attempt_$attempt.out.log"
        $matrixErr = Join-Path $reportsDir "$prefix.matrix_attempt_$attempt.err.log"
        $matrixExit = Invoke-LoggedProcess -Label "MATRIX_ATTEMPT_$attempt" -FilePath "powershell.exe" -Arguments @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $matrixScript,
            "-ComPort", $ComPort,
            "-BaudRate", [string]$BaudRate,
            "-XsctPath", $XsctPath,
            "-VivadoPath", $VivadoPath,
            "-TriggerModes", "a_tx_lane0,a_tx_lane1,b_tx_lane0,b_tx_lane1",
            "-JtagFrequencyHz", [string]$JtagFrequencyHz,
            "-PerRunTimeoutSeconds", "300",
            "-MaxTfduWindowSeconds", "300",
            "-WaitPollSeconds", [string]$WaitPollSeconds,
            "-MaxWaitMinutes", [string]$MaxWaitMinutes,
            "-AutoBuildPsElfPerTrigger"
        ) -OutLog $matrixOut -ErrLog $matrixErr
        if (Test-Path -LiteralPath $matrixOut -PathType Leaf) {
            $matrixText = Get-Content -LiteralPath $matrixOut -Raw -ErrorAction SilentlyContinue
            $matrixOverallMatch = [regex]::Match([string]$matrixText, "(?m)^MATRIX_OVERALL_EXIT=(\d+)")
            if ($matrixOverallMatch.Success) {
                $matrixParsedExit = [int]$matrixOverallMatch.Groups[1].Value
                Write-SummaryLine "MATRIX_ATTEMPT_${attempt}_PARSED_MATRIX_OVERALL_EXIT=$matrixParsedExit"
                $matrixExit = $matrixParsedExit
            }
        }
        if ($matrixExit -ne 20) {
            break
        }
        Write-SummaryLine "MATRIX_ATTEMPT_BLOCKED_RETRY attempt=$attempt exit=$matrixExit"
        if ($MaxWaitMinutes -gt 0) {
            Write-SummaryLine "MATRIX_BLOCKED_MAX_WAIT_CONTROLLED_BY_WAIT_LOOP=1"
        }
        Start-Sleep -Seconds $WaitPollSeconds
    }
    Copy-IfPresent -Source (Join-Path $backupDir "rf_comm_ps_ps_loopback.before_matrix.elf") -Destination $activeElf | Out-Null
    Write-SummaryLine "ELF_RESTORED_AFTER_MATRIX=1"
    Write-SummaryLine "MATRIX_RESULT_EXIT=$matrixExit"
} else {
    Write-SummaryLine "MATRIX_RESULT_EXIT=SKIPPED"
}

foreach ($path in @($activeBit, $activeLtx, $topBitCopy, $activeXsa, $activeElf)) {
    Write-SummaryLine "FINAL_HASH path=$path sha256=$(Get-Sha256OrMissing -Path $path)"
}

Write-SummaryLine "P7_02_2LANE_REBUILD_MATRIX_END $(Get-Date -Format o)"
exit $matrixExit
