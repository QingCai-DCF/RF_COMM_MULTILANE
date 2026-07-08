[CmdletBinding()]
param(
    [string]$InterfaceAlias = "",
    [string]$ExpectedPcIp = "192.168.10.1",
    [int]$PrefixLength = 24,
    [string]$TargetHost = "192.168.10.2",
    [int]$Port = 5001,
    [int]$TimeoutMs = 3000,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$setupScript = Join-Path $scriptDir "setup_n03_static_direct_network_safe.ps1"

function Test-IsAdministrator {
    $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-IsWifiAdapter {
    param($Adapter)
    $joined = ("{0} {1}" -f $Adapter.Name, $Adapter.InterfaceDescription).ToLowerInvariant()
    return ($joined -match "wi-fi|wifi|wireless|wlan|802\.11")
}

function Test-IsEthernetCandidate {
    param($Adapter)
    if (Test-IsWifiAdapter $Adapter) {
        return $false
    }
    $joined = ("{0} {1}" -f $Adapter.Name, $Adapter.InterfaceDescription).ToLowerInvariant()
    return ($joined -match "ethernet|realtek|gbe|2\.5gbe|lan")
}

Write-Host "N03_STATIC_DIRECT_ADMIN_APPLY_ENTRY=1"
Write-Host "REPO_ROOT=$repoRoot"
Write-Host "EXPECTED_PC_IP=$ExpectedPcIp"
Write-Host "PREFIX_LENGTH=$PrefixLength"
Write-Host "TARGET_HOST=$TargetHost"
Write-Host "PORT=$Port"
Write-Host "TIMEOUT_MS=$TimeoutMs"
Write-Host "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-Host "NO_FPGA_PROGRAMMING=1"
Write-Host "NO_UART_WRITE=1"
Write-Host "NO_TFDU_DRIVE=1"
Write-Host "NO_TCP_PAYLOAD=1"

if (-not (Test-Path -LiteralPath $setupScript)) {
    throw "Required setup script is missing: $setupScript"
}

if ($InterfaceAlias -eq "") {
    $adapters = @(Get-NetAdapter -Physical -ErrorAction SilentlyContinue)
    $selected = $adapters |
        Where-Object { Test-IsEthernetCandidate $_ } |
        Sort-Object -Property @{ Expression = { if ($_.Status -eq "Up") { 0 } else { 1 } } }, Name |
        Select-Object -First 1
    if ($null -eq $selected) {
        Write-Host "SELECTED_ADAPTER=NONE"
        Write-Host "N03_STATIC_DIRECT_ADMIN_APPLY_ENTRY_PASS=0"
        Write-Host "N03_STATIC_DIRECT_ADMIN_APPLY_BLOCKER=ethernet_adapter_not_found"
        exit 20
    }
    $InterfaceAlias = [string]$selected.Name
}

$isAdmin = Test-IsAdministrator
Write-Host "IS_ADMIN=$([int]$isAdmin)"
Write-Host "SELECTED_ADAPTER=$InterfaceAlias"

if (-not $isAdmin -and -not $DryRun) {
    Write-Host "ADMIN_REQUIRED=1"
    Write-Host "N03_STATIC_DIRECT_ADMIN_APPLY_ENTRY_PASS=0"
    Write-Host "N03_STATIC_DIRECT_ADMIN_APPLY_BLOCKER=run_from_administrator_powershell"
    exit 20
}

$setupArgs = @{
    InterfaceAlias = $InterfaceAlias
    ExpectedPcIp = $ExpectedPcIp
    PrefixLength = $PrefixLength
    TargetHost = $TargetHost
    Port = $Port
    TimeoutMs = $TimeoutMs
    Apply = $true
    AddFirewallRule = $true
}
if ($DryRun) {
    $setupArgs["DryRun"] = $true
}

& $setupScript @setupArgs
$setupExit = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
Write-Host "N03_STATIC_DIRECT_ADMIN_APPLY_ENTRY_EXIT=$setupExit"
Write-Host "N03_STATIC_DIRECT_ADMIN_APPLY_ENTRY_PASS=$([int]($setupExit -eq 0))"
exit $setupExit
