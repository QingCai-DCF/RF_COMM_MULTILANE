param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [int]$JtagFrequencyHz = 1000000,
    [int]$WaitPollSeconds = 15,
    [int]$MaxWaitMinutes = 0
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$prefix = "P7_02_b2a_lane0_rxonly_focus_$stamp"
$summaryLog = Join-Path $reportsDir "$prefix.summary.txt"
$buildScript = Join-Path $scriptDir "build_psps_rx_only_elf.ps1"
$singleRunScript = Join-Path $scriptDir "run_2lane_hw_prearmed_ila_safe.ps1"
$analyzerScript = Join-Path $scriptDir "analyze_2lane_ila_csv.py"
$activeElf = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"
$backupElf = Join-Path $reportsDir "$prefix.before.elf.bak"

foreach ($path in @($XsctPath, $VivadoPath, $buildScript, $singleRunScript, $analyzerScript, $activeElf)) {
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
    param([string]$Phase)
    $start = Get-Date
    while ($true) {
        $blockers = @()
        foreach ($proc in (Get-RepoVivadoXsctProcesses)) {
            $shortCommand = [string]$proc.CommandLine
            if ($shortCommand.Length -gt 180) {
                $shortCommand = $shortCommand.Substring(0, 180) + "..."
            }
            $blockers += "process pid=$($proc.ProcessId) name=$($proc.Name) command=$shortCommand"
        }
        $reason = ""
        if (-not (Test-ComPortAvailable -Port $ComPort -Rate $BaudRate -Reason ([ref]$reason))) {
            $blockers += "com_port $ComPort unavailable: $reason"
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

"P7_02_B2A_LANE0_RXONLY_FOCUS_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "PRE_ELF_SHA256=$(Get-Sha256OrMissing -Path $activeElf)"
Copy-Item -LiteralPath $activeElf -Destination $backupElf -Force
Write-SummaryLine "BACKUP_ELF=$backupElf"

$overallExit = 0
try {
    Wait-ExternalBlockers -Phase "before_rxonly_build"
    $buildOut = Join-Path $reportsDir "$prefix.build_rxonly.out.log"
    $buildErr = Join-Path $reportsDir "$prefix.build_rxonly.err.log"
    $buildExit = Invoke-LoggedProcess -Label "BUILD_RXONLY" -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $buildScript,
        "-XsctPath", $XsctPath,
        "-LaneMask", "0x3",
        "-SessionId", "0x2201",
        "-PayloadBytes", "244",
        "-StageSeconds", "60",
        "-PollSleepUs", "0",
        "-MaxPacketBytes", "255",
        "-RxTransferBytes", "255"
    ) -OutLog $buildOut -ErrLog $buildErr
    if ($buildExit -ne 0) {
        $overallExit = $buildExit
        throw "RX-only ELF build failed"
    }
    Write-SummaryLine "RXONLY_ELF_SHA256=$(Get-Sha256OrMissing -Path $activeElf)"

    Wait-ExternalBlockers -Phase "before_b2a_rx_ila"
    $runOut = Join-Path $reportsDir "$prefix.b2a_rx_lane0.run.out.log"
    $runErr = Join-Path $reportsDir "$prefix.b2a_rx_lane0.run.err.log"
    $runExit = Invoke-LoggedProcess -Label "B2A_RX_LANE0_RUN" -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $singleRunScript,
        "-ComPort", $ComPort,
        "-BaudRate", [string]$BaudRate,
        "-XsctPath", $XsctPath,
        "-VivadoPath", $VivadoPath,
        "-TriggerMode", "b2a_rx_lane0",
        "-InitWaitSeconds", "45",
        "-ArmWaitSeconds", "35",
        "-ElfWaitSeconds", "20",
        "-IlaWaitSeconds", "85",
        "-CaptureSeconds", "120",
        "-JtagFrequencyHz", [string]$JtagFrequencyHz
    ) -OutLog $runOut -ErrLog $runErr
    if ($runExit -ne 0) {
        $overallExit = $runExit
    }

    $runText = ""
    if (Test-Path -LiteralPath $runOut) {
        $runText = Get-Content -LiteralPath $runOut -Raw -ErrorAction SilentlyContinue
    }
    $ilaCsv = ""
    $match = [regex]::Match([string]$runText, "(?m)^ILA_CSV=(.+)$")
    if ($match.Success) {
        $ilaCsv = $match.Groups[1].Value.Trim()
    }
    Write-SummaryLine "B2A_RX_LANE0_ILA_CSV=$ilaCsv"
    if ($ilaCsv -and (Test-Path -LiteralPath $ilaCsv)) {
        $analysisMd = Join-Path $reportsDir "$prefix.ila_analysis.md"
        $analysisJson = Join-Path $reportsDir "$prefix.ila_analysis.json"
        $analysisExit = Invoke-LoggedProcess -Label "ANALYZE_MD" -FilePath "python.exe" -Arguments @(
            $analyzerScript,
            $ilaCsv,
            "--out", $analysisMd
        ) -OutLog (Join-Path $reportsDir "$prefix.analyze_md.out.log") -ErrLog (Join-Path $reportsDir "$prefix.analyze_md.err.log")
        $analysisJsonExit = Invoke-LoggedProcess -Label "ANALYZE_JSON" -FilePath "python.exe" -Arguments @(
            $analyzerScript,
            $ilaCsv,
            "--json",
            "--out", $analysisJson
        ) -OutLog (Join-Path $reportsDir "$prefix.analyze_json.out.log") -ErrLog (Join-Path $reportsDir "$prefix.analyze_json.err.log")
        Write-SummaryLine "ANALYSIS_MD=$analysisMd"
        Write-SummaryLine "ANALYSIS_JSON=$analysisJson"
        if ($analysisExit -ne 0 -and $overallExit -eq 0) { $overallExit = $analysisExit }
        if ($analysisJsonExit -ne 0 -and $overallExit -eq 0) { $overallExit = $analysisJsonExit }
    } else {
        Write-SummaryLine "B2A_RX_LANE0_ILA_CSV_MISSING=1"
        if ($overallExit -eq 0) { $overallExit = 4 }
    }
} catch {
    Write-SummaryLine "RUN_ERROR=$($_.Exception.Message)"
    if ($overallExit -eq 0) {
        $overallExit = 30
    }
} finally {
    Copy-Item -LiteralPath $backupElf -Destination $activeElf -Force
    Write-SummaryLine "ELF_RESTORED=1"
    Write-SummaryLine "FINAL_ELF_SHA256=$(Get-Sha256OrMissing -Path $activeElf)"
}

Write-SummaryLine "P7_02_B2A_LANE0_RXONLY_FOCUS_END $(Get-Date -Format o)"
Write-SummaryLine "RUN_EXIT_CODE=$overallExit"
exit $overallExit
