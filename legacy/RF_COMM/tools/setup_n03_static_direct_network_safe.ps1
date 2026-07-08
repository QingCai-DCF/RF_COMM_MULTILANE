[CmdletBinding()]
param(
    [string]$InterfaceAlias = "",
    [string]$ExpectedPcIp = "192.168.10.1",
    [int]$PrefixLength = 24,
    [string]$TargetHost = "192.168.10.2",
    [int]$Port = 5001,
    [int]$TimeoutMs = 1000,
    [int]$PostLaunchPollSeconds = 15,
    [switch]$Apply,
    [switch]$AddFirewallRule,
    [switch]$LaunchElevatedApply,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "n03_static_direct_network_preflight_$stamp.summary.txt"
$jsonReport = Join-Path $reportsDir "n03_static_direct_network_preflight_$stamp.json"
$mdReport = Join-Path $reportsDir "n03_static_direct_network_preflight_$stamp.md"
$currentSummary = Join-Path $reportsDir "n03_static_direct_network_preflight_current.summary.txt"
$currentJson = Join-Path $reportsDir "n03_static_direct_network_preflight_current.json"
$currentMd = Join-Path $reportsDir "n03_static_direct_network_preflight_current.md"

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding utf8
}

function Test-TcpPortQuick {
    param(
        [string]$HostName,
        [int]$TcpPort,
        [int]$ConnectTimeoutMs
    )
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $iar = $client.BeginConnect($HostName, $TcpPort, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne($ConnectTimeoutMs, $false)
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

function ConvertTo-PlainObject {
    param($Object)
    if ($null -eq $Object) {
        return $null
    }
    return [pscustomobject]@{
        name = [string]$Object.Name
        interface_description = [string]$Object.InterfaceDescription
        status = [string]$Object.Status
        link_speed = [string]$Object.LinkSpeed
        if_index = [int]$Object.ifIndex
        mac_address = [string]$Object.MacAddress
    }
}

function Is-WifiAdapter {
    param($Adapter)
    $joined = ("{0} {1}" -f $Adapter.Name, $Adapter.InterfaceDescription).ToLowerInvariant()
    return ($joined -match "wi-fi|wifi|wireless|wlan|802\.11")
}

function Is-EthernetCandidate {
    param($Adapter)
    if (Is-WifiAdapter $Adapter) {
        return $false
    }
    $joined = ("{0} {1}" -f $Adapter.Name, $Adapter.InterfaceDescription).ToLowerInvariant()
    return ($joined -match "ethernet|realtek|gbe|2\.5gbe|lan")
}

function Test-IsAdministrator {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Quote-CommandArg {
    param([string]$Value)
    if ($Value -match "[\s`"']") {
        return "'" + ($Value -replace "'", "''") + "'"
    }
    return $Value
}

"N03_STATIC_DIRECT_NETWORK_PREFLIGHT_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding utf8
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "INTERFACE_ALIAS_ARG=$InterfaceAlias"
Write-SummaryLine "EXPECTED_PC_IP=$ExpectedPcIp"
Write-SummaryLine "PREFIX_LENGTH=$PrefixLength"
Write-SummaryLine "TARGET_HOST=$TargetHost"
Write-SummaryLine "PORT=$Port"
Write-SummaryLine "TIMEOUT_MS=$TimeoutMs"
Write-SummaryLine "POST_LAUNCH_POLL_SECONDS=$PostLaunchPollSeconds"
Write-SummaryLine "APPLY=$([int]$Apply.IsPresent)"
Write-SummaryLine "ADD_FIREWALL_RULE=$([int]$AddFirewallRule.IsPresent)"
Write-SummaryLine "LAUNCH_ELEVATED_APPLY=$([int]$LaunchElevatedApply.IsPresent)"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "NO_FPGA_PROGRAMMING=1"
Write-SummaryLine "NO_UART_WRITE=1"
Write-SummaryLine "NO_TFDU_DRIVE=1"
Write-SummaryLine "NO_TCP_PAYLOAD=1"
$isAdmin = Test-IsAdministrator
Write-SummaryLine "IS_ADMIN=$([int]$isAdmin)"

$adapters = @(Get-NetAdapter -Physical -ErrorAction SilentlyContinue)
$ethernet = @($adapters | Where-Object { Is-EthernetCandidate $_ })
$selected = $null
if ($InterfaceAlias -ne "") {
    $selected = $adapters | Where-Object { $_.Name -eq $InterfaceAlias } | Select-Object -First 1
} else {
    $selected = $ethernet |
        Sort-Object -Property @{ Expression = { if ($_.Status -eq "Up") { 0 } else { 1 } } }, Name |
        Select-Object -First 1
}

if ($null -eq $selected) {
    Write-SummaryLine "SELECTED_ADAPTER=NONE"
    Write-SummaryLine "PC_ETHERNET_LINK_UP=0"
    Write-SummaryLine "PC_EXPECTED_STATIC_IP_PRESENT=0"
    Write-SummaryLine "PC_TARGET_SUBNET_ROUTE_READY=0"
    Write-SummaryLine "TCP_QUICK_CONNECT_OK=0"
    Write-SummaryLine "N03_STATIC_DIRECT_NETWORK_PREFLIGHT_PASS=0"
    Write-SummaryLine "N03_STATIC_DIRECT_NETWORK_BLOCKER=ethernet_adapter_not_found"
    Write-SummaryLine "N03_STATIC_DIRECT_NETWORK_PREFLIGHT_END $(Get-Date -Format o)"
    exit 20
}

$selectedPlain = ConvertTo-PlainObject $selected
Write-SummaryLine "SELECTED_ADAPTER=$($selected.Name)"
Write-SummaryLine "SELECTED_ADAPTER_DESC=$($selected.InterfaceDescription)"
Write-SummaryLine "SELECTED_ADAPTER_STATUS=$($selected.Status)"
Write-SummaryLine "SELECTED_ADAPTER_LINK_SPEED=$($selected.LinkSpeed)"
Write-SummaryLine "SELECTED_ADAPTER_IFINDEX=$($selected.ifIndex)"

$isWifi = Is-WifiAdapter $selected
$linkUp = ($selected.Status -eq "Up")
$isEthernet = Is-EthernetCandidate $selected
Write-SummaryLine "SELECTED_ADAPTER_WIFI=$([int]$isWifi)"
Write-SummaryLine "SELECTED_ADAPTER_ETHERNET_CANDIDATE=$([int]$isEthernet)"
Write-SummaryLine "PC_ETHERNET_LINK_UP=$([int]$linkUp)"

$existingIps = @(Get-NetIPAddress -InterfaceIndex $selected.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue)
$expectedIpPresent = $false
foreach ($ip in $existingIps) {
    Write-SummaryLine "SELECTED_IPV4=$($ip.IPAddress)/$($ip.PrefixLength) state=$($ip.AddressState) origin=$($ip.PrefixOrigin)"
    if ($ip.IPAddress -eq $ExpectedPcIp -and [int]$ip.PrefixLength -eq $PrefixLength) {
        $expectedIpPresent = $true
    }
}
Write-SummaryLine "PC_EXPECTED_STATIC_IP_PRESENT=$([int]$expectedIpPresent)"
if (-not $expectedIpPresent) {
    Write-SummaryLine "RECOMMENDED_APPLY_COMMAND=New-NetIPAddress -InterfaceAlias `"$($selected.Name)`" -IPAddress $ExpectedPcIp -PrefixLength $PrefixLength -SkipAsSource `$false"
}
Write-SummaryLine "RECOMMENDED_FIREWALL_COMMAND=New-NetFirewallRule -DisplayName RF_COMM_TCP_5001_N03 -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow"
$elevatedApplyArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $MyInvocation.MyCommand.Path,
    "-InterfaceAlias",
    $selected.Name,
    "-ExpectedPcIp",
    $ExpectedPcIp,
    "-PrefixLength",
    [string]$PrefixLength,
    "-TargetHost",
    $TargetHost,
    "-Port",
    [string]$Port,
    "-TimeoutMs",
    [string]$TimeoutMs,
    "-Apply",
    "-AddFirewallRule"
)
$elevatedApplyArgLine = (($elevatedApplyArgs | ForEach-Object { Quote-CommandArg $_ }) -join " ")
$elevatedApplyCommand = "powershell.exe $elevatedApplyArgLine"
$escapedElevatedApplyArgLine = $elevatedApplyArgLine -replace "'", "''"
$elevatedUacCommand = "Start-Process -FilePath powershell.exe -ArgumentList '$escapedElevatedApplyArgLine' -Verb RunAs"
$detachedUacScript = "Start-Process -FilePath powershell.exe -ArgumentList '$escapedElevatedApplyArgLine' -Verb RunAs"
$detachedUacArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-Command",
    $detachedUacScript
)
Write-SummaryLine "ELEVATED_APPLY_COMMAND=$elevatedApplyCommand"
Write-SummaryLine "ELEVATED_UAC_COMMAND=$elevatedUacCommand"
Write-SummaryLine "ELEVATED_DETACHED_UAC_COMMAND=Start-Process -FilePath powershell.exe -ArgumentList <uac-helper> -WindowStyle Hidden"
Write-SummaryLine "ELEVATED_APPLY_COMMAND_NOTE=run_uac_then_rerun_preflight"
if (-not $isAdmin -and -not $expectedIpPresent) {
    Write-SummaryLine "ADMIN_REQUIRED_TO_APPLY=1"
    Write-SummaryLine "N03_STATIC_DIRECT_NETWORK_NEXT_ACTION=run_elevated_uac_command"
} else {
    Write-SummaryLine "ADMIN_REQUIRED_TO_APPLY=0"
}

if ($LaunchElevatedApply -and -not $expectedIpPresent) {
    if ($DryRun) {
        Write-SummaryLine "LAUNCH_ELEVATED_APPLY_DRY_RUN_COMMAND=$elevatedUacCommand"
    } elseif ($isAdmin) {
        Write-SummaryLine "LAUNCH_ELEVATED_APPLY_ALREADY_ADMIN_APPLY_INLINE=1"
        $Apply = [System.Management.Automation.SwitchParameter]::Present
        $AddFirewallRule = [System.Management.Automation.SwitchParameter]::Present
    } else {
        Write-SummaryLine "LAUNCH_ELEVATED_APPLY_START=1"
        Start-Process -FilePath "powershell.exe" -ArgumentList $detachedUacArgs -WorkingDirectory $repoRoot -WindowStyle Hidden | Out-Null
        Write-SummaryLine "LAUNCH_ELEVATED_APPLY_STARTED=1"
        $pollDeadline = (Get-Date).AddSeconds([Math]::Max(0, $PostLaunchPollSeconds))
        do {
            Start-Sleep -Seconds 1
            $existingIps = @(Get-NetIPAddress -InterfaceIndex $selected.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue)
            $expectedIpPresent = $false
            foreach ($ip in $existingIps) {
                if ($ip.IPAddress -eq $ExpectedPcIp -and [int]$ip.PrefixLength -eq $PrefixLength) {
                    $expectedIpPresent = $true
                }
            }
        } while (-not $expectedIpPresent -and (Get-Date) -lt $pollDeadline)
        Write-SummaryLine "PC_EXPECTED_STATIC_IP_PRESENT_AFTER_ELEVATED_LAUNCH=$([int]$expectedIpPresent)"
        Write-SummaryLine "LAUNCH_ELEVATED_APPLY_POLL_DONE=1"
        if (-not $expectedIpPresent) {
            Write-SummaryLine "LAUNCH_ELEVATED_APPLY_PENDING_OR_DECLINED=1"
        }
    }
}

$applyAttempted = $false
$applySucceeded = $false
$applyRefusedNotAdmin = $false
$firewallAttempted = $false
$firewallSucceeded = $false
$firewallRefusedNotAdmin = $false
if ($Apply -and -not $expectedIpPresent) {
    $applyAttempted = $true
    if ($InterfaceAlias -eq "") {
        throw "-Apply requires -InterfaceAlias so the target adapter is explicit."
    }
    if (-not $isEthernet -or $isWifi) {
        throw "-Apply refused: selected adapter is not a wired Ethernet candidate."
    }
    if (-not $linkUp) {
        throw "-Apply refused: selected Ethernet link is not Up."
    }
    if ($DryRun) {
        Write-SummaryLine "APPLY_DRY_RUN_COMMAND=New-NetIPAddress -InterfaceAlias `"$InterfaceAlias`" -IPAddress $ExpectedPcIp -PrefixLength $PrefixLength -SkipAsSource `$false"
    } elseif (-not $isAdmin) {
        $applyRefusedNotAdmin = $true
        Write-SummaryLine "APPLY_REFUSED_NOT_ADMIN=1"
    } else {
        New-NetIPAddress -InterfaceAlias $InterfaceAlias -IPAddress $ExpectedPcIp -PrefixLength $PrefixLength -SkipAsSource $false | Out-Null
        $applySucceeded = $true
    }
}

if ($AddFirewallRule) {
    $firewallAttempted = $true
    $ruleName = "RF_COMM_TCP_5001_N03"
    $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if ($DryRun) {
        Write-SummaryLine "FIREWALL_DRY_RUN_COMMAND=New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow"
    } elseif ($null -ne $existingRule) {
        $firewallSucceeded = $true
    } elseif (-not $isAdmin) {
        $firewallRefusedNotAdmin = $true
        Write-SummaryLine "FIREWALL_REFUSED_NOT_ADMIN=1"
    } else {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
        $firewallSucceeded = $true
    }
}

if ($Apply -and -not $DryRun) {
    $existingIps = @(Get-NetIPAddress -InterfaceIndex $selected.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue)
    $expectedIpPresent = $false
    foreach ($ip in $existingIps) {
        if ($ip.IPAddress -eq $ExpectedPcIp -and [int]$ip.PrefixLength -eq $PrefixLength) {
            $expectedIpPresent = $true
        }
    }
    Write-SummaryLine "PC_EXPECTED_STATIC_IP_PRESENT_AFTER_APPLY=$([int]$expectedIpPresent)"
}

$targetSubnetReady = ($expectedIpPresent -and $linkUp)
Write-SummaryLine "PC_TARGET_SUBNET_ROUTE_READY=$([int]$targetSubnetReady)"
$tcpQuick = Test-TcpPortQuick -HostName $TargetHost -TcpPort $Port -ConnectTimeoutMs $TimeoutMs
Write-SummaryLine "TCP_QUICK_CONNECT_OK=$([int]$tcpQuick)"

$blockers = [System.Collections.Generic.List[string]]::new()
if (-not $isEthernet -or $isWifi) { $blockers.Add("selected_adapter_not_wired_ethernet") }
if (-not $linkUp) { $blockers.Add("ethernet_link_not_up") }
if (-not $expectedIpPresent) { $blockers.Add("pc_missing_expected_static_ip") }
if (-not $tcpQuick) { $blockers.Add("tcp_target_not_reachable") }
if ($applyRefusedNotAdmin) { $blockers.Add("apply_requires_admin") }
if ($firewallRefusedNotAdmin) { $blockers.Add("firewall_requires_admin") }

$preflightPass = ($blockers.Count -eq 0)
foreach ($reason in $blockers) {
    Write-SummaryLine "N03_STATIC_DIRECT_NETWORK_BLOCKER=$reason"
}
Write-SummaryLine "APPLY_ATTEMPTED=$([int]$applyAttempted)"
Write-SummaryLine "APPLY_SUCCEEDED=$([int]$applySucceeded)"
Write-SummaryLine "APPLY_REFUSED_NOT_ADMIN=$([int]$applyRefusedNotAdmin)"
Write-SummaryLine "FIREWALL_ATTEMPTED=$([int]$firewallAttempted)"
Write-SummaryLine "FIREWALL_SUCCEEDED=$([int]$firewallSucceeded)"
Write-SummaryLine "FIREWALL_REFUSED_NOT_ADMIN=$([int]$firewallRefusedNotAdmin)"
Write-SummaryLine "N03_STATIC_DIRECT_NETWORK_PREFLIGHT_PASS=$([int]$preflightPass)"
Write-SummaryLine "N03_STATIC_DIRECT_NETWORK_PREFLIGHT_END $(Get-Date -Format o)"

$payload = [ordered]@{
    generated = (Get-Date -Format o)
    preflight_pass = [bool]$preflightPass
    blockers = @($blockers)
    expected_pc_ip = $ExpectedPcIp
    prefix_length = $PrefixLength
    target_host = $TargetHost
    port = $Port
    selected_adapter = $selectedPlain
    ethernet_candidates = @($ethernet | ForEach-Object { ConvertTo-PlainObject $_ })
    selected_ipv4 = @($existingIps | ForEach-Object {
        [pscustomobject]@{
            ip_address = [string]$_.IPAddress
            prefix_length = [int]$_.PrefixLength
            address_state = [string]$_.AddressState
            prefix_origin = [string]$_.PrefixOrigin
        }
    })
    markers = [ordered]@{
        pc_ethernet_link_up = [bool]$linkUp
        pc_expected_static_ip_present = [bool]$expectedIpPresent
        pc_target_subnet_route_ready = [bool]$targetSubnetReady
        tcp_quick_connect_ok = [bool]$tcpQuick
        is_admin = [bool]$isAdmin
        admin_required_to_apply = [bool]((-not $isAdmin) -and (-not $expectedIpPresent))
        apply_refused_not_admin = [bool]$applyRefusedNotAdmin
        firewall_refused_not_admin = [bool]$firewallRefusedNotAdmin
        no_fpga_programming = $true
        no_uart_write = $true
        no_tfdu_drive = $true
        no_tcp_payload = $true
    }
    elevated_apply_command = $elevatedApplyCommand
    elevated_uac_command = $elevatedUacCommand
}
$payload | ConvertTo-Json -Depth 6 | Out-File -LiteralPath $jsonReport -Encoding utf8

$md = @(
    "# N03 Static Direct Network Preflight",
    "",
    "Generated: $(Get-Date -Format o)",
    "",
    "Verdict: $(if ($preflightPass) { 'PASS_PREFLIGHT' } else { 'BLOCKED' })",
    "",
    "This helper is read-only by default. It does not program FPGA, write UART, drive TFDU, or send TCP payloads.",
    "",
    "- Selected adapter: $($selected.Name)",
    "- Adapter status: $($selected.Status)",
    "- Expected PC IP: $ExpectedPcIp/$PrefixLength",
    "- Expected IP present: $expectedIpPresent",
    "- Current shell administrator: $isAdmin",
    "- Target TCP: ${TargetHost}:$Port",
    "- TCP quick connect: $tcpQuick",
    "- Blockers: $(if ($blockers.Count) { $blockers -join ', ' } else { 'none' })",
    "- Elevated apply command: $elevatedApplyCommand",
    "- Elevated UAC command: $elevatedUacCommand",
    "- Summary log: $summaryLog",
    "- JSON report: $jsonReport"
)
[System.IO.File]::WriteAllLines($mdReport, [string[]]$md, [System.Text.Encoding]::UTF8)

Copy-Item -LiteralPath $summaryLog -Destination $currentSummary -Force
Copy-Item -LiteralPath $jsonReport -Destination $currentJson -Force
Copy-Item -LiteralPath $mdReport -Destination $currentMd -Force

if ($preflightPass) {
    exit 0
}
exit 20
