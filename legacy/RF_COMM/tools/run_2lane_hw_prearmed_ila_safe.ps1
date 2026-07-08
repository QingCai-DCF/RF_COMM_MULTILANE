param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$TriggerMode = "b_rx_flush_state",
    [int]$InitWaitSeconds = 45,
    [int]$ArmWaitSeconds = 35,
    [int]$ElfWaitSeconds = 20,
    [int]$IlaWaitSeconds = 85,
    [int]$CaptureSeconds = 120,
    [int]$JtagFrequencyHz = 1000000,
    [int]$ShutdownTimeoutSeconds = 90,
    [switch]$SkipPreflight,
    [switch]$GuardOnly
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$prefix = "2lane_prearmed_${TriggerMode}_$stamp"

$uartLog = Join-Path $reportsDir "uart_$prefix.log"
$initOutLog = Join-Path $reportsDir "xsct_init_$prefix.out.log"
$initErrLog = Join-Path $reportsDir "xsct_init_$prefix.err.log"
$elfOutLog = Join-Path $reportsDir "xsct_elf_$prefix.out.log"
$elfErrLog = Join-Path $reportsDir "xsct_elf_$prefix.err.log"
$ilaCsv = Join-Path $reportsDir "ila_$prefix.csv"
$ilaSummary = Join-Path $reportsDir "ila_$prefix.summary.txt"
$ilaOutLog = Join-Path $reportsDir "ila_$prefix.out.log"
$ilaErrLog = Join-Path $reportsDir "ila_$prefix.err.log"
$shutdownLog = Join-Path $reportsDir "program_tfdu_shutdown_after_$prefix.log"
$shutdownOutLog = Join-Path $reportsDir "program_tfdu_shutdown_after_$prefix.out.log"
$shutdownErrLog = Join-Path $reportsDir "program_tfdu_shutdown_after_$prefix.err.log"
$preflightOutLog = Join-Path $reportsDir "hw_target_preflight_before_$prefix.out.log"
$preflightErrLog = Join-Path $reportsDir "hw_target_preflight_before_$prefix.err.log"
$summaryLog = Join-Path $reportsDir "$prefix.summary.txt"

$initTcl = Join-Path $repoRoot "software\ps_ps_loopback\program_fpga_init_ps7.tcl"
$elfTcl = Join-Path $repoRoot "software\ps_ps_loopback\run_elf_only.tcl"
$ilaTcl = Join-Path $repoRoot "tools\capture_2lane_ila_once.tcl"
$shutdownTcl = Join-Path $repoRoot "tools\program_tfdu_shutdown.tcl"
$preflightTcl = Join-Path $repoRoot "tools\check_hw_target.tcl"
$psMakefile = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\src\subdir.mk"

foreach ($path in @($XsctPath, $VivadoPath, $initTcl, $elfTcl, $ilaTcl, $shutdownTcl, $preflightTcl, $psMakefile)) {
    if (-not (Test-Path $path)) {
        throw "Required path is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -Path $summaryLog -Value $Line -Encoding ascii
}

function Convert-DefineValueToUInt32 {
    param([string]$Value)

    $clean = $Value.Trim()
    $clean = $clean -replace "^[()]+", ""
    $clean = $clean -replace "[()]+$", ""
    $clean = $clean -replace "[uUlL]+$", ""
    if ($clean -match "^0[xX]([0-9a-fA-F]+)$") {
        return [Convert]::ToUInt32($matches[1], 16)
    }
    return [Convert]::ToUInt32($clean, 10)
}

function Get-CompileDefineUInt32 {
    param(
        [string]$Text,
        [string]$Name
    )

    $match = [regex]::Match($Text, "-D" + [regex]::Escape($Name) + "=([^\s]+)")
    if (-not $match.Success) {
        return $null
    }
    return Convert-DefineValueToUInt32 -Value $match.Groups[1].Value
}

function Get-ExpectedPsConfigForTrigger {
    param([string]$Mode)

    switch -Regex ($Mode) {
        "^a_tx_lane0$" {
            return @{
                Known = $true
                LaneMask = 0x1
                PayloadLaneMask = 0x1
                RxLaneMask = 0x1
                Session = 0x2201
                PayloadBytes = 64
                TxOnly = 1
                TdmBidir = 0
                RxOnly = 0
            }
        }
        "^a_tx_lane1$" {
            return @{
                Known = $true
                LaneMask = 0x2
                PayloadLaneMask = 0x2
                RxLaneMask = 0x2
                Session = 0x2202
                PayloadBytes = 64
                TxOnly = 1
                TdmBidir = 0
                RxOnly = 0
            }
        }
        "^b_tx_nonzero$" {
            return @{
                Known = $true
                LaneMask = 0x3
                PayloadLaneMask = 0x3
                RxLaneMask = 0x3
                Session = 0x2203
                PayloadBytes = 247
                TxOnly = 0
                TdmBidir = 1
                RxOnly = 0
            }
        }
        "^b_tx_lane0$" {
            return @{
                Known = $true
                LaneMask = 0x1
                PayloadLaneMask = 0x1
                RxLaneMask = 0x1
                Session = 0x2201
                PayloadBytes = 247
                TxOnly = 0
                TdmBidir = 1
                RxOnly = 0
            }
        }
        "^b_tx_lane1$" {
            return @{
                Known = $true
                LaneMask = 0x2
                PayloadLaneMask = 0x2
                RxLaneMask = 0x2
                Session = 0x2202
                PayloadBytes = 247
                TxOnly = 0
                TdmBidir = 1
                RxOnly = 0
            }
        }
        "^b2a_rx_(nonzero|lane0|lane1)$" {
            return @{
                Known = $true
                LaneMask = 0x3
                PayloadLaneMask = 0x3
                RxLaneMask = 0x3
                Session = 0x2201
                PayloadBytes = 244
                TxOnly = 0
                TdmBidir = 0
                RxOnly = 1
            }
        }
        default {
            return @{
                Known = $false
            }
        }
    }
}

function Test-CompileFlagsForTrigger {
    param(
        [string]$Mode,
        [string]$MakefilePath
    )

    $expected = Get-ExpectedPsConfigForTrigger -Mode $Mode
    [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_TRIGGER=$Mode")
    if (-not $expected.Known) {
        [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_SKIPPED=1")
        [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_REASON=no static PS lane-mask expectation for this trigger")
        return $true
    }

    $text = Get-Content -LiteralPath $MakefilePath -Raw -ErrorAction Stop
    $laneMask = Get-CompileDefineUInt32 -Text $text -Name "PSPS_STAGE_LANE_MASK"
    $payloadLaneMask = Get-CompileDefineUInt32 -Text $text -Name "PSPS_PAYLOAD_LANE_MASK"
    $rxLaneMask = Get-CompileDefineUInt32 -Text $text -Name "PSPS_RX_LANE_MASK"
    $session = Get-CompileDefineUInt32 -Text $text -Name "PSPS_STAGE_SESSION_ID"
    $payloadBytes = Get-CompileDefineUInt32 -Text $text -Name "PSPS_PAYLOAD_BYTES"
    $txOnly = Get-CompileDefineUInt32 -Text $text -Name "PSPS_TX_ONLY"
    $tdmBidir = Get-CompileDefineUInt32 -Text $text -Name "PSPS_TDM_BIDIR"
    $rxOnly = Get-CompileDefineUInt32 -Text $text -Name "PSPS_RX_ONLY"
    $maxPacketBytes = Get-CompileDefineUInt32 -Text $text -Name "IR_HW_MAX_PACKET_BYTES"
    $rxTransferBytes = Get-CompileDefineUInt32 -Text $text -Name "IR_HW_RX_TRANSFER_BYTES"
    if ($null -eq $maxPacketBytes -and $null -ne $rxTransferBytes) {
        $maxPacketBytes = $rxTransferBytes
        [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_INFERRED IR_HW_MAX_PACKET_BYTES=$maxPacketBytes source=IR_HW_RX_TRANSFER_BYTES")
    }

    $ackOnlyTriggerMask = $null
    switch -Regex ($Mode) {
        "^(a_tx_lane0|b_tx_lane0)$" { $ackOnlyTriggerMask = 0x1 }
        "^(a_tx_lane1|b_tx_lane1)$" { $ackOnlyTriggerMask = 0x2 }
        "^(b_rx_check_state|b_rx_flush_state)$" { $ackOnlyTriggerMask = $laneMask }
    }
    $ackOnlyMaskKnown = ($ackOnlyTriggerMask -eq 0x1 -or $ackOnlyTriggerMask -eq 0x2 -or $ackOnlyTriggerMask -eq 0x3)
    $ackOnlyCandidate = (
        $ackOnlyMaskKnown -and
        $laneMask -eq $ackOnlyTriggerMask -and
        $payloadLaneMask -eq $ackOnlyTriggerMask -and
        $rxLaneMask -eq $ackOnlyTriggerMask -and
        $session -eq (0x2200 + $ackOnlyTriggerMask) -and
        $txOnly -eq 1 -and
        $tdmBidir -eq 0 -and
        $rxOnly -eq 0
    )
    if ($ackOnlyCandidate -and $payloadBytes -eq 247 -and $null -eq $maxPacketBytes) {
        $maxPacketBytes = 255
        [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_INFERRED IR_HW_MAX_PACKET_BYTES=255 source=ACK_ONLY_LEGACY_DEFAULT")
    }
    if ($ackOnlyCandidate -and $payloadBytes -eq 247 -and $null -eq $rxTransferBytes) {
        $rxTransferBytes = 255
        [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_INFERRED IR_HW_RX_TRANSFER_BYTES=255 source=ACK_ONLY_LEGACY_DEFAULT")
    }

    [void](Write-SummaryLine ("PS_COMPILE_FLAG_GUARD_ACTUAL lane_mask=0x{0:X} payload_lane_mask=0x{1:X} rx_lane_mask=0x{2:X} session=0x{3:X} payload_bytes={4} tx_only={5} tdm_bidir={6} rx_only={7} max_packet={8} rx_transfer={9}" -f $laneMask, $payloadLaneMask, $rxLaneMask, $session, $payloadBytes, $txOnly, $tdmBidir, $rxOnly, $maxPacketBytes, $rxTransferBytes))
    [void](Write-SummaryLine ("PS_COMPILE_FLAG_GUARD_EXPECT lane_mask=0x{0:X} payload_lane_mask=0x{1:X} rx_lane_mask=0x{2:X} session=0x{3:X} payload_bytes={4} tx_only={5} tdm_bidir={6} rx_only={7}" -f $expected.LaneMask, $expected.PayloadLaneMask, $expected.RxLaneMask, $expected.Session, $expected.PayloadBytes, $expected.TxOnly, $expected.TdmBidir, $expected.RxOnly))

    $missing = @()
    foreach ($pair in @(
        @{Name = "PSPS_STAGE_LANE_MASK"; Value = $laneMask},
        @{Name = "PSPS_PAYLOAD_LANE_MASK"; Value = $payloadLaneMask},
        @{Name = "PSPS_RX_LANE_MASK"; Value = $rxLaneMask},
        @{Name = "PSPS_STAGE_SESSION_ID"; Value = $session},
        @{Name = "PSPS_PAYLOAD_BYTES"; Value = $payloadBytes},
        @{Name = "PSPS_TX_ONLY"; Value = $txOnly},
        @{Name = "PSPS_TDM_BIDIR"; Value = $tdmBidir},
        @{Name = "PSPS_RX_ONLY"; Value = $rxOnly},
        @{Name = "IR_HW_MAX_PACKET_BYTES"; Value = $maxPacketBytes},
        @{Name = "IR_HW_RX_TRANSFER_BYTES"; Value = $rxTransferBytes}
    )) {
        if ($null -eq $pair.Value) {
            $missing += $pair.Name
        }
    }
    if ($missing.Count -gt 0) {
        [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_PASS=0")
        [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_MISSING=$($missing -join ',')")
        return $false
    }

    $rawBytes = $payloadBytes + 8
    $ackOnlyLegacyOk = (
        $ackOnlyCandidate -and
        $payloadBytes -eq 247 -and
        $maxPacketBytes -le 255 -and
        $rxTransferBytes -le 255 -and
        $rawBytes -le $maxPacketBytes
    )
    $ackOnlyG1SizedOk = (
        $ackOnlyCandidate -and
        $payloadBytes -eq 256 -and
        $rawBytes -eq 264 -and
        $maxPacketBytes -eq 264 -and
        $rxTransferBytes -eq 264
    )
    if ($ackOnlyLegacyOk -or $ackOnlyG1SizedOk) {
        $profileName = if ($ackOnlyG1SizedOk) { "ACK_ONLY_G1_SIZED" } else { "ACK_ONLY_LEGACY" }
        [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_PROFILE=$profileName")
        [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_RAW_BYTES=$rawBytes")
        [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_PASS=1")
        return $true
    }

    $ok = (
        $laneMask -eq $expected.LaneMask -and
        $payloadLaneMask -eq $expected.PayloadLaneMask -and
        $rxLaneMask -eq $expected.RxLaneMask -and
        $session -eq $expected.Session -and
        $payloadBytes -eq $expected.PayloadBytes -and
        $txOnly -eq $expected.TxOnly -and
        $tdmBidir -eq $expected.TdmBidir -and
        $rxOnly -eq $expected.RxOnly -and
        $maxPacketBytes -le 255 -and
        $rxTransferBytes -le 255 -and
        $rawBytes -le $maxPacketBytes
    )
    [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_RAW_BYTES=$rawBytes")
    [void](Write-SummaryLine "PS_COMPILE_FLAG_GUARD_PASS=$([int]$ok)")
    return $ok
}

function Wait-FileContains {
    param(
        [string]$Path,
        [string]$Pattern,
        [int]$TimeoutSeconds,
        [System.Diagnostics.Process]$Process
    )

    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        if ($Process -and $Process.HasExited) {
            return $false
        }
        if (Test-Path $Path) {
            $text = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
            if ($text -match $Pattern) {
                return $true
            }
        }
        Start-Sleep -Milliseconds 250
    }
    return $false
}

"LANE2_PREARMED_SAFE_RUN_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "UART_LOG=$uartLog"
Write-SummaryLine "INIT_STDOUT_LOG=$initOutLog"
Write-SummaryLine "INIT_STDERR_LOG=$initErrLog"
Write-SummaryLine "ELF_STDOUT_LOG=$elfOutLog"
Write-SummaryLine "ELF_STDERR_LOG=$elfErrLog"
Write-SummaryLine "ILA_CSV=$ilaCsv"
Write-SummaryLine "ILA_SUMMARY=$ilaSummary"
Write-SummaryLine "ILA_STDOUT_LOG=$ilaOutLog"
Write-SummaryLine "ILA_STDERR_LOG=$ilaErrLog"
Write-SummaryLine "SHUTDOWN_LOG=$shutdownLog"
Write-SummaryLine "PREFLIGHT_STDOUT_LOG=$preflightOutLog"
Write-SummaryLine "PREFLIGHT_STDERR_LOG=$preflightErrLog"
Write-SummaryLine "TRIGGER_MODE=$TriggerMode"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "SHUTDOWN_TIMEOUT_SECONDS=$ShutdownTimeoutSeconds"
Write-SummaryLine "SKIP_PREFLIGHT=$([int]$SkipPreflight.IsPresent)"
Write-SummaryLine "GUARD_ONLY=$([int]$GuardOnly.IsPresent)"
Write-SummaryLine "PS_MAKEFILE=$psMakefile"

if (-not (Test-CompileFlagsForTrigger -Mode $TriggerMode -MakefilePath $psMakefile)) {
    Write-SummaryLine "PS_COMPILE_FLAG_GUARD_BLOCKED_NO_PROGRAMMING=1"
    Write-SummaryLine "LANE2_PREARMED_SAFE_RUN_END $(Get-Date -Format o)"
    Write-SummaryLine "RUN_RESULT_STATUS=FAIL_PS_COMPILE_FLAG_GUARD"
    Write-SummaryLine "RUN_EXIT_CODE=21"
    exit 21
}
if ($GuardOnly) {
    Write-SummaryLine "GUARD_ONLY_NO_HARDWARE_PROGRAMMING=1"
    Write-SummaryLine "GUARD_ONLY_NO_UART_WRITE=1"
    Write-SummaryLine "GUARD_ONLY_NO_TFDU_DRIVE=1"
    Write-SummaryLine "LANE2_PREARMED_SAFE_RUN_END $(Get-Date -Format o)"
    Write-SummaryLine "RUN_RESULT_STATUS=PASS_GUARD_ONLY"
    Write-SummaryLine "RUN_EXIT_CODE=0"
    exit 0
}

if (-not $SkipPreflight) {
    Write-SummaryLine "PREFLIGHT_START=$(Get-Date -Format o)"
    & $VivadoPath -mode batch -notrace -source $preflightTcl -tclargs "localhost:3121" ([string]$JtagFrequencyHz) *> $preflightOutLog 2> $preflightErrLog
    $preflightExit = $LASTEXITCODE
    Write-SummaryLine "PREFLIGHT_EXIT=$preflightExit"
    if (Test-Path -LiteralPath $preflightOutLog) {
        $preflightLines = Get-Content -LiteralPath $preflightOutLog -ErrorAction SilentlyContinue | Where-Object {
            $_ -match "HW_PREFLIGHT|Labtools|ERROR|WARNING"
        }
        foreach ($line in ($preflightLines | Select-Object -Last 60)) {
            Write-SummaryLine "PREFLIGHT_MATCH=$line"
        }
    }
    if ((Test-Path -LiteralPath $preflightErrLog) -and (Get-Item -LiteralPath $preflightErrLog).Length -gt 0) {
        foreach ($line in (Get-Content -LiteralPath $preflightErrLog -ErrorAction SilentlyContinue | Select-Object -Last 20)) {
            Write-SummaryLine "PREFLIGHT_STDERR=$line"
        }
    }
    if ($preflightExit -ne 0) {
        Write-SummaryLine "PREFLIGHT_BLOCKED_NO_PROGRAMMING=1"
        Write-SummaryLine "LANE2_PREARMED_SAFE_RUN_END $(Get-Date -Format o)"
        exit 20
    }
}

$uartJob = Start-Job -ScriptBlock {
    param($Port, $Rate, $LogPath, $Seconds)

    "UART_CAPTURE_BEGIN $(Get-Date -Format o) port=$Port baud=$Rate" | Out-File -FilePath $LogPath -Encoding ascii

    try {
        $serial = New-Object System.IO.Ports.SerialPort $Port, $Rate, "None", 8, "One"
        $serial.ReadTimeout = 200
        $serial.DtrEnable = $false
        $serial.RtsEnable = $false

        $opened = $false
        for ($attempt = 1; $attempt -le 30 -and -not $opened; $attempt++) {
            try {
                $serial.Open()
                $opened = $true
            } catch {
                Add-Content -Path $LogPath -Value "`r`nUART_OPEN_RETRY attempt=$attempt error=$($_.Exception.Message)" -Encoding ascii
                Start-Sleep -Milliseconds 250
            }
        }
        if (-not $opened) {
            throw "Unable to open $Port after retries"
        }

        $timer = [System.Diagnostics.Stopwatch]::StartNew()
        while ($timer.Elapsed.TotalSeconds -lt $Seconds) {
            $chunk = $serial.ReadExisting()
            if ($chunk.Length -gt 0) {
                Add-Content -Path $LogPath -Value $chunk -NoNewline -Encoding ascii
            }
            Start-Sleep -Milliseconds 50
        }
    } catch {
        Add-Content -Path $LogPath -Value "`r`nUART_CAPTURE_ERROR $($_.Exception.Message)" -Encoding ascii
    } finally {
        if ($serial -and $serial.IsOpen) {
            $serial.Close()
        }
        Add-Content -Path $LogPath -Value "`r`nUART_CAPTURE_END $(Get-Date -Format o)" -Encoding ascii
    }
} -ArgumentList $ComPort, $BaudRate, $uartLog, $CaptureSeconds

$runStart = Get-Date
$shutdownExit = $null
$initExit = $null
$elfExit = $null
$ilaExit = $null
$ilaTimedOut = $false
$ilaProc = $null
$runError = $null

try {
    Write-SummaryLine "HW_RUN_START=$($runStart.ToString('o'))"

    Write-SummaryLine "INIT_START=$(Get-Date -Format o)"
    $initProc = Start-Process -FilePath $XsctPath `
        -ArgumentList @($initTcl) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $initOutLog `
        -RedirectStandardError $initErrLog `
        -WindowStyle Hidden `
        -PassThru
    $initDone = $initProc.WaitForExit($InitWaitSeconds * 1000)
    if (-not $initDone) {
        Write-SummaryLine "INIT_TIMEOUT_KILLED=1"
        Stop-Process -Id $initProc.Id -Force -ErrorAction SilentlyContinue
        throw "FPGA/PS7 init timed out"
    }
    $initProc.Refresh()
    $initExit = $initProc.ExitCode
    if ($null -eq $initExit -and (Test-Path $initOutLog)) {
        $initText = Get-Content -Path $initOutLog -Raw -ErrorAction SilentlyContinue
        if ($initText -match "PS7_INIT_READY_NO_ELF") {
            $initExit = 0
            Write-SummaryLine "INIT_EXIT_INFERRED=0"
        }
    }
    Write-SummaryLine "INIT_EXIT=$initExit"
    if ($initExit -ne 0) {
        throw "FPGA/PS7 init failed"
    }

    Write-SummaryLine "ILA_ARM_START=$(Get-Date -Format o)"
    $ilaProc = Start-Process -FilePath $VivadoPath `
        -ArgumentList @("-mode", "batch", "-source", $ilaTcl, "-tclargs", $ilaCsv, $ilaSummary, $TriggerMode, [string]$JtagFrequencyHz) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $ilaOutLog `
        -RedirectStandardError $ilaErrLog `
        -WindowStyle Hidden `
        -PassThru

    $armed = Wait-FileContains -Path $ilaSummary -Pattern "ILA2_RUN_WAIT_|ILA2_RUN_TRIGGER_NOW" -TimeoutSeconds $ArmWaitSeconds -Process $ilaProc
    Write-SummaryLine "ILA_ARMED=$([int]$armed)"
    if (-not $armed) {
        if (-not $ilaProc.HasExited) {
            Stop-Process -Id $ilaProc.Id -Force -ErrorAction SilentlyContinue
        }
        throw "ILA did not arm before timeout"
    }

    Write-SummaryLine "ELF_START=$(Get-Date -Format o)"
    $elfProc = Start-Process -FilePath $XsctPath `
        -ArgumentList @($elfTcl) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $elfOutLog `
        -RedirectStandardError $elfErrLog `
        -WindowStyle Hidden `
        -PassThru
    $elfDone = $elfProc.WaitForExit($ElfWaitSeconds * 1000)
    if ($elfDone) {
        $elfProc.Refresh()
        $elfExit = $elfProc.ExitCode
        if ($null -eq $elfExit -and (Test-Path $elfOutLog)) {
            $elfText = Get-Content -Path $elfOutLog -Raw -ErrorAction SilentlyContinue
            if ($elfText -match "PS_ELF_STARTED_NO_FPGA") {
                $elfExit = 0
                Write-SummaryLine "ELF_EXIT_INFERRED=0"
            }
        }
        Write-SummaryLine "ELF_EXIT=$elfExit"
        if ($elfExit -ne 0) {
            throw "ELF start failed"
        }
    } else {
        Write-SummaryLine "ELF_TIMEOUT_KILLED=1"
        Stop-Process -Id $elfProc.Id -Force -ErrorAction SilentlyContinue
    }

    $ilaDone = $ilaProc.WaitForExit($IlaWaitSeconds * 1000)
    if ($ilaDone) {
        $ilaProc.Refresh()
        $ilaExit = $ilaProc.ExitCode
        if ($null -eq $ilaExit -and (Test-Path $ilaSummary)) {
            $ilaText = Get-Content -Path $ilaSummary -Raw -ErrorAction SilentlyContinue
            if ($ilaText -match "ILA2_CAPTURE_DONE") {
                $ilaExit = 0
                Write-SummaryLine "ILA_EXIT_INFERRED=0"
            }
        }
        Write-SummaryLine "ILA_EXIT=$ilaExit"
    } else {
        $ilaTimedOut = $true
        Write-SummaryLine "ILA_TIMEOUT_KILLED=1"
        Stop-Process -Id $ilaProc.Id -Force -ErrorAction SilentlyContinue
    }
} catch {
    $runError = $_
    Write-SummaryLine "RUN_ERROR=$($_.Exception.Message)"
} finally {
    $shutdownStart = Get-Date
    Write-SummaryLine "SHUTDOWN_START=$($shutdownStart.ToString('o'))"

    if ($ilaProc -and -not $ilaProc.HasExited) {
        Stop-Process -Id $ilaProc.Id -Force -ErrorAction SilentlyContinue
    }

    $shutdownProc = Start-Process -FilePath $VivadoPath `
        -ArgumentList @("-mode", "batch", "-source", $shutdownTcl) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $shutdownOutLog `
        -RedirectStandardError $shutdownErrLog `
        -WindowStyle Hidden `
        -PassThru
    $shutdownDone = $shutdownProc.WaitForExit($ShutdownTimeoutSeconds * 1000)
    if (-not $shutdownDone) {
        Write-SummaryLine "SHUTDOWN_TIMEOUT_KILLED=1"
        Stop-Process -Id $shutdownProc.Id -Force -ErrorAction SilentlyContinue
        $shutdownExit = 124
    } else {
        $shutdownProc.Refresh()
        $shutdownExit = $shutdownProc.ExitCode
    }

    @(
        "STDOUT:"
        if (Test-Path $shutdownOutLog) { Get-Content -Path $shutdownOutLog -ErrorAction SilentlyContinue }
        "STDERR:"
        if (Test-Path $shutdownErrLog) { Get-Content -Path $shutdownErrLog -ErrorAction SilentlyContinue }
    ) | Out-File -FilePath $shutdownLog -Encoding ascii

    $shutdownEnd = Get-Date
    Write-SummaryLine "SHUTDOWN_END=$($shutdownEnd.ToString('o'))"
    Write-SummaryLine "SHUTDOWN_EXIT=$shutdownExit"
    Write-SummaryLine ("HW_WINDOW_TO_SHUTDOWN_START_SECONDS={0:N1}" -f (($shutdownStart - $runStart).TotalSeconds))
    Write-SummaryLine ("HW_WINDOW_TO_SHUTDOWN_END_SECONDS={0:N1}" -f (($shutdownEnd - $runStart).TotalSeconds))

    Wait-Job -Job $uartJob -Timeout 5 | Out-Null
    if ($uartJob.State -eq "Running") {
        Stop-Job -Job $uartJob -ErrorAction SilentlyContinue
    }
    Receive-Job -Job $uartJob -ErrorAction SilentlyContinue | Out-Null
    Remove-Job -Job $uartJob -Force -ErrorAction SilentlyContinue
}

if (Test-Path $uartLog) {
    $uartText = Get-Content -Path $uartLog -Raw -ErrorAction SilentlyContinue
    $interesting = $uartText -split "`r?`n" | Where-Object {
        $_ -match "PSPS_(INIT_OK|STAGE_BEGIN|STATS|STAGE_SUMMARY|TDM_STATS|TDM_STAGE_SUMMARY)|RF_COMM PS-PS loopback"
    }
    foreach ($line in ($interesting | Select-Object -Last 30)) {
        Write-SummaryLine "UART_MATCH=$line"
    }
}

if (Test-Path $ilaCsv) {
    Write-SummaryLine "ILA_CSV_SIZE=$((Get-Item -LiteralPath $ilaCsv).Length)"
} else {
    Write-SummaryLine "ILA_CSV_MISSING=1"
}

if ($null -eq $shutdownExit -and (Test-Path $shutdownLog)) {
    $shutdownText = Get-Content -Path $shutdownLog -Raw -ErrorAction SilentlyContinue
    if ($shutdownText -match "TFDU_SHUTDOWN_PROGRAMMED") {
        $shutdownExit = 0
        Write-SummaryLine "SHUTDOWN_EXIT_INFERRED=0"
    }
}
if ($null -eq $shutdownExit) {
    $shutdownExit = -1
    Write-SummaryLine "SHUTDOWN_EXIT_INFERRED=-1"
}

Write-SummaryLine "LANE2_PREARMED_SAFE_RUN_END $(Get-Date -Format o)"

if ($shutdownExit -ne 0) {
    Write-SummaryLine "RUN_RESULT_STATUS=FAIL_SHUTDOWN"
    Write-SummaryLine "RUN_EXIT_CODE=31"
    throw "Shutdown programming failed, see $shutdownLog"
}

if ($null -ne $runError) {
    Write-SummaryLine "RUN_ERROR_FINAL=$($runError.Exception.Message)"
    Write-SummaryLine "RUN_RESULT_STATUS=FAIL_RUN_ERROR"
    Write-SummaryLine "RUN_EXIT_CODE=10"
    exit 10
}

if ($ilaTimedOut) {
    Write-SummaryLine "RUN_RESULT_STATUS=FAIL_ILA_TIMEOUT"
    Write-SummaryLine "RUN_EXIT_CODE=3"
    exit 3
}

if ($null -ne $ilaExit -and $ilaExit -ne 0) {
    Write-SummaryLine "RUN_RESULT_STATUS=FAIL_ILA_EXIT"
    Write-SummaryLine "RUN_EXIT_CODE=$ilaExit"
    exit $ilaExit
}

if ($null -ne $elfExit -and $elfExit -ne 0) {
    Write-SummaryLine "RUN_RESULT_STATUS=FAIL_ELF_EXIT"
    Write-SummaryLine "RUN_EXIT_CODE=$elfExit"
    exit $elfExit
}

if ($null -ne $initExit -and $initExit -ne 0) {
    Write-SummaryLine "RUN_RESULT_STATUS=FAIL_INIT_EXIT"
    Write-SummaryLine "RUN_EXIT_CODE=$initExit"
    exit $initExit
}

if (-not (Test-Path $ilaCsv)) {
    Write-SummaryLine "RUN_RESULT_STATUS=FAIL_ILA_CSV_MISSING"
    Write-SummaryLine "RUN_EXIT_CODE=4"
    exit 4
}

Write-SummaryLine "RUN_RESULT_STATUS=PASS"
Write-SummaryLine "RUN_EXIT_CODE=0"
exit 0
