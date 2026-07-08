param(
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [int]$DurationSeconds = 15,
    [int]$ReadTimeoutMs = 200
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "ps_uart_boot_probe_$stamp.summary.txt"
$uartLog = Join-Path $reportsDir "ps_uart_boot_probe_$stamp.uart.log"

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Get-MatchCount {
    param(
        [string]$Text,
        [string]$Pattern
    )
    return ([regex]::Matches($Text, $Pattern, "IgnoreCase")).Count
}

"PS_UART_BOOT_PROBE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "DURATION_SECONDS=$DurationSeconds"
Write-SummaryLine "READ_TIMEOUT_MS=$ReadTimeoutMs"
Write-SummaryLine "SUMMARY_LOG=$summaryLog"
Write-SummaryLine "UART_LOG=$uartLog"

$ports = [System.IO.Ports.SerialPort]::GetPortNames()
Write-SummaryLine "SERIAL_PORTS=$($ports -join ',')"
$comPresent = $ports -contains $ComPort
Write-SummaryLine "COM_PORT_PRESENT=$([int]$comPresent)"
if (-not $comPresent) {
    Write-SummaryLine "UART_PROBE_VERDICT=FAIL_COM_PORT_MISSING"
    Write-SummaryLine "NO_UART_WRITE_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "PS_UART_BOOT_PROBE_END $(Get-Date -Format o)"
    exit 2
}

$serial = $null
$openOk = $false
$errorMessage = ""

try {
    $serial = New-Object System.IO.Ports.SerialPort $ComPort, $BaudRate, "None", 8, "One"
    $serial.ReadTimeout = $ReadTimeoutMs
    $serial.WriteTimeout = $ReadTimeoutMs
    $serial.DtrEnable = $false
    $serial.RtsEnable = $false
    $serial.Open()
    $openOk = $true
    Write-SummaryLine "UART_OPEN_OK=1"

    New-Item -ItemType File -Force -Path $uartLog | Out-Null
    Write-SummaryLine "UART_CAPTURE_BEGIN=$(Get-Date -Format o)"
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt $DurationSeconds) {
        try {
            $chunk = $serial.ReadExisting()
            if ($chunk.Length -gt 0) {
                Add-Content -LiteralPath $uartLog -Value $chunk -NoNewline -Encoding ascii
            }
        } catch {
            Write-SummaryLine "UART_READ_WARN=$($_.Exception.Message)"
        }
        Start-Sleep -Milliseconds 50
    }
    Write-SummaryLine "UART_CAPTURE_END=$(Get-Date -Format o)"
} catch {
    $errorMessage = $_.Exception.Message
    Write-SummaryLine "UART_OPEN_OK=0"
    Write-SummaryLine "UART_PROBE_ERROR=$errorMessage"
} finally {
    if ($serial -and $serial.IsOpen) {
        $serial.Close()
    }
}

if (-not $openOk) {
    Write-SummaryLine "UART_PROBE_VERDICT=FAIL_OPEN_PORT"
    Write-SummaryLine "NO_UART_WRITE_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"
    Write-SummaryLine "PS_UART_BOOT_PROBE_END $(Get-Date -Format o)"
    exit 3
}

$uartText = ""
if (Test-Path -LiteralPath $uartLog) {
    $uartText = Get-Content -LiteralPath $uartLog -Raw -ErrorAction SilentlyContinue
}
if ($null -eq $uartText) {
    $uartText = ""
}

$bridgeBanner = Get-MatchCount -Text $uartText -Pattern "RF_COMM PS lwIP bridge"
$pspsBanner = Get-MatchCount -Text $uartText -Pattern "RF_COMM PS-PS loopback experiment"
$boardIpCount = Get-MatchCount -Text $uartText -Pattern "Board IP:\s+\d+\.\d+\.\d+\.\d+"
$tcpListenCount = Get-MatchCount -Text $uartText -Pattern "RF TCP bridge listening on port\s+5001"
$dhcpFallbackCount = Get-MatchCount -Text $uartText -Pattern "DHCP timeout, using static fallback"
$pspsInitOkCount = Get-MatchCount -Text $uartText -Pattern "PSPS_INIT_OK"
$pspsStatsCount = Get-MatchCount -Text $uartText -Pattern "PSPS_(STATS|STAGE_SUMMARY|TDM_STATS|TDM_STAGE_SUMMARY|RX_ONLY_STATS|RX_ONLY_SUMMARY)"
$irInitFailCount = Get-MatchCount -Text $uartText -Pattern "IR hardware init failed"
$netifFailCount = Get-MatchCount -Text $uartText -Pattern "Error adding network interface"
$tcpStartFailCount = Get-MatchCount -Text $uartText -Pattern "TCP bridge start failed"

Write-SummaryLine "UART_LOG_BYTES=$((Get-Item -LiteralPath $uartLog).Length)"
Write-SummaryLine "MATCH_BRIDGE_BANNER=$bridgeBanner"
Write-SummaryLine "MATCH_PSPS_BANNER=$pspsBanner"
Write-SummaryLine "MATCH_BOARD_IP=$boardIpCount"
Write-SummaryLine "MATCH_TCP_LISTEN_5001=$tcpListenCount"
Write-SummaryLine "MATCH_DHCP_STATIC_FALLBACK=$dhcpFallbackCount"
Write-SummaryLine "MATCH_PSPS_INIT_OK=$pspsInitOkCount"
Write-SummaryLine "MATCH_PSPS_STATS=$pspsStatsCount"
Write-SummaryLine "MATCH_IR_INIT_FAIL=$irInitFailCount"
Write-SummaryLine "MATCH_NETIF_FAIL=$netifFailCount"
Write-SummaryLine "MATCH_TCP_START_FAIL=$tcpStartFailCount"

$ipMatches = [regex]::Matches($uartText, "Board IP:\s+(\d+\.\d+\.\d+\.\d+)", "IgnoreCase")
foreach ($m in $ipMatches) {
    Write-SummaryLine "BOARD_IP_SEEN=$($m.Groups[1].Value)"
}

$interesting = $uartText -split "`r?`n" | Where-Object {
    $_ -match "RF_COMM|Board IP|Netmask|Gateway|DHCP|RF TCP bridge|PSPS_|IR hardware init failed|TCP bridge start failed|Error adding network interface"
}
foreach ($line in ($interesting | Select-Object -Last 40)) {
    Write-SummaryLine "UART_MATCH=$line"
}

if ($bridgeBanner -gt 0 -and $boardIpCount -gt 0 -and $tcpListenCount -gt 0) {
    Write-SummaryLine "UART_PROBE_VERDICT=PASS_PS_LWIP_BRIDGE_READY"
} elseif ($bridgeBanner -gt 0) {
    Write-SummaryLine "UART_PROBE_VERDICT=PARTIAL_PS_LWIP_BRIDGE_TEXT"
} elseif ($pspsBanner -gt 0 -or $pspsInitOkCount -gt 0 -or $pspsStatsCount -gt 0) {
    Write-SummaryLine "UART_PROBE_VERDICT=PASS_PSPS_LOOPBACK_RUNNING"
} elseif ($irInitFailCount -gt 0 -or $netifFailCount -gt 0 -or $tcpStartFailCount -gt 0) {
    Write-SummaryLine "UART_PROBE_VERDICT=FAIL_BOOT_ERROR_TEXT"
} elseif ($uartText.Length -gt 0) {
    Write-SummaryLine "UART_PROBE_VERDICT=INCONCLUSIVE_OTHER_UART_TEXT"
} else {
    Write-SummaryLine "UART_PROBE_VERDICT=INCONCLUSIVE_NO_UART_TEXT"
}

Write-SummaryLine "NO_UART_WRITE_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "PS_UART_BOOT_PROBE_END $(Get-Date -Format o)"
exit 0
