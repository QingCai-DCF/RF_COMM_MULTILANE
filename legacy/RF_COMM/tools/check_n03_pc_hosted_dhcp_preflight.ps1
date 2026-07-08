[CmdletBinding()]
param(
    [string]$InterfaceAlias = "",
    [string]$IcsServerIp = "192.168.137.1",
    [string]$StandaloneServerIp = "192.168.20.1",
    [int]$PrefixLength = 24,
    [string]$DhcpPoolStart = "192.168.20.100",
    [string]$DhcpPoolEnd = "192.168.20.200",
    [int]$TcpPort = 5001
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$summaryLog = Join-Path $reportsDir "n03_pc_hosted_dhcp_preflight_$stamp.summary.txt"
$jsonReport = Join-Path $reportsDir "n03_pc_hosted_dhcp_preflight_$stamp.json"
$mdReport = Join-Path $reportsDir "n03_pc_hosted_dhcp_preflight_$stamp.md"
$currentSummary = Join-Path $reportsDir "n03_pc_hosted_dhcp_preflight_current.summary.txt"
$currentJson = Join-Path $reportsDir "n03_pc_hosted_dhcp_preflight_current.json"
$currentMd = Join-Path $reportsDir "n03_pc_hosted_dhcp_preflight_current.md"

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding utf8
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

function ConvertTo-AdapterObject {
    param($Adapter)
    if ($null -eq $Adapter) {
        return $null
    }
    return [pscustomobject]@{
        name = [string]$Adapter.Name
        interface_description = [string]$Adapter.InterfaceDescription
        status = [string]$Adapter.Status
        link_speed = [string]$Adapter.LinkSpeed
        if_index = [int]$Adapter.ifIndex
        mac_address = [string]$Adapter.MacAddress
    }
}

function ConvertTo-ServiceObject {
    param($Service)
    if ($null -eq $Service) {
        return [pscustomobject]@{
            present = $false
            name = ""
            status = "MISSING"
            display_name = ""
        }
    }
    return [pscustomobject]@{
        present = $true
        name = [string]$Service.Name
        status = [string]$Service.Status
        display_name = [string]$Service.DisplayName
    }
}

function ConvertTo-IcsSharingType {
    param($Type)
    if ($null -eq $Type) {
        return "none"
    }
    switch ([int]$Type) {
        0 { return "public" }
        1 { return "private" }
        default { return "unknown_$Type" }
    }
}

"N03_PC_HOSTED_DHCP_PREFLIGHT_BEGIN $(Get-Date -Format o)" | Out-File -LiteralPath $summaryLog -Encoding utf8
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "INTERFACE_ALIAS_ARG=$InterfaceAlias"
Write-SummaryLine "ICS_SERVER_IP=$IcsServerIp"
Write-SummaryLine "STANDALONE_SERVER_IP=$StandaloneServerIp"
Write-SummaryLine "PREFIX_LENGTH=$PrefixLength"
Write-SummaryLine "DHCP_POOL_START=$DhcpPoolStart"
Write-SummaryLine "DHCP_POOL_END=$DhcpPoolEnd"
Write-SummaryLine "TCP_PORT=$TcpPort"
Write-SummaryLine "READ_ONLY=1"
Write-SummaryLine "NO_NETWORK_CONFIG_CHANGE=1"
Write-SummaryLine "NO_DHCP_SERVICE_START=1"
Write-SummaryLine "NO_DHCP_PACKET_INJECTION=1"
Write-SummaryLine "NO_FPGA_PROGRAMMING=1"
Write-SummaryLine "NO_UART_WRITE=1"
Write-SummaryLine "NO_TFDU_DRIVE=1"

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

$selectedIps = @()
$selectedName = "NONE"
$selectedDesc = ""
$selectedStatus = "Missing"
$selectedSpeed = ""
$selectedIfIndex = -1
$selectedIsWifi = $false
$selectedIsEthernet = $false
$linkUp = $false
$icsSubnetPresent = $false
$standaloneSubnetPresent = $false

if ($null -ne $selected) {
    $selectedName = [string]$selected.Name
    $selectedDesc = [string]$selected.InterfaceDescription
    $selectedStatus = [string]$selected.Status
    $selectedSpeed = [string]$selected.LinkSpeed
    $selectedIfIndex = [int]$selected.ifIndex
    $selectedIsWifi = Is-WifiAdapter $selected
    $selectedIsEthernet = Is-EthernetCandidate $selected
    $linkUp = ($selected.Status -eq "Up")
    $selectedIps = @(Get-NetIPAddress -InterfaceIndex $selected.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue)
    foreach ($ip in $selectedIps) {
        if ($ip.IPAddress -eq $IcsServerIp -and [int]$ip.PrefixLength -eq $PrefixLength) {
            $icsSubnetPresent = $true
        }
        if ($ip.IPAddress -eq $StandaloneServerIp -and [int]$ip.PrefixLength -eq $PrefixLength) {
            $standaloneSubnetPresent = $true
        }
    }
}

Write-SummaryLine "SELECTED_ADAPTER=$selectedName"
Write-SummaryLine "SELECTED_ADAPTER_DESC=$selectedDesc"
Write-SummaryLine "SELECTED_ADAPTER_STATUS=$selectedStatus"
Write-SummaryLine "SELECTED_ADAPTER_LINK_SPEED=$selectedSpeed"
Write-SummaryLine "SELECTED_ADAPTER_IFINDEX=$selectedIfIndex"
Write-SummaryLine "SELECTED_ADAPTER_WIFI=$([int]$selectedIsWifi)"
Write-SummaryLine "SELECTED_ADAPTER_ETHERNET_CANDIDATE=$([int]$selectedIsEthernet)"
Write-SummaryLine "PC_ETHERNET_LINK_UP=$([int]$linkUp)"
foreach ($ip in $selectedIps) {
    Write-SummaryLine "SELECTED_IPV4=$($ip.IPAddress)/$($ip.PrefixLength) state=$($ip.AddressState) origin=$($ip.PrefixOrigin)"
}
Write-SummaryLine "ICS_SUBNET_IP_PRESENT=$([int]$icsSubnetPresent)"
Write-SummaryLine "STANDALONE_DHCP_SUBNET_IP_PRESENT=$([int]$standaloneSubnetPresent)"

$icsService = Get-Service -Name "SharedAccess" -ErrorAction SilentlyContinue
$dhcpServerService = Get-Service -Name "DHCPServer" -ErrorAction SilentlyContinue
$icsServiceObject = ConvertTo-ServiceObject $icsService
$dhcpServerServiceObject = ConvertTo-ServiceObject $dhcpServerService
$icsRunning = ($null -ne $icsService -and $icsService.Status -eq "Running")
$dhcpServerRunning = ($null -ne $dhcpServerService -and $dhcpServerService.Status -eq "Running")
Write-SummaryLine "ICS_SERVICE_PRESENT=$([int]($null -ne $icsService))"
Write-SummaryLine "ICS_SERVICE_STATUS=$($icsServiceObject.status)"
Write-SummaryLine "DHCP_SERVER_SERVICE_PRESENT=$([int]($null -ne $dhcpServerService))"
Write-SummaryLine "DHCP_SERVER_SERVICE_STATUS=$($dhcpServerServiceObject.status)"

$icsSharingRows = @()
$icsSharingQueryOk = $false
$icsSharingQueryError = ""
$icsSharingQueryRequiresAdmin = $false
try {
    $shareManager = New-Object -ComObject "HNetCfg.HNetShare"
    $connections = @($shareManager.EnumEveryConnection())
    foreach ($connection in $connections) {
        $props = $null
        $config = $null
        try { $props = $shareManager.NetConnectionProps($connection) } catch { $props = $null }
        try { $config = $shareManager.INetSharingConfigurationForINetConnection($connection) } catch { $config = $null }
        $sharingEnabled = ($null -ne $config -and [bool]$config.SharingEnabled)
        $sharingType = if ($sharingEnabled) { ConvertTo-IcsSharingType $config.SharingConnectionType } else { "none" }
        $name = if ($null -ne $props) { [string]$props.Name } else { "unknown" }
        $device = if ($null -ne $props) { [string]$props.DeviceName } else { "" }
        $guid = if ($null -ne $props) { [string]$props.Guid } else { "" }
        $statusText = if ($null -ne $props) { [string]$props.Status } else { "" }
        $icsSharingRows += [pscustomobject]@{
            name = $name
            device_name = $device
            guid = $guid
            status = $statusText
            sharing_enabled = [bool]$sharingEnabled
            sharing_type = $sharingType
        }
    }
    $icsSharingQueryOk = $true
} catch {
    $icsSharingQueryError = [string]$_.Exception.Message
    $icsSharingQueryRequiresAdmin = ($icsSharingQueryError -match "Access is denied|E_ACCESSDENIED|0x80070005")
}
$icsPrivateRows = @($icsSharingRows | Where-Object { $_.sharing_enabled -and $_.sharing_type -eq "private" })
$icsPublicRows = @($icsSharingRows | Where-Object { $_.sharing_enabled -and $_.sharing_type -eq "public" })
$icsPrivateSelected = @($icsPrivateRows | Where-Object { $_.name -eq $selectedName }).Count -gt 0
Write-SummaryLine "ICS_SHARING_QUERY_OK=$([int]$icsSharingQueryOk)"
Write-SummaryLine "ICS_SHARING_QUERY_REQUIRES_ADMIN=$([int]$icsSharingQueryRequiresAdmin)"
if ($icsSharingQueryError -ne "") { Write-SummaryLine "ICS_SHARING_QUERY_ERROR=$icsSharingQueryError" }
Write-SummaryLine "ICS_SHARING_CONNECTION_COUNT=$($icsSharingRows.Count)"
Write-SummaryLine "ICS_PRIVATE_INTERFACE_SELECTED=$([int]$icsPrivateSelected)"
Write-SummaryLine "ICS_PRIVATE_INTERFACES=$(if ($icsPrivateRows.Count) { ($icsPrivateRows | ForEach-Object { $_.name }) -join ',' } else { 'none' })"
Write-SummaryLine "ICS_PUBLIC_INTERFACES=$(if ($icsPublicRows.Count) { ($icsPublicRows | ForEach-Object { $_.name }) -join ',' } else { 'none' })"
foreach ($row in $icsSharingRows | Where-Object { $_.sharing_enabled }) {
    Write-SummaryLine "ICS_SHARING_ENABLED=$($row.name):$($row.sharing_type):$($row.status)"
}

$udp67Endpoints = @()
try {
    $udp67Endpoints = @(Get-NetUDPEndpoint -LocalPort 67 -ErrorAction SilentlyContinue)
} catch {
    $udp67Endpoints = @()
    Write-SummaryLine "UDP67_QUERY_ERROR=$($_.Exception.Message)"
}
$udp67ProcessRows = @()
foreach ($endpoint in $udp67Endpoints | Select-Object -First 20) {
    $proc = Get-Process -Id $endpoint.OwningProcess -ErrorAction SilentlyContinue
    $procName = if ($null -ne $proc) { [string]$proc.ProcessName } else { "unknown" }
    $udp67ProcessRows += [pscustomobject]@{
        local_address = [string]$endpoint.LocalAddress
        local_port = [int]$endpoint.LocalPort
        owning_process = [int]$endpoint.OwningProcess
        process_name = $procName
    }
    Write-SummaryLine "UDP67_PROCESS=$($endpoint.OwningProcess):$($procName):$($endpoint.LocalAddress):$($endpoint.LocalPort)"
}
Write-SummaryLine "UDP67_LISTENER_COUNT=$($udp67Endpoints.Count)"

$dhcpServerDetected = ($icsRunning -or $dhcpServerRunning -or $udp67Endpoints.Count -gt 0)
$dhcpSubnetReady = ($icsSubnetPresent -or $standaloneSubnetPresent)
$serverReady = ($linkUp -and $selectedIsEthernet -and -not $selectedIsWifi -and $dhcpServerDetected -and $dhcpSubnetReady)

$blockers = [System.Collections.Generic.List[string]]::new()
if ($null -eq $selected) { $blockers.Add("ethernet_adapter_not_found") }
if (-not $selectedIsEthernet -or $selectedIsWifi) { $blockers.Add("selected_adapter_not_wired_ethernet") }
if (-not $linkUp) { $blockers.Add("ethernet_link_not_up") }
if (-not $dhcpServerDetected) { $blockers.Add("no_pc_dhcp_server_detected") }
if (-not $dhcpSubnetReady) { $blockers.Add("no_dhcp_server_subnet_ip_on_selected_adapter") }

$status = "READY_SERVER_PENDING_BOARD_LEASE"
if (-not $serverReady) {
    $status = "DEFERRED_NO_PC_DHCP_SERVER"
}
if ($null -eq $selected) {
    $status = "BLOCKED_ETHERNET_ADAPTER_NOT_FOUND"
} elseif (-not $linkUp) {
    $status = "BLOCKED_ETHERNET_LINK_DOWN"
}

$nextAction = "capture_dhcp_lease_and_tcp_hello"
if (-not $serverReady) {
    if (-not $dhcpServerDetected -and -not $dhcpSubnetReady) {
        $nextAction = "configure_windows_ics_or_standalone_dhcp_server"
    } elseif (-not $dhcpServerDetected) {
        $nextAction = "start_or_configure_pc_dhcp_server"
    } elseif (-not $dhcpSubnetReady) {
        $nextAction = "assign_pc_dhcp_server_subnet_ip"
    } else {
        $nextAction = "clear_preflight_blockers"
    }
}
$standaloneIpCommand = if ($selectedName -ne "NONE") {
    "New-NetIPAddress -InterfaceAlias `"$selectedName`" -IPAddress $StandaloneServerIp -PrefixLength $PrefixLength -SkipAsSource `$false"
} else {
    ""
}

Write-SummaryLine "N03_PC_HOSTED_DHCP_SERVER_DETECTED=$([int]$dhcpServerDetected)"
Write-SummaryLine "N03_PC_HOSTED_DHCP_SERVER_READY=$([int]$serverReady)"
Write-SummaryLine "N03_PC_HOSTED_DHCP_DISCOVER_OBSERVED=0"
Write-SummaryLine "N03_PC_HOSTED_DHCP_OFFER_OBSERVED=0"
Write-SummaryLine "N03_PC_HOSTED_DHCP_REQUEST_OBSERVED=0"
Write-SummaryLine "N03_PC_HOSTED_DHCP_ACK_OBSERVED=0"
Write-SummaryLine "N03_PC_HOSTED_DHCP_LEASE_PASS=0"
foreach ($reason in $blockers) {
    Write-SummaryLine "N03_PC_HOSTED_DHCP_PREFLIGHT_BLOCKER=$reason"
}
Write-SummaryLine "N03_PC_HOSTED_DHCP_NEXT_ACTION=$nextAction"
Write-SummaryLine "N03_PC_HOSTED_DHCP_STANDALONE_IP_COMMAND=$standaloneIpCommand"
Write-SummaryLine "N03_PC_HOSTED_DHCP_ICS_GUI_COMMAND=control.exe ncpa.cpl"
Write-SummaryLine "N03_PC_HOSTED_DHCP_PREFLIGHT_STATUS=$status"
Write-SummaryLine "N03_PC_HOSTED_DHCP_PREFLIGHT_COMPLETE=1"
Write-SummaryLine "N03_PC_HOSTED_DHCP_PREFLIGHT_END $(Get-Date -Format o)"

$payload = [ordered]@{
    generated = (Get-Date -Format o)
    status = $status
    server_ready = [bool]$serverReady
    server_detected = [bool]$dhcpServerDetected
    blockers = @($blockers)
    selected_adapter = ConvertTo-AdapterObject $selected
    ethernet_candidates = @($ethernet | ForEach-Object { ConvertTo-AdapterObject $_ })
    selected_ipv4 = @($selectedIps | ForEach-Object {
        [pscustomobject]@{
            ip_address = [string]$_.IPAddress
            prefix_length = [int]$_.PrefixLength
            address_state = [string]$_.AddressState
            prefix_origin = [string]$_.PrefixOrigin
        }
    })
    expected = [ordered]@{
        ics_server_ip = $IcsServerIp
        standalone_server_ip = $StandaloneServerIp
        prefix_length = $PrefixLength
        dhcp_pool_start = $DhcpPoolStart
        dhcp_pool_end = $DhcpPoolEnd
        tcp_port_after_lease = $TcpPort
    }
    services = [ordered]@{
        shared_access_ics = $icsServiceObject
        dhcp_server = $dhcpServerServiceObject
    }
    ics_sharing = [ordered]@{
        query_ok = [bool]$icsSharingQueryOk
        query_requires_admin = [bool]$icsSharingQueryRequiresAdmin
        query_error = $icsSharingQueryError
        private_interface_selected = [bool]$icsPrivateSelected
        private_interfaces = @($icsPrivateRows | ForEach-Object { $_.name })
        public_interfaces = @($icsPublicRows | ForEach-Object { $_.name })
        connections = $icsSharingRows
    }
    udp67 = $udp67ProcessRows
    next_action = [ordered]@{
        action = $nextAction
        standalone_ip_command = $standaloneIpCommand
        ics_gui_command = "control.exe ncpa.cpl"
    }
    markers = [ordered]@{
        read_only = $true
        no_network_config_change = $true
        no_dhcp_service_start = $true
        no_dhcp_packet_injection = $true
        no_fpga_programming = $true
        no_uart_write = $true
        no_tfdu_drive = $true
        dhcp_discover_observed = $false
        dhcp_offer_observed = $false
        dhcp_request_observed = $false
        dhcp_ack_observed = $false
        pc_hosted_dhcp_lease_pass = $false
    }
}
$payload | ConvertTo-Json -Depth 8 | Out-File -LiteralPath $jsonReport -Encoding utf8

$md = @(
    "# N03 PC-hosted DHCP Preflight",
    "",
    "Generated: $(Get-Date -Format o)",
    "",
    "Verdict: $status",
    "",
    "This helper is read-only. It does not change IP configuration, start DHCP services, inject DHCP packets, program FPGA, write UART, or drive TFDU.",
    "",
    "- Selected adapter: $selectedName",
    "- Adapter status: $selectedStatus",
    "- Adapter link speed: $selectedSpeed",
    "- ICS service status: $($icsServiceObject.status)",
    "- ICS sharing query ok: $icsSharingQueryOk",
    "- ICS sharing query requires admin: $icsSharingQueryRequiresAdmin",
    "- ICS private interface selected: $icsPrivateSelected",
    "- ICS private interfaces: $(if ($icsPrivateRows.Count) { ($icsPrivateRows | ForEach-Object { $_.name }) -join ', ' } else { 'none' })",
    "- ICS public interfaces: $(if ($icsPublicRows.Count) { ($icsPublicRows | ForEach-Object { $_.name }) -join ', ' } else { 'none' })",
    "- DHCP Server service status: $($dhcpServerServiceObject.status)",
    "- UDP 67 listener count: $($udp67Endpoints.Count)",
    "- ICS subnet IP present: $icsSubnetPresent ($IcsServerIp/$PrefixLength)",
    "- Standalone DHCP subnet IP present: $standaloneSubnetPresent ($StandaloneServerIp/$PrefixLength)",
    "- Server detected: $dhcpServerDetected",
    "- Server ready for board lease attempt: $serverReady",
    "- Lease pass: false",
    "- Blockers: $(if ($blockers.Count) { $blockers -join ', ' } else { 'none' })",
    "- Next action: $nextAction",
    "- Standalone server IP command: $standaloneIpCommand",
    "- ICS GUI command: control.exe ncpa.cpl",
    "",
    "Required real N03-7 evidence remains DHCP DISCOVER/OFFER/REQUEST/ACK, a board IP in the configured pool, and a TCP HELLO/STATUS pass to the leased board IP.",
    "",
    "Typical setup choices:",
    "",
    "- Windows ICS: shared adapter usually owns 192.168.137.1/24; use the IP printed by ipconfig and board UART.",
    "- Standalone DHCP server: use 192.168.20.1/24 on the PC Ethernet adapter and pool $DhcpPoolStart-$DhcpPoolEnd.",
    "",
    "- Summary log: $summaryLog",
    "- JSON report: $jsonReport"
)
[System.IO.File]::WriteAllLines($mdReport, [string[]]$md, [System.Text.Encoding]::UTF8)

Copy-Item -LiteralPath $summaryLog -Destination $currentSummary -Force
Copy-Item -LiteralPath $jsonReport -Destination $currentJson -Force
Copy-Item -LiteralPath $mdReport -Destination $currentMd -Force

exit 0
