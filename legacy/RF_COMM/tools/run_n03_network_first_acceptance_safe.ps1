[CmdletBinding()]
param(
    [string]$TargetHost = "192.168.10.2",
    [int]$Port = 5001,
    [string]$ComPort = "COM3",
    [int]$UartProbeSeconds = 20,
    [int]$ReconnectCycles = 20,
    [double]$TimeoutSeconds = 5.0,
    [int]$MatrixRepeat = 100,
    [int]$QuickRepeat = 10,
    [int]$SustainedSeconds = 60,
    [int]$LongSeconds = 300,
    [switch]$SkipUartProbe,
    [switch]$SkipStaticDirectPreflight,
    [switch]$UseLatestTargetHint,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "n03_network_first_acceptance_safe_$stamp.summary.txt"
$mdReport = Join-Path $reportsDir "n03_network_first_acceptance_safe_$stamp.md"
$matrixCsv = Join-Path $reportsDir "n03_network_first_acceptance_safe_$stamp.matrix.csv"
$logDir = Join-Path $reportsDir "n03_network_first_acceptance_$stamp"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$expectedConstraintSha256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
$acceptanceScript = Join-Path $repoRoot "software\host_client\run_acceptance.ps1"
$uartProbeScript = Join-Path $repoRoot "tools\probe_ps_uart_boot_safe.ps1"
$staticDirectPreflightScript = Join-Path $repoRoot "tools\setup_n03_static_direct_network_safe.ps1"
$maxContinuousRunSeconds = 600
$framePayloadBytes = 512

foreach ($path in @($acceptanceScript, $uartProbeScript, $staticDirectPreflightScript)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding utf8
}

function Add-MatrixRow {
    param(
        [string]$Item,
        [string]$Status,
        [string]$Evidence,
        [string]$Note
    )
    [pscustomobject]@{
        item = $Item
        status = $Status
        evidence = $Evidence
        note = $Note
    } | Export-Csv -LiteralPath $matrixCsv -NoTypeInformation -Append -Encoding UTF8
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
    Write-SummaryLine "STEP_COMMAND name=$Name $FilePath $($Arguments -join ' ')"
    if ($DryRun) {
        Write-SummaryLine "STEP_DRY_RUN name=$Name"
        return [pscustomobject]@{ ExitCode = 0; TimedOut = $false; DryRun = $true; Stdout = ""; Stderr = "" }
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
            DryRun = $false
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
        DryRun = $false
        Stdout = if (Test-Path -LiteralPath $LogPath) { Get-Content -LiteralPath $LogPath -Raw -ErrorAction SilentlyContinue } else { "" }
        Stderr = if (Test-Path -LiteralPath $ErrPath) { Get-Content -LiteralPath $ErrPath -Raw -ErrorAction SilentlyContinue } else { "" }
    }
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

function Get-LatestReport {
    param([string]$Pattern)
    $matches = @(Get-ChildItem -LiteralPath $reportsDir -Filter $Pattern -File -ErrorAction SilentlyContinue |
        Sort-Object -Property LastWriteTime -Descending)
    if ($matches.Count -eq 0) { return $null }
    return $matches[0].FullName
}

function Get-LatestUartBoardIp {
    $summaryPath = Get-LatestReport -Pattern "ps_uart_boot_probe_*.summary.txt"
    if ([string]::IsNullOrWhiteSpace($summaryPath)) { return "" }
    $text = Get-Content -LiteralPath $summaryPath -Raw -ErrorAction SilentlyContinue
    $matches = @([regex]::Matches($text, "^BOARD_IP_SEEN=(\d+\.\d+\.\d+\.\d+)$", "IgnoreCase,Multiline"))
    if ($matches.Count -eq 0) { return "" }
    return $matches[$matches.Count - 1].Groups[1].Value
}

function Get-ExternalPreconditionTcpCandidate {
    $jsonPath = Join-Path $reportsDir "external_preconditions_current.json"
    if (-not (Test-Path -LiteralPath $jsonPath -PathType Leaf)) { return "" }
    try {
        $payload = Get-Content -LiteralPath $jsonPath -Raw | ConvertFrom-Json
        $candidates = @($payload.local_tcp_discovery.candidates)
        if ($candidates.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace([string]$candidates[0])) {
            return [string]$candidates[0]
        }
    } catch {
        return ""
    }
    return ""
}

function Resolve-TargetHostHint {
    $uartIp = Get-LatestUartBoardIp
    if (-not [string]::IsNullOrWhiteSpace($uartIp)) {
        return [pscustomobject]@{ Host = $uartIp; Source = "latest_uart_board_ip" }
    }
    $tcpCandidate = Get-ExternalPreconditionTcpCandidate
    if (-not [string]::IsNullOrWhiteSpace($tcpCandidate)) {
        return [pscustomobject]@{ Host = $tcpCandidate; Source = "external_local_tcp_5001_candidate" }
    }
    return [pscustomobject]@{ Host = ""; Source = "none" }
}

function Invoke-Acceptance {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [int]$TimeoutSecondsForStep
    )
    $outLog = Join-Path $logDir "$Name.out.log"
    $errLog = Join-Path $logDir "$Name.err.log"
    $args = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $acceptanceScript
    ) + $Arguments + @("-LogDir", $logDir)
    $result = Invoke-LoggedProcess -Name $Name -FilePath "powershell.exe" -Arguments $args -LogPath $outLog -ErrPath $errLog -TimeoutSecondsForStep $TimeoutSecondsForStep
    $combined = $result.Stdout + "`n" + $result.Stderr
    foreach ($line in ($combined -split "`r?`n" | Where-Object { $_ -match "N03_|acceptance PASS|acceptance FAIL|log_acceptance|summary|ERROR|failed" } | Select-Object -Last 80)) {
        Write-SummaryLine "STEP_MATCH name=$Name $line"
    }
    return $result
}

function Step-Status {
    param($Result)
    if ($Result.PSObject.Properties.Name -contains "DryRun" -and $Result.DryRun) { return "DRY_RUN" }
    if ($Result.ExitCode -eq 0) { return "PASS" }
    if ($Result.ExitCode -eq 20) { return "BLOCKED" }
    if ($Result.TimedOut) { return "TIMEOUT" }
    return "FAIL"
}

function Get-MarkerValues {
    param(
        [string]$Text,
        [string]$Key
    )
    $values = [System.Collections.Generic.List[string]]::new()
    foreach ($line in ($Text -split "`r?`n")) {
        if ($line.StartsWith("$Key=")) {
            $values.Add($line.Substring($Key.Length + 1).Trim())
        }
    }
    return @($values)
}

function Test-MarkerPositive {
    param(
        [string]$Text,
        [string]$Key
    )
    foreach ($value in (Get-MarkerValues -Text $Text -Key $Key)) {
        [int]$parsed = 0
        if ([int]::TryParse($value, [ref]$parsed)) {
            if ($parsed -gt 0) {
                return $true
            }
        } elseif ($value.ToLowerInvariant() -in @("true", "yes", "pass")) {
            return $true
        }
    }
    return $false
}

function Write-N03IncompletePassMarkers {
    Write-SummaryLine "N03_STATIC_DIRECT_TCP_PASS=0"
    Write-SummaryLine "N03_TCP_PROTOCOL_COMMAND_PASS=0"
    Write-SummaryLine "N03_TCP_PAYLOAD_MEMORY_ECHO_PASS=0"
    Write-SummaryLine "N03_TCP_TO_PSPL_SYNTHETIC_LOOPBACK_PASS=0"
    Write-SummaryLine "N03_IR_PHYSICAL_DEFERRED_NEGATIVE_PASS=0"
    Write-SummaryLine "N03_LINK_RECOVERY_PASS=0"
    Write-SummaryLine "N03_DHCP_FALLBACK_TCP_HELLO_PASS=0"
    Write-SummaryLine "N03_DHCP_FALLBACK_MEMORY_ECHO_PASS=0"
    Write-SummaryLine "N03_DHCP_FALLBACK_PASS=0"
    Write-SummaryLine "N03_PC_HOSTED_DHCP_LEASE_PASS=0"
}

function Invoke-PayloadCase {
    param(
        [string]$Mode,
        [int]$PayloadBytes,
        [int]$Count,
        [string]$NamePrefix,
        [string]$Pattern
    )
    $frameSize = [Math]::Min($PayloadBytes, $framePayloadBytes)
    $framesPerPayload = [int][Math]::Ceiling([double]$PayloadBytes / [double]$frameSize)
    $minRxFrames = [Math]::Max(1, $framesPerPayload * $Count)
    $name = "{0}_{1}_{2}" -f $NamePrefix, $Mode, $PayloadBytes
    $args = @(
        "-Mode", $Mode,
        "-TargetHost", $TargetHost,
        "-Port", [string]$Port,
        "-TimeoutSeconds", [string]$TimeoutSeconds,
        "-Repeat", [string]$Count,
        "-PayloadSize", [string]$frameSize,
        "-AppPayloadSize", [string]$PayloadBytes,
        "-PayloadPattern", $Pattern,
        "-MinRxFrames", [string]$minRxFrames
    )
    $timeout = [int]([Math]::Max(60.0, ($TimeoutSeconds + 2.0) * $minRxFrames + 30.0))
    return Invoke-Acceptance -Name $name -Arguments $args -TimeoutSecondsForStep $timeout
}

function Invoke-DurationCase {
    param(
        [string]$Mode,
        [int]$PayloadBytes,
        [int]$Seconds,
        [string]$NamePrefix,
        [string]$Pattern
    )
    $effectiveSeconds = [Math]::Min($Seconds, $maxContinuousRunSeconds)
    $frameSize = [Math]::Min($PayloadBytes, $framePayloadBytes)
    $name = "{0}_{1}_{2}_{3}s" -f $NamePrefix, $Mode, $PayloadBytes, $effectiveSeconds
    $args = @(
        "-Mode", $Mode,
        "-TargetHost", $TargetHost,
        "-Port", [string]$Port,
        "-TimeoutSeconds", [string]$TimeoutSeconds,
        "-DurationSeconds", [string]$effectiveSeconds,
        "-PayloadSize", [string]$frameSize,
        "-AppPayloadSize", [string]$PayloadBytes,
        "-PayloadPattern", $Pattern,
        "-StatusIntervalSeconds", "5"
    )
    $timeout = [int]($effectiveSeconds + 120)
    return Invoke-Acceptance -Name $name -Arguments $args -TimeoutSecondsForStep $timeout
}

$originalTargetHost = $TargetHost
$targetHint = [pscustomobject]@{ Host = ""; Source = "disabled" }
if ($UseLatestTargetHint) {
    $targetHint = Resolve-TargetHostHint
    if (-not [string]::IsNullOrWhiteSpace($targetHint.Host)) {
        $TargetHost = [string]$targetHint.Host
    }
}

"N03_NETWORK_FIRST_ACCEPTANCE_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding utf8
"item,status,evidence,note" | Out-File -LiteralPath $matrixCsv -Encoding UTF8
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "TARGET_HOST_ORIGINAL=$originalTargetHost"
Write-SummaryLine "USE_LATEST_TARGET_HINT=$([int]$UseLatestTargetHint.IsPresent)"
Write-SummaryLine "TARGET_HOST_HINT_SOURCE=$($targetHint.Source)"
Write-SummaryLine "TARGET_HOST_HINT_VALUE=$($targetHint.Host)"
Write-SummaryLine "TARGET_HOST=$TargetHost"
Write-SummaryLine "PORT=$Port"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "UART_PROBE_SECONDS=$UartProbeSeconds"
Write-SummaryLine "RECONNECT_CYCLES=$ReconnectCycles"
Write-SummaryLine "TIMEOUT_SECONDS=$TimeoutSeconds"
Write-SummaryLine "MATRIX_REPEAT=$MatrixRepeat"
Write-SummaryLine "QUICK_REPEAT=$QuickRepeat"
Write-SummaryLine "SUSTAINED_SECONDS=$SustainedSeconds"
Write-SummaryLine "LONG_SECONDS=$LongSeconds"
Write-SummaryLine "SKIP_STATIC_DIRECT_PREFLIGHT=$([int]$SkipStaticDirectPreflight.IsPresent)"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "NO_UART_WRITE_UNLESS_READONLY_PROBE=1"
Write-SummaryLine "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"
Write-SummaryLine "NO_IR_PHYSICAL_PASS_CLAIM=1"
Write-SummaryLine "NO_2LANE_PASS_CLAIM=1"

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
Add-MatrixRow -Item "constraint" -Status $(if ($constraintHash -eq $expectedConstraintSha256) { "PASS" } else { "FAIL" }) -Evidence $constraintHash -Note "Project hard constraint must not change."
if ($constraintHash -ne $expectedConstraintSha256) {
    Write-N03IncompletePassMarkers
    Write-SummaryLine "N03_REAL_BOARD_ACCEPTANCE_PASS=0"
    Write-SummaryLine "N03_REAL_BOARD_ACCEPTANCE_BLOCKED=1"
    Write-SummaryLine "N03_BLOCKED_REASON=project_constraint_hash_mismatch"
    Write-SummaryLine "N03_NETWORK_FIRST_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"
    exit 2
}

if (-not $SkipStaticDirectPreflight) {
    $staticLog = Join-Path $logDir "static_direct_preflight.out.log"
    $staticErr = Join-Path $logDir "static_direct_preflight.err.log"
    $staticResult = Invoke-LoggedProcess -Name "static_direct_preflight_readonly" -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $staticDirectPreflightScript,
        "-TargetHost",
        $TargetHost,
        "-Port",
        [string]$Port,
        "-TimeoutMs",
        [string]([Math]::Max(1000, [int]([Math]::Max($TimeoutSeconds, 1.0) * 1000.0)))
    ) -LogPath $staticLog -ErrPath $staticErr -TimeoutSecondsForStep ([int]([Math]::Max($TimeoutSeconds, 1.0) + 20))
    $staticCombined = $staticResult.Stdout + "`n" + $staticResult.Stderr
    foreach ($line in ($staticCombined -split "`r?`n" | Where-Object { $_ -match "PC_|TCP_|N03_STATIC_DIRECT|RECOMMENDED_|ELEVATED_|APPLY_|FIREWALL_|ADMIN_|IS_ADMIN|SELECTED_ADAPTER" } | Select-Object -Last 100)) {
        Write-SummaryLine "STATIC_PREFLIGHT_MATCH $line"
    }
    $staticBlockers = @(Get-MarkerValues -Text $staticCombined -Key "N03_STATIC_DIRECT_NETWORK_BLOCKER")
    $staticPassMarkers = @(Get-MarkerValues -Text $staticCombined -Key "N03_STATIC_DIRECT_NETWORK_PREFLIGHT_PASS")
    $staticStatus = if ($staticPassMarkers -contains "1") {
        "PASS"
    } elseif ($staticBlockers.Count -gt 0) {
        "BLOCKED"
    } else {
        Step-Status $staticResult
    }
    Add-MatrixRow -Item "N03-1_pc_static_direct_preflight" -Status $staticStatus -Evidence $staticLog -Note "Read-only PC Ethernet static direct preflight."
    $recommendedApply = (Get-MarkerValues -Text $staticCombined -Key "RECOMMENDED_APPLY_COMMAND" | Select-Object -First 1)
    $recommendedFirewall = (Get-MarkerValues -Text $staticCombined -Key "RECOMMENDED_FIREWALL_COMMAND" | Select-Object -First 1)
    $elevatedApply = (Get-MarkerValues -Text $staticCombined -Key "ELEVATED_APPLY_COMMAND" | Select-Object -First 1)
    $elevatedUac = (Get-MarkerValues -Text $staticCombined -Key "ELEVATED_UAC_COMMAND" | Select-Object -First 1)
    if ($recommendedApply) { Write-SummaryLine "N03_RECOMMENDED_STATIC_IP_COMMAND=$recommendedApply" }
    if ($recommendedFirewall) { Write-SummaryLine "N03_RECOMMENDED_FIREWALL_COMMAND=$recommendedFirewall" }
    if ($elevatedApply) { Write-SummaryLine "N03_ELEVATED_STATIC_DIRECT_SETUP_COMMAND=$elevatedApply" }
    if ($elevatedUac) { Write-SummaryLine "N03_ELEVATED_STATIC_DIRECT_UAC_COMMAND=$elevatedUac" }
    if ($staticBlockers -contains "pc_missing_expected_static_ip") {
        Write-N03IncompletePassMarkers
        Write-SummaryLine "N03_REAL_BOARD_ACCEPTANCE_PASS=0"
        Write-SummaryLine "N03_REAL_BOARD_ACCEPTANCE_BLOCKED=1"
        Write-SummaryLine "N03_BLOCKED_REASON=pc_missing_expected_static_ip"
        Write-SummaryLine "N03_NETWORK_FIRST_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"
        $md = @(
            "# N03 Network-first Real Acceptance",
            "",
            "Generated: $(Get-Date -Format o)",
            "",
            "Verdict: BLOCKED",
            "",
            "PC Ethernet is not configured for the N03 static-direct subnet, so no TCP payload, no PS/PL synthetic injection, no FPGA programming, and no TFDU drive were executed.",
            "",
            "- Required PC IP: 192.168.10.1/24",
            "- Target: ${TargetHost}:$Port",
            "- Recommended static IP command: $recommendedApply",
            "- Recommended firewall command: $recommendedFirewall",
            "- Elevated setup command: $elevatedApply",
            "- Elevated UAC command: $elevatedUac",
            "- Summary log: $summaryLog",
            "- Matrix CSV: $matrixCsv",
            "- Log dir: $logDir"
        )
        [System.IO.File]::WriteAllLines($mdReport, [string[]]$md, [System.Text.Encoding]::UTF8)
        exit 20
    }
}

if (-not $SkipUartProbe) {
    $uartLog = Join-Path $logDir "uart_probe.out.log"
    $uartErr = Join-Path $logDir "uart_probe.err.log"
    $uartResult = Invoke-LoggedProcess -Name "uart_probe_readonly" -FilePath "powershell.exe" -Arguments @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $uartProbeScript,
        "-ComPort",
        $ComPort,
        "-DurationSeconds",
        [string]$UartProbeSeconds
    ) -LogPath $uartLog -ErrPath $uartErr -TimeoutSecondsForStep ($UartProbeSeconds + 20)
    Add-MatrixRow -Item "uart_probe_readonly" -Status (Step-Status $uartResult) -Evidence $uartLog -Note "Read-only UART boot/IP probe."
    $uartCombined = $uartResult.Stdout + "`n" + $uartResult.Stderr
    $uartDhcpFallbackSeen = Test-MarkerPositive -Text $uartCombined -Key "MATCH_DHCP_STATIC_FALLBACK"
    $uartTcpListenSeen = Test-MarkerPositive -Text $uartCombined -Key "MATCH_TCP_LISTEN_5001"
    $uartBoardIps = @(Get-MarkerValues -Text $uartCombined -Key "BOARD_IP_SEEN")
    $uartFallbackIpSeen = $uartBoardIps -contains $TargetHost
    $uartFallbackStatus = if ($uartDhcpFallbackSeen -and $uartTcpListenSeen -and $uartFallbackIpSeen) {
        "PASS"
    } elseif ($uartResult.ExitCode -eq 0) {
        "PENDING"
    } else {
        Step-Status $uartResult
    }
    Add-MatrixRow -Item "N03-6_uart_dhcp_fallback_probe" -Status $uartFallbackStatus -Evidence $uartLog -Note "Read-only UART evidence for DHCP timeout, static fallback IP, and TCP_READY."
    Write-SummaryLine "N03_DHCP_FALLBACK_UART_DHCP_TIMEOUT_SEEN=$([int]$uartDhcpFallbackSeen)"
    Write-SummaryLine "N03_DHCP_FALLBACK_UART_STATIC_IP_SEEN=$([int]$uartFallbackIpSeen)"
    Write-SummaryLine "N03_DHCP_FALLBACK_UART_TCP_READY_SEEN=$([int]$uartTcpListenSeen)"
} else {
    $uartCombined = ""
    $uartDhcpFallbackSeen = $false
    $uartTcpListenSeen = $false
    $uartFallbackIpSeen = $false
    Write-SummaryLine "N03_DHCP_FALLBACK_UART_DHCP_TIMEOUT_SEEN=0"
    Write-SummaryLine "N03_DHCP_FALLBACK_UART_STATIC_IP_SEEN=0"
    Write-SummaryLine "N03_DHCP_FALLBACK_UART_TCP_READY_SEEN=0"
}

$tcpQuick = $true
if ($DryRun) {
    Write-SummaryLine "TCP_QUICK_CONNECT_SKIPPED_DRY_RUN=1"
} else {
    $tcpQuick = Test-TcpPortQuick -HostName $TargetHost -TcpPort $Port -TimeoutMs ([int]([Math]::Max($TimeoutSeconds, 1.0) * 1000.0))
}
Write-SummaryLine "TCP_QUICK_CONNECT_OK=$([int]$tcpQuick)"
if (-not $tcpQuick) {
    Add-MatrixRow -Item "N03-1_static_tcp_connect" -Status "BLOCKED" -Evidence "$TargetHost`:$Port=False" -Note "Board PS bridge is not reachable over TCP."
    Write-N03IncompletePassMarkers
    Write-SummaryLine "N03_REAL_BOARD_ACCEPTANCE_PASS=0"
    Write-SummaryLine "N03_REAL_BOARD_ACCEPTANCE_BLOCKED=1"
    Write-SummaryLine "N03_BLOCKED_REASON=tcp_target_not_reachable"
    Write-SummaryLine "N03_NETWORK_FIRST_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"
    $md = @(
        "# N03 Network-first Real Acceptance",
        "",
        "Generated: $(Get-Date -Format o)",
        "",
        "Verdict: BLOCKED",
        "",
        "Target ${TargetHost}:$Port was not reachable, so no TCP payload, no PS/PL synthetic injection, no FPGA programming, and no TFDU drive were executed.",
        "",
        "- Summary log: $summaryLog",
        "- Matrix CSV: $matrixCsv",
        "- Log dir: $logDir"
    )
    [System.IO.File]::WriteAllLines($mdReport, [string[]]$md, [System.Text.Encoding]::UTF8)
    exit 20
}

$overall = 0
$memoryAllOk = $true
$psplAllOk = $true

$smoke = Invoke-Acceptance -Name "n03_01_02_smoke" -Arguments @(
    "-Mode", "smoke",
    "-TargetHost", $TargetHost,
    "-Port", [string]$Port,
    "-TimeoutSeconds", [string]$TimeoutSeconds
) -TimeoutSecondsForStep ([int]($TimeoutSeconds + 30))
Add-MatrixRow -Item "N03-1_2_static_tcp_hello" -Status (Step-Status $smoke) -Evidence (Join-Path $logDir "n03_01_02_smoke.out.log") -Note "Static TCP connect plus HELLO/STATUS."
if ($smoke.ExitCode -ne 0 -and $overall -eq 0) { $overall = $smoke.ExitCode }

$commands = Invoke-Acceptance -Name "n03_03_commands" -Arguments @(
    "-Mode", "n03_commands",
    "-TargetHost", $TargetHost,
    "-Port", [string]$Port,
    "-TimeoutSeconds", [string]$TimeoutSeconds
) -TimeoutSecondsForStep 90
Add-MatrixRow -Item "N03-3_commands" -Status (Step-Status $commands) -Evidence (Join-Path $logDir "n03_03_commands.out.log") -Note "N03 ASCII command matrix."
if ($commands.ExitCode -ne 0 -and $overall -eq 0) { $overall = $commands.ExitCode }

foreach ($size in @(1, 8, 16, 64, 128, 256, 512, 1024, 4096)) {
    $result = Invoke-PayloadCase -Mode "n03_memory_echo" -PayloadBytes $size -Count $MatrixRepeat -NamePrefix "n03_04_matrix" -Pattern "incremental"
    Add-MatrixRow -Item "N03-4_memory_echo_${size}" -Status (Step-Status $result) -Evidence (Join-Path $logDir "n03_04_matrix_n03_memory_echo_${size}.out.log") -Note "Application payload bytes=$size; larger than one RFCM frame are segmented over 512-byte frames."
    if ($result.ExitCode -ne 0) { $memoryAllOk = $false }
    if ($result.ExitCode -ne 0 -and $overall -eq 0) { $overall = $result.ExitCode }
}
$memorySoak = Invoke-DurationCase -Mode "n03_memory_echo" -PayloadBytes 1024 -Seconds $LongSeconds -NamePrefix "n03_04_soak" -Pattern "incremental"
Add-MatrixRow -Item "N03-4_memory_echo_1024_${LongSeconds}s" -Status (Step-Status $memorySoak) -Evidence (Join-Path $logDir "n03_04_soak_n03_memory_echo_1024_${LongSeconds}s.out.log") -Note "Sustained memory echo run, capped at 600 seconds by lower wrapper."
if ($memorySoak.ExitCode -ne 0) { $memoryAllOk = $false }
if ($memorySoak.ExitCode -ne 0 -and $overall -eq 0) { $overall = $memorySoak.ExitCode }

foreach ($case in @(
    @{ Size = 16; Count = 10 },
    @{ Size = 64; Count = 100 },
    @{ Size = 256; Count = 100 }
)) {
    $result = Invoke-PayloadCase -Mode "n03_pspl_synth" -PayloadBytes $case.Size -Count $case.Count -NamePrefix "n03_05_matrix" -Pattern "synth_ramp"
    Add-MatrixRow -Item "N03-5_pspl_synth_$($case.Size)" -Status (Step-Status $result) -Evidence (Join-Path $logDir "n03_05_matrix_n03_pspl_synth_$($case.Size).out.log") -Note "PS/PL synthetic loopback payload bytes=$($case.Size)."
    if ($result.ExitCode -ne 0) { $psplAllOk = $false }
    if ($result.ExitCode -ne 0 -and $overall -eq 0) { $overall = $result.ExitCode }
}
foreach ($case in @(
    @{ Size = 256; Seconds = $SustainedSeconds },
    @{ Size = 1024; Seconds = $SustainedSeconds },
    @{ Size = 1024; Seconds = $LongSeconds }
)) {
    $result = Invoke-DurationCase -Mode "n03_pspl_synth" -PayloadBytes $case.Size -Seconds $case.Seconds -NamePrefix "n03_05_soak" -Pattern "synth_ramp"
    Add-MatrixRow -Item "N03-5_pspl_synth_$($case.Size)_$($case.Seconds)s" -Status (Step-Status $result) -Evidence (Join-Path $logDir "n03_05_soak_n03_pspl_synth_$($case.Size)_$($case.Seconds)s.out.log") -Note "PS/PL synthetic sustained run; large application payloads are segmented over safe frame sizes."
    if ($result.ExitCode -ne 0) { $psplAllOk = $false }
    if ($result.ExitCode -ne 0 -and $overall -eq 0) { $overall = $result.ExitCode }
}

$negative = Invoke-Acceptance -Name "n03_09_negative" -Arguments @(
    "-Mode", "n03_negative",
    "-TargetHost", $TargetHost,
    "-Port", [string]$Port,
    "-TimeoutSeconds", [string]$TimeoutSeconds
) -TimeoutSecondsForStep 90
Add-MatrixRow -Item "N03-9_negative" -Status (Step-Status $negative) -Evidence (Join-Path $logDir "n03_09_negative.out.log") -Note "IR-deferred and unknown-command negative tests."
if ($negative.ExitCode -ne 0 -and $overall -eq 0) { $overall = $negative.ExitCode }

$reconnect = Invoke-Acceptance -Name "n03_09_reconnect" -Arguments @(
    "-Mode", "reconnect",
    "-TargetHost", $TargetHost,
    "-Port", [string]$Port,
    "-TimeoutSeconds", [string]$TimeoutSeconds,
    "-ReconnectCycles", [string]$ReconnectCycles
) -TimeoutSecondsForStep ([int](($TimeoutSeconds + 2.0) * $ReconnectCycles + 60))
Add-MatrixRow -Item "N03-9_reconnect" -Status (Step-Status $reconnect) -Evidence (Join-Path $logDir "n03_09_reconnect.out.log") -Note "TCP reconnect cycles."
if ($reconnect.ExitCode -ne 0 -and $overall -eq 0) { $overall = $reconnect.ExitCode }

$pass = ($overall -eq 0 -and -not $DryRun)
$dhcpFallbackPass = (
    $uartDhcpFallbackSeen `
    -and $uartFallbackIpSeen `
    -and $uartTcpListenSeen `
    -and ($smoke.ExitCode -eq 0) `
    -and $memoryAllOk `
    -and -not $DryRun
)
Add-MatrixRow -Item "N03-6_dhcp_timeout_static_fallback" -Status $(if ($dhcpFallbackPass) { "PASS" } else { "REAL_BOARD_PENDING" }) -Evidence $matrixCsv -Note "Requires UART DHCP timeout/static fallback/TCP_READY plus real TCP HELLO and memory echo."
if ($DryRun) {
    Write-SummaryLine "N03_DRY_RUN=1"
}
Write-SummaryLine "N03_STATIC_DIRECT_TCP_PASS=$([int]($smoke.ExitCode -eq 0 -and -not $DryRun))"
Write-SummaryLine "N03_TCP_PROTOCOL_COMMAND_PASS=$([int]($commands.ExitCode -eq 0 -and -not $DryRun))"
Write-SummaryLine "N03_TCP_PAYLOAD_MEMORY_ECHO_PASS=$([int]($memoryAllOk -and -not $DryRun))"
Write-SummaryLine "N03_TCP_TO_PSPL_SYNTHETIC_LOOPBACK_PASS=$([int]($psplAllOk -and -not $DryRun))"
Write-SummaryLine "N03_IR_PHYSICAL_DEFERRED_NEGATIVE_PASS=$([int]($negative.ExitCode -eq 0 -and -not $DryRun))"
Write-SummaryLine "N03_LINK_RECOVERY_PASS=$([int]($reconnect.ExitCode -eq 0 -and -not $DryRun))"
Write-SummaryLine "N03_DHCP_FALLBACK_TCP_HELLO_PASS=$([int]($smoke.ExitCode -eq 0 -and -not $DryRun))"
Write-SummaryLine "N03_DHCP_FALLBACK_MEMORY_ECHO_PASS=$([int]($memoryAllOk -and -not $DryRun))"
Write-SummaryLine "N03_DHCP_FALLBACK_PASS=$([int]$dhcpFallbackPass)"
Write-SummaryLine "N03_PC_HOSTED_DHCP_LEASE_PASS=0"
Write-SummaryLine "N03_REAL_BOARD_ACCEPTANCE_PASS=$([int]$pass)"
Write-SummaryLine "N03_REAL_BOARD_ACCEPTANCE_BLOCKED=0"
Write-SummaryLine "NO_IR_PHYSICAL_PASS_CLAIM=1"
Write-SummaryLine "NO_2LANE_PASS_CLAIM=1"
Write-SummaryLine "N03_NETWORK_FIRST_ACCEPTANCE_SAFE_END $(Get-Date -Format o)"

$verdict = if ($pass) { "PASS_REAL_BOARD_STATIC_DIRECT_BASELINE_EXCEPT_DHCP_LEASE" } else { "FAIL_OR_PARTIAL_REAL_BOARD" }
$mdLines = @(
    "# N03 Network-first Real Acceptance",
    "",
    "Generated: $(Get-Date -Format o)",
    "",
    "Verdict: $verdict",
    "",
    "This wrapper does not program FPGA, does not write UART, and does not drive TFDU. It uses the N03 network-first modes where IR physical is deferred.",
    "",
    "- Target host: $TargetHost",
    "- TCP port: $Port",
    "- DHCP fallback pass: $([int]$dhcpFallbackPass)",
    "- DHCP fallback UART DHCP timeout seen: $([int]$uartDhcpFallbackSeen)",
    "- DHCP fallback UART static IP seen: $([int]$uartFallbackIpSeen)",
    "- DHCP fallback UART TCP ready seen: $([int]$uartTcpListenSeen)",
    "- Summary log: $summaryLog",
    "- Matrix CSV: $matrixCsv",
    "- Log dir: $logDir",
    "",
    "Non-claims: IR_PHYSICAL_PASS=0, 2LANE_PASS=0, REAL_IR_DATA_ROUNDTRIP_PASS=0, ROTATION_PASS=0, FINAL_TARGET_PASS=0."
)
[System.IO.File]::WriteAllLines($mdReport, [string[]]$mdLines, [System.Text.Encoding]::UTF8)

exit $overall
