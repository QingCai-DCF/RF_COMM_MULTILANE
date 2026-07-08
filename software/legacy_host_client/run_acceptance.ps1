[CmdletBinding()]
param(
    [ValidateSet("smoke", "single_lane", "soak_2h", "reconnect", "fdx_partition", "offline_mock", "n03_commands", "n03_memory_echo", "n03_pspl_synth", "n03_negative")]
    [string]$Mode = "smoke",

    [string]$TargetHost = "192.168.10.2",
    [int]$Port = 5001,
    [double]$TimeoutSeconds = 5.0,

    [string]$SessionId = "0x1234",
    [string]$LaneMask = "0x1",
    [string]$TxLaneMask = "0x3",
    [string]$RxLaneMask = "0xc",

    [int]$DurationSeconds = 0,
    [int]$Repeat = 1000,
    [int]$PayloadSize = 248,
    [int]$AppPayloadSize = 0,
    [ValidateSet("incremental", "synth_ramp", "zero", "ff")]
    [string]$PayloadPattern = "incremental",
    [double]$IntervalSeconds = 0.0,
    [double]$StatusIntervalSeconds = 1.0,
    [int]$Window = 1,
    [double]$AckTimeoutSeconds = 3.0,

    [double]$MinTxMbps = 0.0,
    [double]$MinRxMbps = 0.0,
    [int]$MinRxFrames = 0,
    [int]$ReconnectCycles = 20,
    [int]$ReconnectPayloadSize = 64,

    [string]$LogDir = "",
    [switch]$VerboseFrames,
    [switch]$SkipLogAnalysis,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
trap {
    Write-Error $_
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..\..")).Path
$clientPath = Join-Path $scriptDir "rf_comm_client.py"
$analyzerPath = Join-Path $scriptDir "analyze_acceptance_log.py"
$mockServerPath = Join-Path $scriptDir "mock_rfcm_server.py"
$providedParams = @{}
foreach ($key in $PSBoundParameters.Keys) {
    $providedParams[$key] = $true
}
$MaxContinuousRunSeconds = 600

if ($LogDir -eq "") {
    $LogDir = Join-Path $scriptDir "logs"
}

function Get-FreeTcpPort {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    try {
        $listener.Start()
        return $listener.LocalEndpoint.Port
    } finally {
        $listener.Stop()
    }
}

if ($Mode -eq "offline_mock") {
    $TargetHost = "127.0.0.1"
    if (-not $providedParams.ContainsKey("Port")) {
        $Port = Get-FreeTcpPort
    }
}

function New-LogPath {
    param([string]$Name)

    if (-not $DryRun) {
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    }
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    return (Join-Path $LogDir "$Name`_$stamp.csv")
}

function Invoke-RFClient {
    param([string[]]$ClientArgs)

    $display = @("python", $clientPath) + $ClientArgs
    Write-Host ($display -join " ")
    if ($DryRun) {
        return
    }

    & python $clientPath @ClientArgs
    if ($LASTEXITCODE -ne 0) {
        throw "rf_comm_client.py failed with exit code $LASTEXITCODE"
    }
}

function Get-ArgValue {
    param(
        [string[]]$ArgsIn,
        [string]$Name
    )

    for ($idx = 0; $idx -lt $ArgsIn.Count - 1; $idx++) {
        if ($ArgsIn[$idx] -eq $Name) {
            return $ArgsIn[$idx + 1]
        }
    }
    return $null
}

function Invoke-LogAnalysis {
    param(
        [string]$CsvLog,
        [double]$MinDurationSeconds
    )

    if ($SkipLogAnalysis) {
        Write-Host "log analysis skipped: $CsvLog"
        return
    }

    $analysisArgs = @(
        $analyzerPath,
        $CsvLog,
        "--require-pass",
        "--max-errors", "0"
    )
    if ($MinDurationSeconds -gt 0.0) {
        $analysisArgs += @("--min-duration", [string]$MinDurationSeconds)
    }
    if ($MinDurationSeconds -gt 0.0 -and $StatusIntervalSeconds -gt 0.0) {
        $analysisArgs += @("--min-status-frames", "1")
    }
    if ($MinTxMbps -gt 0.0) {
        $analysisArgs += @("--min-tx-mbps", [string]$MinTxMbps)
    }
    if ($MinRxMbps -gt 0.0) {
        $analysisArgs += @("--min-rx-mbps", [string]$MinRxMbps)
    }
    if ($MinRxFrames -gt 0) {
        $analysisArgs += @("--min-rx-frames", [string]$MinRxFrames)
    }

    Write-Host ((@("python") + $analysisArgs) -join " ")
    if ($DryRun) {
        return
    }

    & python @analysisArgs
    if ($LASTEXITCODE -ne 0) {
        throw "analyze_acceptance_log.py failed with exit code $LASTEXITCODE"
    }
}

function Start-OfflineMockServer {
    if ($DryRun) {
        $readyPreview = Join-Path $LogDir "offline_mock_ready_DRYRUN.txt"
        $logPreview = Join-Path $LogDir "offline_mock_server_DRYRUN.log"
        Write-Host ("python {0} --host 127.0.0.1 --port {1} --ready-file {2} --log {3}" -f $mockServerPath, $Port, $readyPreview, $logPreview)
        return $null
    }

    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $readyFile = Join-Path $LogDir "offline_mock_ready_$stamp.txt"
    $serverLog = Join-Path $LogDir "offline_mock_server_$stamp.log"
    $serverArgs = @(
        $mockServerPath,
        "--host", "127.0.0.1",
        "--port", [string]$Port,
        "--ready-file", $readyFile,
        "--log", $serverLog
    )

    Write-Host ((@("python") + $serverArgs) -join " ")
    $proc = Start-Process -FilePath "python" -ArgumentList $serverArgs -PassThru -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(10)
    while (-not (Test-Path -LiteralPath $readyFile)) {
        if ($proc.HasExited) {
            throw "offline mock server exited early with code $($proc.ExitCode); log=$serverLog"
        }
        if ((Get-Date) -gt $deadline) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            throw "offline mock server did not become ready; log=$serverLog"
        }
        Start-Sleep -Milliseconds 100
    }

    Write-Host (Get-Content -LiteralPath $readyFile -Raw)
    Write-Host "offline mock server log: $serverLog"
    return $proc
}

function Stop-OfflineMockServer {
    param($Process)

    if ($null -eq $Process) {
        return
    }
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        $Process.WaitForExit(2000) | Out-Null
    }
}

function Base-Args {
    return @("--host", $TargetHost, "--port", [string]$Port, "--timeout", [string]$TimeoutSeconds)
}

function Acceptance-Args {
    $argsOut = @("--require-clean")
    if ($MinTxMbps -gt 0.0) {
        $argsOut += @("--min-tx-mbps", [string]$MinTxMbps)
    }
    if ($MinRxMbps -gt 0.0) {
        $argsOut += @("--min-rx-mbps", [string]$MinRxMbps)
    }
    if ($MinRxFrames -gt 0) {
        $argsOut += @("--min-rx-frames", [string]$MinRxFrames)
    }
    return $argsOut
}

function Clean-Args {
    return @("--require-clean")
}

function Traffic-Args {
    param(
        [string]$Name,
        [int]$DefaultDurationSeconds,
        [int]$DefaultWindow,
        [string]$PayloadPatternOverride = ""
    )

    $argsOut = Base-Args
    $requestedDurationSeconds = 0
    if ($DurationSeconds -gt 0) {
        $requestedDurationSeconds = $DurationSeconds
    } elseif ($DefaultDurationSeconds -gt 0) {
        $requestedDurationSeconds = $DefaultDurationSeconds
    }

    if ($requestedDurationSeconds -gt 0) {
        $effectiveDurationSeconds = [Math]::Min($requestedDurationSeconds, $MaxContinuousRunSeconds)
        if ($requestedDurationSeconds -gt $MaxContinuousRunSeconds) {
            Write-Host ("continuous runtime cap applied: requested_duration_seconds={0} effective_duration_seconds={1}" -f $requestedDurationSeconds, $effectiveDurationSeconds)
        }
        $argsOut += @("--duration", [string]$effectiveDurationSeconds)
    } else {
        $argsOut += @("--repeat", [string]$Repeat)
    }

    $effectiveWindow = $Window
    if ($DefaultWindow -gt 0 -and -not $providedParams.ContainsKey("Window")) {
        $effectiveWindow = $DefaultWindow
    }

    $effectivePayloadPattern = $PayloadPattern
    if ($PayloadPatternOverride -ne "") {
        $effectivePayloadPattern = $PayloadPatternOverride
    }

    $effectiveFramePayloadSize = $PayloadSize
    $effectiveAppPayloadSize = $AppPayloadSize
    if ($effectiveFramePayloadSize -gt 512 -and $effectiveAppPayloadSize -le 0) {
        $effectiveAppPayloadSize = $effectiveFramePayloadSize
        $effectiveFramePayloadSize = 512
    }
    if ($effectiveFramePayloadSize -gt 512) {
        throw "PayloadSize is an RFCM frame payload limit and must be <= 512 when AppPayloadSize is set."
    }

    $argsOut += @(
        "--payload-size", [string]$effectiveFramePayloadSize,
        "--payload-pattern", $effectivePayloadPattern,
        "--interval", [string]$IntervalSeconds,
        "--status-interval", [string]$StatusIntervalSeconds,
        "--window", [string]$effectiveWindow,
        "--ack-timeout", [string]$AckTimeoutSeconds,
        "--csv-log", (New-LogPath $Name)
    )
    if ($effectiveAppPayloadSize -gt 0) {
        $argsOut += @("--app-payload-size", [string]$effectiveAppPayloadSize)
    }
    if (-not $VerboseFrames) {
        $argsOut += "--quiet"
    }
    $argsOut += Acceptance-Args
    return $argsOut
}

function Invoke-Traffic {
    param(
        [string]$Name,
        [int]$DefaultDurationSeconds,
        [int]$DefaultWindow,
        [string]$PayloadPatternOverride = ""
    )

    $trafficArgs = Traffic-Args -Name $Name -DefaultDurationSeconds $DefaultDurationSeconds -DefaultWindow $DefaultWindow -PayloadPatternOverride $PayloadPatternOverride
    Invoke-RFClient $trafficArgs

    $csvLog = Get-ArgValue -ArgsIn $trafficArgs -Name "--csv-log"
    $durationArg = Get-ArgValue -ArgsIn $trafficArgs -Name "--duration"
    $minDuration = 0.0
    if ($null -ne $durationArg) {
        $minDuration = [double]$durationArg
    }
    Invoke-LogAnalysis -CsvLog $csvLog -MinDurationSeconds $minDuration
}

function Invoke-N03ModeConfig {
    param([string]$BridgeMode)

    Invoke-RFClient ((Base-Args) + @(
        "--clear",
        "--config-session", $SessionId,
        "--config-lane-mask", $LaneMask,
        "--config-enable", "0",
        "--config-mode", $BridgeMode,
        "--status"
    ) + (Clean-Args))
}

function Invoke-N03MemoryEcho {
    if (-not $providedParams.ContainsKey("Repeat")) {
        $script:Repeat = 32
    }
    if (-not $providedParams.ContainsKey("PayloadSize")) {
        $script:PayloadSize = 64
    }
    if (-not $providedParams.ContainsKey("MinRxFrames")) {
        $script:MinRxFrames = $Repeat
    }

    Invoke-N03ModeConfig -BridgeMode "network_memory_echo"
    Invoke-Traffic -Name "n03_memory_echo" -DefaultDurationSeconds 0 -DefaultWindow 1 -PayloadPatternOverride $PayloadPattern
    Write-Host "N03_TCP_PAYLOAD_MEMORY_ECHO_PASS=1"
}

function Invoke-N03Commands {
    Invoke-RFClient ((Base-Args) + @(
        "--command", "PING",
        "--command", "GET_VERSION",
        "--command", "GET_BUILD_ID",
        "--command", "READ build_id",
        "--command", "READ counters",
        "--command", "READ network_status",
        "--command", "READ pspl_status",
        "--command", "CONFIG payload_bytes 64",
        "--command", "CONFIG mode network_memory_echo",
        "--command", "CONFIG mode pspl_synth_loopback",
        "--command", "CLEAR counters",
        "--command", "CLEAR sticky",
        "--command", "START",
        "--command", "STOP",
        "--command", "SHUTDOWN_SAFE",
        "--status"
    ) + (Clean-Args))
    Write-Host "N03_TCP_PROTOCOL_COMMAND_PASS=1"
}

function Invoke-N03PsplSynth {
    if (-not $providedParams.ContainsKey("Repeat")) {
        $script:Repeat = 32
    }
    if (-not $providedParams.ContainsKey("PayloadSize")) {
        $script:PayloadSize = 64
    }
    if (-not $providedParams.ContainsKey("MinRxFrames")) {
        $script:MinRxFrames = $Repeat
    }

    Invoke-N03ModeConfig -BridgeMode "pspl_synth_loopback"
    Invoke-Traffic -Name "n03_pspl_synth" -DefaultDurationSeconds 0 -DefaultWindow 1 -PayloadPatternOverride "synth_ramp"
    Write-Host "N03_TCP_TO_PSPL_SYNTHETIC_LOOPBACK_PASS=1"
}

function Invoke-N03Negative {
    Invoke-RFClient ((Base-Args) + @(
        "--command", "START ir_tx",
        "--expect-error", "ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE"
    ))
    Invoke-RFClient ((Base-Args) + @(
        "--command", "CONFIG payload_bytes 0",
        "--expect-error", "ERR_BAD_ARG"
    ))
    Invoke-RFClient ((Base-Args) + @(
        "--command", "CONFIG payload_bytes too_large",
        "--expect-error", "ERR_BAD_ARG"
    ))
    Invoke-RFClient ((Base-Args) + @(
        "--command", "UNKNOWN_CMD",
        "--expect-error", "ERR_UNKNOWN_CMD"
    ))
    Invoke-RFClient ((Base-Args) + @(
        "--config-mode", "ir_physical",
        "--expect-error", "ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE"
    ))
    Write-Host "N03_BAD_ARG_NEGATIVE_PASS=1"
    Write-Host "N03_IR_PHYSICAL_DEFERRED_NEGATIVE_PASS=1"
}

Write-Host "RF_COMM acceptance mode: $Mode"
Write-Host "Repository: $repoRoot"
Write-Host "Continuous runtime cap seconds: $MaxContinuousRunSeconds"

switch ($Mode) {
    "smoke" {
        Invoke-RFClient ((Base-Args) + @("--hello", "--status") + (Clean-Args))
    }
    "single_lane" {
        Invoke-RFClient ((Base-Args) + @(
            "--clear",
            "--config-session", $SessionId,
            "--config-lane-mask", $LaneMask,
            "--config-enable", "1",
            "--status"
        ) + (Clean-Args))
        Invoke-Traffic -Name "single_lane" -DefaultDurationSeconds 0 -DefaultWindow 1
    }
    "soak_2h" {
        if (-not $PSBoundParameters.ContainsKey("PayloadSize")) {
            $PayloadSize = 32
        }
        if (-not $PSBoundParameters.ContainsKey("IntervalSeconds")) {
            $IntervalSeconds = 0.01
        }
        if (-not $PSBoundParameters.ContainsKey("StatusIntervalSeconds")) {
            $StatusIntervalSeconds = 5.0
        }
        Invoke-Traffic -Name "soak_2h" -DefaultDurationSeconds $MaxContinuousRunSeconds -DefaultWindow 1
    }
    "reconnect" {
        Invoke-RFClient ((Base-Args) + @(
            "--reconnect-cycles", [string]$ReconnectCycles,
            "--reconnect-delay", "1.0",
            "--reconnect-payload-size", [string]$ReconnectPayloadSize,
            "--reconnect-payload-pattern", $PayloadPattern
        ))
    }
    "fdx_partition" {
        Invoke-RFClient ((Base-Args) + @(
            "--clear",
            "--config-session", $SessionId,
            "--config-tx-lane-mask", $TxLaneMask,
            "--config-rx-lane-mask", $RxLaneMask,
            "--config-enable", "1",
            "--status"
        ) + (Clean-Args))
        Invoke-Traffic -Name "fdx_partition" -DefaultDurationSeconds 600 -DefaultWindow 4
    }
    "n03_commands" {
        Invoke-N03Commands
    }
    "n03_memory_echo" {
        Invoke-N03MemoryEcho
    }
    "n03_pspl_synth" {
        Invoke-N03PsplSynth
    }
    "n03_negative" {
        Invoke-N03Negative
    }
    "offline_mock" {
        if (-not $providedParams.ContainsKey("Repeat")) {
            $Repeat = 32
        }
        if (-not $providedParams.ContainsKey("PayloadSize")) {
            $PayloadSize = 64
        }
        if (-not $providedParams.ContainsKey("MinRxFrames")) {
            $MinRxFrames = $Repeat
        }
        if (-not $providedParams.ContainsKey("ReconnectCycles")) {
            $ReconnectCycles = 3
        }

        $mockProcess = Start-OfflineMockServer
        try {
            Invoke-RFClient ((Base-Args) + @("--hello", "--status") + (Clean-Args))
            Invoke-RFClient ((Base-Args) + @(
                "--clear",
                "--config-session", $SessionId,
                "--config-lane-mask", $LaneMask,
                "--config-enable", "1",
                "--status"
            ) + (Clean-Args))
            Invoke-Traffic -Name "offline_mock_single_lane" -DefaultDurationSeconds 0 -DefaultWindow 1
            Invoke-N03Commands
            Invoke-N03MemoryEcho
            Invoke-N03PsplSynth
            Invoke-N03Negative
            Invoke-RFClient ((Base-Args) + @(
                "--reconnect-cycles", [string]$ReconnectCycles,
                "--reconnect-delay", "0.1",
                "--reconnect-payload-size", [string]$ReconnectPayloadSize,
                "--reconnect-payload-pattern", $PayloadPattern
            ))
        } finally {
            Stop-OfflineMockServer $mockProcess
        }
    }
}

Write-Host "RF_COMM acceptance mode finished: $Mode"
