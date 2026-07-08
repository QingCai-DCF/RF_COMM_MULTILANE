[CmdletBinding()]
param(
    [int]$Jobs = 16,
    [switch]$SkipLoopbackSim,
    [switch]$SkipHostTests,
    [switch]$RunVitisBuild,
    [switch]$RunBootImageBuild,
    [switch]$RunHwCheck,
    [switch]$SkipPythonCacheClean,
    [string]$VivadoBat = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctBat = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$ExpectedConstraintHash = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$failures = New-Object System.Collections.Generic.List[string]
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

function Write-GatePass {
    param([string]$Name, [string]$Detail = "")
    if ($Detail -eq "") {
        Write-Host "[PASS] $Name"
    } else {
        Write-Host "[PASS] $Name - $Detail"
    }
}

function Write-GateFail {
    param([string]$Name, [string]$Detail)
    $failures.Add("${Name}: $Detail") | Out-Null
    Write-Host "[FAIL] $Name - $Detail"
}

function Write-GateInfo {
    param([string]$Name, [string]$Detail)
    Write-Host "[INFO] $Name - $Detail"
}

function Invoke-GateProcess {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [string]$FilePath,
        [string[]]$Arguments
    )

    $display = @($FilePath) + $Arguments
    Write-GateInfo $Name ("running: " + ($display -join " "))
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            Write-GateFail $Name "exit code $LASTEXITCODE"
        } else {
            Write-GatePass $Name
        }
    } finally {
        Pop-Location
    }
}

function Check-ConstraintHash {
    $paths = @(
        (Join-Path (Join-Path $env:USERPROFILE "Desktop") $constraintFileName),
        (Join-Path $repoRoot $constraintFileName)
    )

    foreach ($path in $paths) {
        if (-not (Test-Path -LiteralPath $path)) {
            Write-GateFail "constraint_hash" "missing $path"
            continue
        }
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
        if ($hash -ne $ExpectedConstraintHash) {
            Write-GateFail "constraint_hash" "$path hash=$hash expected=$ExpectedConstraintHash"
        } else {
            Write-GatePass "constraint_hash" "$path"
        }
    }
}

function Check-FilePresent {
    param([string]$Name, [string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-GateFail $Name "missing $Path"
        return
    }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -le 0) {
        Write-GateFail $Name "$Path is empty"
        return
    }
    Write-GatePass $Name ("{0} bytes, {1}" -f $item.Length, $item.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
}

function Get-FirstExisting {
    param([string[]]$Paths)
    foreach ($path in $Paths) {
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }
    return $null
}

function Check-BootImage {
    $bootBin = Join-Path $repoRoot "software\_boot\BOOT.BIN"
    $fsblCandidates = @(
        (Join-Path $repoRoot "software\_vitis_ws\design_shiboqi_wrapper\export\design_shiboqi_wrapper\sw\design_shiboqi_wrapper\boot\fsbl.elf"),
        (Join-Path $repoRoot "software\_vitis_ws\design_shiboqi_wrapper\zynq_fsbl\fsbl.elf")
    )
    $bitCandidates = @(
        (Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"),
        (Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.bit")
    )
    $appElf = Join-Path $repoRoot "software\_vitis_ws\rf_comm_ps_bridge\Debug\rf_comm_ps_bridge.elf"

    if (-not (Test-Path -LiteralPath $bootBin)) {
        Write-GateFail "boot_bin" "missing $bootBin; run .\tools\build_boot_image.ps1"
        return
    }

    $fsbl = Get-FirstExisting $fsblCandidates
    if ($null -eq $fsbl) {
        Write-GateFail "boot_bin" "FSBL missing; run Vitis build"
        return
    }
    $bitFile = Get-FirstExisting $bitCandidates
    if ($null -eq $bitFile) {
        Write-GateFail "boot_bin" "bitstream input missing; expected one of: $($bitCandidates -join ', ')"
        return
    }

    $inputPaths = @($fsbl, $bitFile, $appElf)
    foreach ($path in $inputPaths) {
        if (-not (Test-Path -LiteralPath $path)) {
            Write-GateFail "boot_bin" "input missing: $path"
            return
        }
    }

    $bootItem = Get-Item -LiteralPath $bootBin
    $newerInput = $inputPaths | ForEach-Object { Get-Item -LiteralPath $_ } |
        Where-Object { $_.LastWriteTime -gt $bootItem.LastWriteTime } |
        Select-Object -First 1

    if ($null -ne $newerInput) {
        Write-GateFail "boot_bin" "stale; newer input is $($newerInput.FullName)"
        return
    }

    Write-GatePass "boot_bin" ("{0} bytes, {1}" -f $bootItem.Length, $bootItem.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
}

function Check-LogsClean {
    $paths = @(
        (Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\synth_1\runme.log"),
        (Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\runme.log"),
        (Join-Path $repoRoot "TFDU_VFIR_Client_Array\vivado.log")
    )

    foreach ($path in $paths) {
        if (-not (Test-Path -LiteralPath $path)) {
            Write-GateFail "vivado_log" "missing $path"
            continue
        }
        $matches = Select-String -LiteralPath $path -Pattern "(^\s*(CRITICAL WARNING|ERROR):)|REQP-1840|Timing constraints are not met" -CaseSensitive:$false
        if ($matches) {
            foreach ($match in $matches) {
                Write-GateFail "vivado_log" "${path}:$($match.LineNumber): $($match.Line.Trim())"
            }
        } else {
            Write-GatePass "vivado_log" $path
        }
    }
}

function Check-TimingReport {
    $path = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\timing_summary_post_route.rpt"
    if (-not (Test-Path -LiteralPath $path)) {
        Write-GateFail "timing" "missing $path"
        return
    }

    $lines = Get-Content -LiteralPath $path
    $summaryLine = $lines | Where-Object {
        $_ -match "^\s*-?\d+\.\d+\s+-?\d+\.\d+\s+\d+\s+\d+\s+-?\d+\.\d+\s+-?\d+\.\d+\s+\d+\s+\d+"
    } | Select-Object -First 1

    if (-not $summaryLine) {
        Write-GateFail "timing" "could not parse timing summary"
        return
    }

    $values = $summaryLine.Trim() -split "\s+"
    $wns = [double]$values[0]
    $tnsFail = [int]$values[2]
    $whs = [double]$values[4]
    $thsFail = [int]$values[6]
    $met = ($lines -match "All user specified timing constraints are met.").Count -gt 0

    if ($wns -ge 0.0 -and $whs -ge 0.0 -and $tnsFail -eq 0 -and $thsFail -eq 0 -and $met) {
        Write-GatePass "timing" "WNS=$wns WHS=$whs setup_fail=$tnsFail hold_fail=$thsFail"
    } else {
        Write-GateFail "timing" "WNS=$wns WHS=$whs setup_fail=$tnsFail hold_fail=$thsFail met=$met"
    }
}

function Check-UtilizationReport {
    $path = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\utilization_post_route.rpt"
    if (-not (Test-Path -LiteralPath $path)) {
        Write-GateFail "utilization" "missing $path"
        return
    }

    $content = Get-Content -LiteralPath $path
    $summary = @{}
    foreach ($line in $content) {
        if ($line -notmatch "^\s*\|") {
            continue
        }

        $cells = @($line -split "\|" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
        if ($cells.Count -lt 6) {
            continue
        }

        $percent = $cells[$cells.Count - 1]
        switch ($cells[0]) {
            "Slice LUTs" { $summary["LUT"] = $percent }
            "Slice Registers" { $summary["FF"] = $percent }
            "Block RAM Tile" { $summary["BRAM"] = $percent }
            "DSPs" { $summary["DSP"] = $percent }
        }
    }

    if ($summary.Count -lt 4) {
        Write-GateFail "utilization" "could not parse utilization summary"
        return
    }

    $detail = "LUT={0}% FF={1}% BRAM={2}% DSP={3}%" -f $summary["LUT"], $summary["FF"], $summary["BRAM"], $summary["DSP"]
    Write-GatePass "utilization" $detail
}

function Clean-PythonCache {
    if ($SkipPythonCacheClean) {
        Write-GateInfo "python_cache" "skipped"
        return
    }

    $cacheDirs = Get-ChildItem -LiteralPath $repoRoot -Recurse -Directory -Filter "__pycache__"
    foreach ($dir in $cacheDirs) {
        $resolved = (Resolve-Path -LiteralPath $dir.FullName).Path
        if (-not $resolved.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-GateFail "python_cache" "refusing to remove outside repo: $resolved"
            continue
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
        Write-GatePass "python_cache" "removed $resolved"
    }
    if (-not $cacheDirs) {
        Write-GatePass "python_cache" "no cache directories"
    }
}

try {
    $proc = [System.Diagnostics.Process]::GetCurrentProcess()
    $proc.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::High
    $proc.ProcessorAffinity = [IntPtr]65535
    Write-GateInfo "process" "priority=$($proc.PriorityClass) affinity=$($proc.ProcessorAffinity)"
} catch {
    Write-GateInfo "process" "could not set priority/affinity: $($_.Exception.Message)"
}

Write-GateInfo "repo" $repoRoot

Check-ConstraintHash

$bitstreamPath = Get-FirstExisting @(
    (Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"),
    (Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.bit")
)
if ($null -eq $bitstreamPath) {
    Check-FilePresent "bitstream" (Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit")
} else {
    Check-FilePresent "bitstream" $bitstreamPath
}
Check-FilePresent "xsa" (Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.xsa")
Check-FilePresent "ps_elf" (Join-Path $repoRoot "software\_vitis_ws\rf_comm_ps_bridge\Debug\rf_comm_ps_bridge.elf")

Check-TimingReport
Check-UtilizationReport
Check-LogsClean

if (-not $SkipLoopbackSim) {
    $simScript = Join-Path $repoRoot "IPs\ip_ir_array\run_loopback_single_lane.ps1"
    Invoke-GateProcess "rtl_loopback_sim" (Split-Path -Parent $simScript) "powershell" @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $simScript, "-Test", "all", "-Jobs", [string]$Jobs
    )
} else {
    Write-GateInfo "rtl_loopback_sim" "skipped"
}

if (-not $SkipHostTests) {
    $hostDir = Join-Path $repoRoot "software\host_client"
    Invoke-GateProcess "host_py_compile" $hostDir "python" @(
        "-m", "py_compile", "rf_comm_client.py", "analyze_acceptance_log.py", "mock_rfcm_server.py", "test_rf_comm_client.py"
    )
    Invoke-GateProcess "host_unittest" $hostDir "python" @("-m", "unittest", "test_rf_comm_client.py", "-v")
    Invoke-GateProcess "host_offline_acceptance" $hostDir "powershell" @(
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
    Write-GateInfo "host_tests" "skipped"
}

if ($RunVitisBuild) {
    $buildScript = Join-Path $repoRoot "software\ps_lwip_bridge\build_vitis.tcl"
    $env:MAKEFLAGS = "-j$Jobs"
    Invoke-GateProcess "vitis_build" (Split-Path -Parent $buildScript) $XsctBat @($buildScript)
} else {
    Write-GateInfo "vitis_build" "skipped"
}

if ($RunBootImageBuild -or $RunVitisBuild) {
    $bootScript = Join-Path $repoRoot "tools\build_boot_image.ps1"
    Invoke-GateProcess "boot_image_build" $repoRoot "powershell" @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $bootScript, "-Jobs", [string]$Jobs, "-Force"
    )
} else {
    Write-GateInfo "boot_image_build" "skipped"
}

Check-BootImage

if ($RunHwCheck) {
    $hwScript = Join-Path $repoRoot "tools\hw_check.tcl"
    $output = & $VivadoBat -mode batch -notrace -source $hwScript 2>&1
    $output | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        Write-GateFail "hw_check" "Vivado exit code $LASTEXITCODE"
    } elseif ($output -match "HW_STATUS HW_DEVICE_FOUND") {
        Write-GatePass "hw_check" "hardware device found"
    } elseif ($output -match "HW_STATUS NO_HW_TARGET|HW_STATUS NO_HW_DEVICE") {
        Write-GateFail "hw_check" "no JTAG target/device"
    } else {
        Write-GateFail "hw_check" "could not determine hardware status"
    }
} else {
    Write-GateInfo "hw_check" "skipped"
}

Clean-PythonCache

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "RF_COMM_PROJECT_GATES_FAIL"
    foreach ($failure in $failures) {
        Write-Host " - $failure"
    }
    exit 1
}

Write-Host ""
Write-Host "RF_COMM_PROJECT_GATES_PASS"
exit 0
