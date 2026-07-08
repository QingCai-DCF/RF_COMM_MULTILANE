[CmdletBinding()]
param(
    [int]$Jobs = 16,
    [string]$VivadoBin = "D:\Xilinx\Vivado\2023.1\bin",
    [string]$ExpectedConstraintHash = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11",
    [switch]$SkipHostTests
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$constraintFileName = (-join @(
    [char]0x9879,
    [char]0x76EE,
    [char]0x7EA6,
    [char]0x675F,
    [char]0x0028,
    [char]0x76EE,
    [char]0x6807,
    [char]0xFF09
)) + ".txt"
$failures = New-Object System.Collections.Generic.List[string]

function Write-SimPass {
    param([string]$Name, [string]$Detail = "")
    if ($Detail -eq "") {
        Write-Host "[PASS] $Name"
    } else {
        Write-Host "[PASS] $Name - $Detail"
    }
}

function Write-SimFail {
    param([string]$Name, [string]$Detail)
    $failures.Add("${Name}: $Detail") | Out-Null
    Write-Host "[FAIL] $Name - $Detail"
}

function Invoke-SimProcess {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$FilePath,
        [string[]]$Arguments
    )

    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            Write-SimFail $Name "exit code $LASTEXITCODE"
        } else {
            Write-SimPass $Name
        }
    } finally {
        Pop-Location
    }
}

try {
    $proc = [System.Diagnostics.Process]::GetCurrentProcess()
    $proc.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::High
    $proc.ProcessorAffinity = [IntPtr]65535
    Write-Host "[INFO] process - priority=$($proc.PriorityClass) affinity=$($proc.ProcessorAffinity)"
} catch {
    Write-Host "[INFO] process - could not set priority/affinity: $($_.Exception.Message)"
}

Write-Host "[INFO] repo - $repoRoot"

foreach ($path in @(
    (Join-Path (Join-Path $env:USERPROFILE "Desktop") $constraintFileName),
    (Join-Path $repoRoot $constraintFileName)
)) {
    if (-not (Test-Path -LiteralPath $path)) {
        Write-SimFail "constraint_hash" "missing $path"
        continue
    }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
    if ($hash -ne $ExpectedConstraintHash) {
        Write-SimFail "constraint_hash" "$path hash=$hash expected=$ExpectedConstraintHash"
    } else {
        Write-SimPass "constraint_hash" $path
    }
}

$simScript = Join-Path $repoRoot "IPs\ip_ir_array\run_loopback_single_lane.ps1"
Invoke-SimProcess "rtl_xsim_suite" (Split-Path -Parent $simScript) "powershell" @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $simScript,
    "-VivadoBin", $VivadoBin, "-Test", "all", "-Jobs", [string]$Jobs
)

if (-not $SkipHostTests) {
    $psBridgeDir = Join-Path $repoRoot "software\ps_lwip_bridge"
    Invoke-SimProcess "ps_bridge_static_checks" $psBridgeDir "python" @(
        "check_ps_bridge_static.py"
    )

    $hostDir = Join-Path $repoRoot "software\host_client"
    Invoke-SimProcess "host_py_compile" $hostDir "python" @(
        "-m", "py_compile", "rf_comm_client.py", "analyze_acceptance_log.py", "mock_rfcm_server.py", "test_rf_comm_client.py"
    )
    Invoke-SimProcess "host_mock_protocol_tests" $hostDir "python" @(
        "-m", "unittest", "test_rf_comm_client.py", "-v"
    )
    Invoke-SimProcess "host_offline_acceptance" $hostDir "powershell" @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "run_acceptance.ps1",
        "-Mode", "offline_mock",
        "-Repeat", "8",
        "-PayloadSize", "32",
        "-ReconnectCycles", "2",
        "-TimeoutSeconds", "2",
        "-AckTimeoutSeconds", "2"
    )
} else {
    Write-Host "[INFO] host_mock_protocol_tests - skipped"
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "RF_COMM_SIMULATION_GATES_FAIL"
    foreach ($failure in $failures) {
        Write-Host " - $failure"
    }
    exit 1
}

Write-Host ""
Write-Host "RF_COMM_SIMULATION_GATES_PASS"
exit 0
