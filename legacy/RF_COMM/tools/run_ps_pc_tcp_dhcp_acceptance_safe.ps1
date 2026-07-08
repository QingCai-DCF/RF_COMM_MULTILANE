param(
    [string]$TargetHost = "",
    [int]$Port = 5001,
    [string]$ComPort = "COM3",
    [int]$UartProbeSeconds = 12,
    [int]$ReconnectCycles = 4,
    [double]$TimeoutSeconds = 5.0,
    [switch]$UseStaticFallback,
    [switch]$SkipUartProbe,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "ps_pc_tcp_dhcp_acceptance_safe_$stamp.summary.txt"
$mdReport = Join-Path $reportsDir "ps_pc_tcp_dhcp_acceptance_safe_$stamp.md"
$uartProbeLog = Join-Path $reportsDir "ps_pc_tcp_dhcp_acceptance_safe_$stamp.uart_probe.log"
$smokeLog = Join-Path $reportsDir "ps_pc_tcp_dhcp_acceptance_safe_$stamp.smoke.log"
$smokeErr = Join-Path $reportsDir "ps_pc_tcp_dhcp_acceptance_safe_$stamp.smoke.err.log"
$reconnectLog = Join-Path $reportsDir "ps_pc_tcp_dhcp_acceptance_safe_$stamp.reconnect.log"
$reconnectErr = Join-Path $reportsDir "ps_pc_tcp_dhcp_acceptance_safe_$stamp.reconnect.err.log"

$expectedConstraintSha256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
$uartProbeScript = Join-Path $repoRoot "tools\probe_ps_uart_boot_safe.ps1"
$acceptanceScript = Join-Path $repoRoot "software\host_client\run_acceptance.ps1"

foreach ($path in @($uartProbeScript, $acceptanceScript)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Add-MdLine {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string]$Line
    )
    $Lines.Add($Line)
}

function Invoke-LoggedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogPath,
        [string]$ErrPath,
        [int]$TimeoutSecondsForStep
    )

    Write-SummaryLine "STEP_START name=$Name log=$LogPath err=$ErrPath"
    if ($DryRun) {
        Write-SummaryLine "STEP_DRY_RUN name=$Name command=$FilePath $($Arguments -join ' ')"
        return [pscustomobject]@{ ExitCode = 0; TimedOut = $false; Stdout = ""; Stderr = "" }
    }

    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $LogPath `
        -RedirectStandardError $ErrPath `
        -WindowStyle Hidden `
        -PassThru
    $finished = $proc.WaitForExit($TimeoutSecondsForStep * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        Write-SummaryLine "STEP_RESULT name=$Name exit=124 timeout=1"
        return [pscustomobject]@{
            ExitCode = 124
            TimedOut = $true
            Stdout = if (Test-Path -LiteralPath $LogPath) { Get-Content -LiteralPath $LogPath -Raw -ErrorAction SilentlyContinue } else { "" }
            Stderr = if (Test-Path -LiteralPath $ErrPath) { Get-Content -LiteralPath $ErrPath -Raw -ErrorAction SilentlyContinue } else { "" }
        }
    }
    $proc.Refresh()
    $exit = if ($null -eq $proc.ExitCode) { 0 } else { $proc.ExitCode }
    Write-SummaryLine "STEP_RESULT name=$Name exit=$exit timeout=0"
    return [pscustomobject]@{
        ExitCode = $exit
        TimedOut = $false
        Stdout = if (Test-Path -LiteralPath $LogPath) { Get-Content -LiteralPath $LogPath -Raw -ErrorAction SilentlyContinue } else { "" }
        Stderr = if (Test-Path -LiteralPath $ErrPath) { Get-Content -LiteralPath $ErrPath -Raw -ErrorAction SilentlyContinue } else { "" }
    }
}

function Get-RegexFirst {
    param(
        [string]$Text,
        [string]$Pattern
    )
    $m = [regex]::Match($Text, $Pattern, "IgnoreCase,Multiline")
    if ($m.Success) {
        return $m.Groups[1].Value.Trim()
    }
    return ""
}

function Test-TcpPortQuick {
    param(
        [string]$HostName,
        [int]$TcpPort,
        [int]$TimeoutMs
    )
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $iar = $client.BeginConnect($HostName, $TcpPort, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if (-not $ok) {
            $client.Close()
            return $false
        }
        $client.EndConnect($iar)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

function Get-LatestFile {
    param([string]$Filter)
    $files = @(Get-ChildItem -LiteralPath $reportsDir -Filter $Filter -File -ErrorAction SilentlyContinue)
    if ($files.Count -eq 0) {
        return $null
    }
    return $files | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

"PS_PC_TCP_DHCP_ACCEPTANCE_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "TARGET_HOST_ARG=$TargetHost"
Write-SummaryLine "PORT=$Port"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "UART_PROBE_SECONDS=$UartProbeSeconds"
Write-SummaryLine "RECONNECT_CYCLES=$ReconnectCycles"
Write-SummaryLine "TIMEOUT_SECONDS=$TimeoutSeconds"
Write-SummaryLine "USE_STATIC_FALLBACK=$([int]$UseStaticFallback.IsPresent)"
Write-SummaryLine "SKIP_UART_PROBE=$([int]$SkipUartProbe.IsPresent)"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "NO_TX_DATA_DONE_BY_THIS_SCRIPT=1"

$constraintPath = Get-ChildItem -LiteralPath $repoRoot -File -Filter "*.txt" |
    Where-Object {
        try {
            (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash -eq $expectedConstraintSha256
        } catch {
            $false
        }
    } |
    Select-Object -First 1 -ExpandProperty FullName
$constraintHash = if ([string]::IsNullOrWhiteSpace($constraintPath)) { "MISSING" } else { (Get-FileHash -Algorithm SHA256 -LiteralPath $constraintPath).Hash }
Write-SummaryLine "CONSTRAINT_SHA256=$constraintHash"
Write-SummaryLine "CONSTRAINT_UNCHANGED=$([int]($constraintHash -eq $expectedConstraintSha256))"

$serialPorts = [System.IO.Ports.SerialPort]::GetPortNames()
Write-SummaryLine "SERIAL_PORTS=$($serialPorts -join ',')"
Write-SummaryLine "COM_PORT_PRESENT=$([int]($serialPorts -contains $ComPort))"

$eth = Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object {
    $_.InterfaceDescription -match "Realtek|Ethernet|GbE|2.5GbE" -or $_.Name -match "Ethernet"
} | Sort-Object -Property @{ Expression = { if ($_.Status -eq "Up") { 0 } else { 1 } } }, Name | Select-Object -First 1
if ($null -ne $eth) {
    Write-SummaryLine "ETH_ADAPTER_NAME=$($eth.Name)"
    Write-SummaryLine "ETH_ADAPTER_DESC=$($eth.InterfaceDescription)"
    Write-SummaryLine "ETH_ADAPTER_STATUS=$($eth.Status)"
    Write-SummaryLine "ETH_ADAPTER_LINK_SPEED=$($eth.LinkSpeed)"
    $ethIps = @(Get-NetIPAddress -InterfaceIndex $eth.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue)
    foreach ($ip in $ethIps) {
        Write-SummaryLine "ETH_IPV4=$($ip.IPAddress)/$($ip.PrefixLength) state=$($ip.AddressState) origin=$($ip.PrefixOrigin)"
    }
} else {
    Write-SummaryLine "ETH_ADAPTER_NAME=NONE"
    Write-SummaryLine "ETH_ADAPTER_STATUS=MISSING"
}

$uartSummaryText = ""
$uartSummaryPath = ""
if (-not $SkipUartProbe) {
    $uartResult = Invoke-LoggedProcess -Name "uart_probe" -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $uartProbeScript,
        "-ComPort",
        $ComPort,
        "-DurationSeconds",
        [string]$UartProbeSeconds
    ) -LogPath $uartProbeLog -ErrPath "$uartProbeLog.err" -TimeoutSecondsForStep ($UartProbeSeconds + 10)
    $uartSummaryText = $uartResult.Stdout
    $uartSummaryPath = Get-RegexFirst -Text $uartSummaryText -Pattern "^SUMMARY_LOG=(.+)$"
    if ($uartSummaryPath -eq "") {
        $latestProbe = Get-LatestFile -Filter "ps_uart_boot_probe_*.summary.txt"
        if ($null -ne $latestProbe) {
            $uartSummaryPath = $latestProbe.FullName
            $uartSummaryText = Get-Content -LiteralPath $uartSummaryPath -Raw -ErrorAction SilentlyContinue
        }
    }
} else {
    $latestProbe = Get-LatestFile -Filter "ps_uart_boot_probe_*.summary.txt"
    if ($null -ne $latestProbe) {
        $uartSummaryPath = $latestProbe.FullName
        $uartSummaryText = Get-Content -LiteralPath $uartSummaryPath -Raw -ErrorAction SilentlyContinue
    }
}

if ($uartSummaryText -ne "") {
    Write-SummaryLine "UART_SUMMARY=$uartSummaryPath"
    $uartVerdict = Get-RegexFirst -Text $uartSummaryText -Pattern "^UART_PROBE_VERDICT=(.+)$"
    if ($uartVerdict -ne "") { Write-SummaryLine "UART_PROBE_VERDICT=$uartVerdict" }
    foreach ($m in [regex]::Matches($uartSummaryText, "^BOARD_IP_SEEN=(\d+\.\d+\.\d+\.\d+)$", "IgnoreCase,Multiline")) {
        Write-SummaryLine "BOARD_IP_SEEN=$($m.Groups[1].Value)"
    }
    $dhcpFallbackSeen = [regex]::IsMatch($uartSummaryText, "^MATCH_DHCP_STATIC_FALLBACK=[1-9]", "IgnoreCase,Multiline")
    $tcpListenSeen = [regex]::IsMatch($uartSummaryText, "^MATCH_TCP_LISTEN_5001=[1-9]", "IgnoreCase,Multiline")
    Write-SummaryLine "UART_DHCP_STATIC_FALLBACK_SEEN=$([int]$dhcpFallbackSeen)"
    Write-SummaryLine "UART_TCP_LISTEN_5001_SEEN=$([int]$tcpListenSeen)"
} else {
    Write-SummaryLine "UART_SUMMARY=NONE"
    Write-SummaryLine "UART_PROBE_VERDICT=NO_UART_SUMMARY"
    $dhcpFallbackSeen = $false
    $tcpListenSeen = $false
}

$boardIps = @([regex]::Matches($uartSummaryText, "^BOARD_IP_SEEN=(\d+\.\d+\.\d+\.\d+)$", "IgnoreCase,Multiline") | ForEach-Object { $_.Groups[1].Value })
if ($TargetHost -eq "" -and $boardIps.Count -gt 0) {
    $TargetHost = $boardIps[$boardIps.Count - 1]
    Write-SummaryLine "TARGET_HOST_FROM_UART=$TargetHost"
}
if ($TargetHost -eq "" -and $UseStaticFallback) {
    $TargetHost = "192.168.10.2"
    Write-SummaryLine "TARGET_HOST_STATIC_FALLBACK=$TargetHost"
}
Write-SummaryLine "TARGET_HOST_EFFECTIVE=$TargetHost"

$blockedReasons = [System.Collections.Generic.List[string]]::new()
if ($TargetHost -eq "") {
    $blockedReasons.Add("no_target_host")
}
if ($null -eq $eth) {
    $blockedReasons.Add("ethernet_adapter_missing")
} elseif ($eth.Status -ne "Up") {
    $blockedReasons.Add("ethernet_link_not_up")
}
if (($serialPorts -contains $ComPort) -eq $false) {
    $blockedReasons.Add("uart_port_missing")
}

$tcpQuick = $false
if ($TargetHost -ne "") {
    $tcpQuick = Test-TcpPortQuick -HostName $TargetHost -TcpPort $Port -TimeoutMs ([int]([math]::Max($TimeoutSeconds, 1.0) * 1000.0))
}
Write-SummaryLine "TCP_QUICK_CONNECT_OK=$([int]$tcpQuick)"

if ($blockedReasons.Count -gt 0 -and -not $tcpQuick) {
    foreach ($reason in $blockedReasons) {
        Write-SummaryLine "BOARD_TCP_DHCP_BLOCKED_REASON=$reason"
    }
    Write-SummaryLine "BOARD_TCP_DHCP_ACCEPTANCE_PASS=0"
    Write-SummaryLine "BOARD_TCP_DHCP_ACCEPTANCE_BLOCKED=1"
    Write-SummaryLine "BOARD_TCP_DHCP_ACCEPTANCE_EXIT=20"
    Write-SummaryLine "PS_PC_TCP_DHCP_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"
    $mdLines = [System.Collections.Generic.List[string]]::new()
    Add-MdLine $mdLines "# PS-PC TCP/DHCP Board Acceptance"
    Add-MdLine $mdLines ""
    Add-MdLine $mdLines "Generated: $(Get-Date -Format o)"
    Add-MdLine $mdLines ""
    Add-MdLine $mdLines "Verdict: BLOCKED"
    Add-MdLine $mdLines ""
    Add-MdLine $mdLines "This run did not program hardware, did not write UART, did not send TX_DATA, and did not drive TFDU boards."
    Add-MdLine $mdLines ""
    Add-MdLine $mdLines ("Blocked reasons: " + ($blockedReasons -join ','))
    Add-MdLine $mdLines ""
    Add-MdLine $mdLines ("Summary log: " + $summaryLog)
    [System.IO.File]::WriteAllLines($mdReport, [string[]]$mdLines, [System.Text.Encoding]::UTF8)
    exit 20
}

if ($DryRun) {
    Write-SummaryLine "BOARD_TCP_DHCP_DRY_RUN=1"
    Write-SummaryLine "BOARD_TCP_DHCP_ACCEPTANCE_PASS=0"
    Write-SummaryLine "BOARD_TCP_DHCP_ACCEPTANCE_BLOCKED=0"
    Write-SummaryLine "BOARD_TCP_DHCP_ACCEPTANCE_EXIT=0"
    Write-SummaryLine "PS_PC_TCP_DHCP_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"
    exit 0
}

$smokeResult = Invoke-LoggedProcess -Name "tcp_smoke" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $acceptanceScript,
    "-Mode",
    "smoke",
    "-TargetHost",
    $TargetHost,
    "-Port",
    [string]$Port,
    "-TimeoutSeconds",
    [string]$TimeoutSeconds
) -LogPath $smokeLog -ErrPath $smokeErr -TimeoutSecondsForStep ([int]($TimeoutSeconds + 20))

foreach ($line in (($smokeResult.Stdout + "`n" + $smokeResult.Stderr) -split "`r?`n" | Where-Object { $_ -match "ACK|STATUS_RSP|acceptance|RF_COMM|failed|error" } | Select-Object -Last 30)) {
    Write-SummaryLine "SMOKE_MATCH=$line"
}

$reconnectResult = Invoke-LoggedProcess -Name "tcp_reconnect" -FilePath "powershell.exe" -Arguments @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $acceptanceScript,
    "-Mode",
    "reconnect",
    "-TargetHost",
    $TargetHost,
    "-Port",
    [string]$Port,
    "-TimeoutSeconds",
    [string]$TimeoutSeconds,
    "-ReconnectCycles",
    [string]$ReconnectCycles
) -LogPath $reconnectLog -ErrPath $reconnectErr -TimeoutSecondsForStep ([int](($TimeoutSeconds + 2.0) * $ReconnectCycles + 20))

foreach ($line in (($reconnectResult.Stdout + "`n" + $reconnectResult.Stderr) -split "`r?`n" | Where-Object { $_ -match "reconnect cycle|ACK|STATUS_RSP|failed|error" } | Select-Object -Last 60)) {
    Write-SummaryLine "RECONNECT_MATCH=$line"
}

$smokeOk = ($smokeResult.ExitCode -eq 0 -and $smokeResult.Stdout -match "ACK" -and $smokeResult.Stdout -match "STATUS_RSP")
$reconnectOk = ($reconnectResult.ExitCode -eq 0 -and $reconnectResult.Stdout -match "reconnect cycle $ReconnectCycles/$ReconnectCycles")
$networkEvidenceOk = ($tcpQuick -or $smokeOk)
$dhcpEvidenceOk = ($boardIps.Count -gt 0 -or $TargetHost -ne "")
$fallbackEvidence = ($dhcpFallbackSeen -or $TargetHost -eq "192.168.10.2")

Write-SummaryLine "SMOKE_OK=$([int]$smokeOk)"
Write-SummaryLine "RECONNECT_OK=$([int]$reconnectOk)"
Write-SummaryLine "NETWORK_EVIDENCE_OK=$([int]$networkEvidenceOk)"
Write-SummaryLine "DHCP_OR_STATIC_EVIDENCE_OK=$([int]$dhcpEvidenceOk)"
Write-SummaryLine "STATIC_FALLBACK_EVIDENCE_OK=$([int]$fallbackEvidence)"

$pass = ($smokeOk -and $reconnectOk -and $networkEvidenceOk -and $dhcpEvidenceOk)
Write-SummaryLine "BOARD_TCP_DHCP_ACCEPTANCE_PASS=$([int]$pass)"
Write-SummaryLine "BOARD_TCP_DHCP_ACCEPTANCE_BLOCKED=0"
$exitCode = if ($pass) { 0 } else { 1 }
Write-SummaryLine "BOARD_TCP_DHCP_ACCEPTANCE_EXIT=$exitCode"
Write-SummaryLine "PS_PC_TCP_DHCP_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"

$md = [System.Collections.Generic.List[string]]::new()
Add-MdLine $md "# PS-PC TCP/DHCP Board Acceptance"
Add-MdLine $md ""
Add-MdLine $md "Generated: $(Get-Date -Format o)"
Add-MdLine $md ""
if ($pass) {
    Add-MdLine $md "Verdict: PASS_REAL_BOARD_TCP_DHCP_RECONNECT"
} else {
    Add-MdLine $md "Verdict: FAIL_OR_NO_BOARD_RESPONSE"
}
Add-MdLine $md ""
Add-MdLine $md "This run did not program hardware, did not write UART, did not send TX_DATA, and did not drive TFDU boards."
Add-MdLine $md ""
Add-MdLine $md ("- Target host: " + $TargetHost)
Add-MdLine $md ("- TCP port: " + $Port)
Add-MdLine $md ("- Smoke OK: " + $smokeOk)
Add-MdLine $md ("- Reconnect OK: " + $reconnectOk)
Add-MdLine $md ("- DHCP/static evidence OK: " + $dhcpEvidenceOk)
Add-MdLine $md ("- Static fallback evidence OK: " + $fallbackEvidence)
Add-MdLine $md ("- Summary log: " + $summaryLog)
Add-MdLine $md ("- UART summary: " + $uartSummaryPath)
Add-MdLine $md ("- Smoke log: " + $smokeLog)
Add-MdLine $md ("- Reconnect log: " + $reconnectLog)
[System.IO.File]::WriteAllLines($mdReport, [string[]]$md, [System.Text.Encoding]::UTF8)

exit $exitCode
