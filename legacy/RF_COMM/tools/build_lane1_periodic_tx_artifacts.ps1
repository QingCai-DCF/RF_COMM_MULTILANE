[CmdletBinding()]
param(
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$BootgenPath = "D:\Xilinx\Vitis\2023.1\bin\bootgen.bat",
    [int]$Jobs = 16,
    [int]$IntervalUs = 1000000,
    [int]$BGapCycles = 64000000,
    [int]$StageSeconds = 60,
    [switch]$NoRestore,
    [switch]$SkipBootBin
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$reportsDir = Join-Path $repoRoot "reports"
$deliverablesDir = Join-Path $repoRoot "deliverables"
$packageRoot = Join-Path $deliverablesDir "lane1_periodic_tx_programming_artifacts_$stamp"
$evidenceDir = Join-Path $packageRoot "evidence"
$backupRoot = Join-Path $reportsDir "lane1_periodic_tx_artifacts_${stamp}.workspace_backup"
$summaryLog = Join-Path $reportsDir "lane1_periodic_tx_artifacts_${stamp}.summary.txt"

$buildScript = Join-Path $repoRoot "tools\build_g0_lane0_artifacts.ps1"
$bitPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"
$ltxPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.ltx"
$rootBitPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.bit"
$xsaPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.xsa"
$elfPath = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"
$fsblCandidates = @(
    (Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\design_shiboqi_wrapper\export\design_shiboqi_wrapper\sw\design_shiboqi_wrapper\boot\fsbl.elf"),
    (Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\design_shiboqi_wrapper\zynq_fsbl\fsbl.elf"),
    (Join-Path $repoRoot "software\_vitis_ws\design_shiboqi_wrapper\export\design_shiboqi_wrapper\sw\design_shiboqi_wrapper\boot\fsbl.elf"),
    (Join-Path $repoRoot "software\_vitis_ws\design_shiboqi_wrapper\zynq_fsbl\fsbl.elf")
)
$ps7InitPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\ps7_init.tcl"

$backupItems = @(
    "software\_vitis_ws_ps_ps_loopback",
    "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.srcs\sources_1\bd\design_shiboqi",
    "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.gen\sources_1\bd\design_shiboqi",
    "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.ip_user_files\bd\design_shiboqi",
    "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\synth_1",
    "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1",
    "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.bit",
    "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.xsa"
)

function Write-SummaryLine {
    param([string]$Line)
    Write-Host $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Assert-UnderRepo {
    param([string]$Path)
    $full = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $Path))
    $root = [System.IO.Path]::GetFullPath($repoRoot)
    if (-not $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing path outside repo: $full"
    }
    return $full
}

function Copy-PathPreservingRelative {
    param(
        [string]$RelativePath,
        [string]$DestinationRoot
    )
    $src = Assert-UnderRepo -Path $RelativePath
    if (-not (Test-Path -LiteralPath $src)) {
        return
    }
    $dst = Join-Path $DestinationRoot $RelativePath
    $parent = Split-Path -Parent $dst
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $item = Get-Item -LiteralPath $src
    if ($item.PSIsContainer) {
        Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
    } else {
        Copy-Item -LiteralPath $src -Destination $dst -Force
    }
}

function Restore-Backup {
    if ($NoRestore.IsPresent) {
        Write-SummaryLine "WORKSPACE_RESTORE_SKIPPED=1"
        return
    }
    Write-SummaryLine "WORKSPACE_RESTORE_BEGIN=$(Get-Date -Format o)"
    foreach ($rel in $backupItems) {
        $src = Join-Path $backupRoot $rel
        if (-not (Test-Path -LiteralPath $src)) {
            continue
        }
        $dst = Assert-UnderRepo -Path $rel
        $srcItem = Get-Item -LiteralPath $src
        if ($srcItem.PSIsContainer) {
            $removed = $false
            if (Test-Path -LiteralPath $dst) {
                $resolvedDst = (Resolve-Path -LiteralPath $dst).Path
                if (-not $resolvedDst.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                    throw "Refusing recursive delete outside repo: $resolvedDst"
                }
                for ($attempt = 1; $attempt -le 5; $attempt++) {
                    try {
                        Remove-Item -LiteralPath $dst -Recurse -Force -ErrorAction Stop
                        $removed = $true
                        break
                    } catch {
                        Write-SummaryLine "RESTORE_REMOVE_RETRY rel=$rel attempt=$attempt error=$($_.Exception.Message)"
                        Start-Sleep -Milliseconds (300 * $attempt)
                    }
                }
            } else {
                $removed = $true
            }
            if ($removed) {
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
                Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force
            } else {
                Write-SummaryLine "RESTORE_REMOVE_WARN rel=$rel action=overlay_copy"
                New-Item -ItemType Directory -Force -Path $dst | Out-Null
                foreach ($child in Get-ChildItem -LiteralPath $src -Force) {
                    Copy-Item -LiteralPath $child.FullName -Destination (Join-Path $dst $child.Name) -Recurse -Force
                }
            }
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
            Copy-Item -LiteralPath $src -Destination $dst -Force
        }
    }
    Write-SummaryLine "WORKSPACE_RESTORE_END=$(Get-Date -Format o)"
}

function Require-File {
    param(
        [string]$Name,
        [string]$Path
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Name missing: $Path"
    }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -le 0) {
        throw "$Name is empty: $Path"
    }
    return $item
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

function Set-EnvMap {
    param([hashtable]$Map)
    foreach ($key in $Map.Keys) {
        [Environment]::SetEnvironmentVariable($key, [string]$Map[$key], "Process")
    }
}

function New-CommonEnv {
    return @{
        VIVADO_MAX_THREADS = [string]$Jobs
        MAKEFLAGS = "-j$Jobs"
        SKIP_ILA_INSERT = "1"
        IR_B_MODE = "stream_bidir"
        IR_LANE_COUNT = "2"
        IR_CNT_CHIP_MAX = "7"
        IR_CNT_PREAMBLE = "64"
        IR_RX_PREAMBLE_REALIGN_EDGE = "1"
        IR_B_SESSION_ID = "0x2202"
        IR_B_RX_LANE_MASK = "2"
        IR_B_EXPECTED_A_LANE_MASK = "2"
        IR_B_TX_LANE_MASK = "2"
        IR_B_ACK_LANE_MASK = "2"
        IR_B_BACKOFF_SLOT_CYCLES = "1024"
        IR_B_START_IDLE_CYCLES = "100000"
        IR_B_DEBUG_SELECT_RX_STATUS = "2"
        IR_STREAM_PHY_DBG_SELECT = "4"
        PSPS_RUN_ONCE = "0"
        PSPS_WARMUP_STAGES = "0"
        PSPS_STAGE_SECONDS = [string]$StageSeconds
        PSPS_STATS_INTERVAL_US = "10000000"
        PSPS_STAGE_LANE_MASK = "0x2"
        PSPS_STAGE_SESSION_ID = "0x2202"
        PSPS_PAYLOAD_LANE_MASK = "0x2"
        PSPS_RX_LANE_MASK = "0x2"
        PSPS_POLL_SLEEP_US = "100"
        IR_TX_POLL_US = "10"
    }
}

function Get-TargetConfig {
    param([string]$Name)
    $envMap = New-CommonEnv
    if ($Name -eq "A_periodic_tx_lane1") {
        $envMap.IR_MAX_RETRY = "12"
        $envMap.IR_FRAG_TIMEOUT_CYCLES = "120000"
        $envMap.IR_B2A_ENABLE = "0"
        $envMap.IR_B2A_FREE_RUN = "0"
        $envMap.IR_B2A_ECHO_ENABLE = "0"
        $envMap.IR_HW_MAX_PACKET_BYTES = "255"
        $envMap.IR_HW_RX_TRANSFER_BYTES = "255"
        $envMap.PSPS_PAYLOAD_BYTES = "64"
        $envMap.PSPS_TX_ONLY = "1"
        $envMap.PSPS_TDM_BIDIR = "0"
        $envMap.PSPS_RX_ONLY = "0"
        $envMap.PSPS_INTER_PACKET_US = [string]$IntervalUs
        $envMap.PSPS_MAX_OUTSTANDING = "0"
        $envMap.PSPS_WINDOW_START_GAP_US = "0"
        return @{
            Name = $Name
            Variant = "a2b_ack"
            Description = "A endpoint sends lane1 packets periodically"
            Env = $envMap
        }
    }
    if ($Name -eq "B_periodic_tx_lane1") {
        $envMap.IR_MAX_PACKET_BYTES = "252"
        $envMap.IR_FRAGMENT_BYTES = "252"
        $envMap.IR_HW_MAX_PACKET_BYTES = "252"
        $envMap.IR_HW_RX_TRANSFER_BYTES = "252"
        $envMap.IR_B2A_ENABLE = "1"
        $envMap.IR_B2A_FREE_RUN = "1"
        $envMap.IR_B2A_ECHO_ENABLE = "0"
        $envMap.IR_B_TX_GAP_CYCLES = [string]$BGapCycles
        $envMap.PSPS_PAYLOAD_BYTES = "244"
        $envMap.PSPS_TX_ONLY = "0"
        $envMap.PSPS_TDM_BIDIR = "0"
        $envMap.PSPS_RX_ONLY = "1"
        $envMap.PSPS_INTER_PACKET_US = "0"
        $envMap.PSPS_MAX_OUTSTANDING = "0"
        return @{
            Name = $Name
            Variant = "b2a_rx"
            Description = "B endpoint free-runs lane1 packets periodically"
            Env = $envMap
        }
    }
    throw "Unknown target config: $Name"
}

function Write-ProgramTcl {
    param(
        [string]$Dir,
        [string]$Label
    )
    $tcl = @"
# XSCT script: program this RF_COMM lane1 periodic TX artifact.
#
# Usage:
#   D:/Xilinx/Vitis/2023.1/bin/xsct.bat program_this_artifact.tcl localhost:3121
#   D:/Xilinx/Vitis/2023.1/bin/xsct.bat program_this_artifact.tcl TCP:localhost:3121

set script_dir [file dirname [file normalize [info script]]]
set bit_file  [file join `$script_dir "design_shiboqi_wrapper.bit"]
set elf_file  [file join `$script_dir "rf_comm_ps_ps_loopback.elf"]
set init_file [file join `$script_dir "ps7_init.tcl"]

foreach f [list `$bit_file `$elf_file `$init_file] {
    if {![file exists `$f]} {
        error "Required file is missing: `$f"
    }
}

puts "RF_COMM lane1 periodic TX artifact programming: $Label"
puts "  bit:  `$bit_file"
puts "  elf:  `$elf_file"
puts "  init: `$init_file"

if {[llength `$argv] > 0} {
    set hw_url [lindex `$argv 0]
    if {![regexp -nocase {^TCP:} `$hw_url]} {
        set hw_url "TCP:`$hw_url"
    }
    puts "Connecting to hw_server: `$hw_url"
    connect -url `$hw_url
} else {
    puts "Connecting to default hw_server"
    connect
}

after 1000

puts "Resetting PS system"
targets -set -filter {name =~ "APU*"}
rst -system
after 3000

puts "Programming FPGA SRAM"
targets -set -filter {name =~ "xc7z*"}
fpga -file `$bit_file
after 1000

puts "Running PS7 init"
targets -set -filter {name =~ "APU*"}
source `$init_file
ps7_init
ps7_post_config

puts "Downloading and starting ELF"
targets -set -filter {name =~ "*Cortex-A9*#0"}
rst -processor
after 1000
dow `$elf_file
con

puts "RF_COMM_ARTIFACT_PROGRAMMED_AND_ELF_STARTED"
"@
    $path = Join-Path $Dir "program_this_artifact.tcl"
    Set-Content -LiteralPath $path -Value $tcl -Encoding ascii
}

function New-BootBin {
    param([string]$Dir)
    if ($SkipBootBin.IsPresent) {
        return "SKIPPED"
    }
    if (-not (Test-Path -LiteralPath $BootgenPath)) {
        return "BOOTGEN_MISSING"
    }
    $fsbl = Join-Path $Dir "fsbl.elf"
    $bit = Join-Path $Dir "design_shiboqi_wrapper.bit"
    $elf = Join-Path $Dir "rf_comm_ps_ps_loopback.elf"
    $bif = Join-Path $Dir "rf_comm_lane1_periodic_tx.bif"
    $boot = Join-Path $Dir "BOOT.BIN"
    $bifText = @"
the_ROM_image:
{
  [bootloader] $fsbl
  $bit
  $elf
}
"@
    Set-Content -LiteralPath $bif -Value $bifText -Encoding ascii
    $bootOut = & $BootgenPath -image $bif -arch zynq -o $boot -w on 2>&1
    $bootOut | Set-Content -LiteralPath (Join-Path $Dir "bootgen.log") -Encoding ascii
    if ($LASTEXITCODE -ne 0 -or ($bootOut -match "^\[ERROR\]")) {
        return "BOOTGEN_FAIL"
    }
    return "PASS"
}

function Package-CurrentArtifacts {
    param([hashtable]$Config)
    $name = [string]$Config.Name
    $targetDir = Join-Path $packageRoot $name
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

    $fsbl = Get-FirstExisting -Paths $fsblCandidates
    if ($null -eq $fsbl) {
        throw "FSBL missing after build"
    }

    Require-File -Name "bit" -Path $bitPath | Out-Null
    Require-File -Name "root bit copy" -Path $rootBitPath | Out-Null
    Require-File -Name "xsa" -Path $xsaPath | Out-Null
    Require-File -Name "elf" -Path $elfPath | Out-Null
    Require-File -Name "fsbl" -Path $fsbl | Out-Null
    Require-File -Name "ps7_init" -Path $ps7InitPath | Out-Null

    Copy-Item -LiteralPath $bitPath -Destination (Join-Path $targetDir "design_shiboqi_wrapper.bit") -Force
    Copy-Item -LiteralPath $xsaPath -Destination (Join-Path $targetDir "design_shiboqi_wrapper.xsa") -Force
    Copy-Item -LiteralPath $elfPath -Destination (Join-Path $targetDir "rf_comm_ps_ps_loopback.elf") -Force
    Copy-Item -LiteralPath $fsbl -Destination (Join-Path $targetDir "fsbl.elf") -Force
    Copy-Item -LiteralPath $ps7InitPath -Destination (Join-Path $targetDir "ps7_init.tcl") -Force
    Write-ProgramTcl -Dir $targetDir -Label $name

    $bootResult = New-BootBin -Dir $targetDir

    $manifest = [ordered]@{
        schema = "rf_comm_lane1_periodic_tx_artifact_v1"
        generated_at = (Get-Date).ToString("o")
        name = $name
        description = $Config.Description
        physical_lane = 1
        lane_mask = "0x2"
        session_id = "0x2202"
        interval_us = $IntervalUs
        b_gap_cycles = $BGapCycles
        stage_seconds = $StageSeconds
        variant = $Config.Variant
        boot_bin_result = $bootResult
        known_boundary = "Lane1 existing P7A evidence showed far-end raw RX absent; this artifact is a periodic TX stimulus, not a lane1 connectivity PASS."
        env = $Config.Env
        files = @{}
    }
    foreach ($file in Get-ChildItem -LiteralPath $targetDir -File) {
        $manifest.files[$file.Name] = [ordered]@{
            bytes = $file.Length
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash
        }
    }
    $manifestPath = Join-Path $targetDir "artifact_manifest.json"
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding ascii

    Write-SummaryLine "PACKAGE_TARGET=$name"
    Write-SummaryLine "PACKAGE_DIR=$targetDir"
    Write-SummaryLine "PACKAGE_BOOT_BIN_RESULT=$bootResult"
    Write-SummaryLine "PACKAGE_BIT_SHA256=$((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $targetDir 'design_shiboqi_wrapper.bit')).Hash)"
    Write-SummaryLine "PACKAGE_ELF_SHA256=$((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $targetDir 'rf_comm_ps_ps_loopback.elf')).Hash)"
    if (Test-Path -LiteralPath (Join-Path $targetDir "BOOT.BIN")) {
        Write-SummaryLine "PACKAGE_BOOT_BIN_SHA256=$((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $targetDir 'BOOT.BIN')).Hash)"
    }
}

function Invoke-TargetBuild {
    param([hashtable]$Config)
    Write-SummaryLine "BUILD_TARGET_BEGIN=$($Config.Name) time=$(Get-Date -Format o)"
    $buildStart = Get-Date
    foreach ($key in ($Config.Env.Keys | Sort-Object)) {
        Write-SummaryLine "BUILD_ENV target=$($Config.Name) $key=$($Config.Env[$key])"
    }
    Set-EnvMap -Map $Config.Env
    $buildOut = Join-Path $reportsDir "lane1_periodic_tx_$($Config.Name)_${stamp}.build.out.log"
    $buildErr = Join-Path $reportsDir "lane1_periodic_tx_$($Config.Name)_${stamp}.build.err.log"
    $args = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $buildScript,
        "-VivadoPath",
        $VivadoPath,
        "-XsctPath",
        $XsctPath,
        "-Variant",
        $Config.Variant,
        "-Jobs",
        [string]$Jobs,
        "-FullBdGenerate"
    )
    Write-SummaryLine "BUILD_STDOUT target=$($Config.Name) $buildOut"
    Write-SummaryLine "BUILD_STDERR target=$($Config.Name) $buildErr"
    $proc = Start-Process -FilePath "powershell.exe" `
        -ArgumentList $args `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $buildOut `
        -RedirectStandardError $buildErr `
        -WindowStyle Hidden `
        -PassThru
    $proc.WaitForExit()
    $proc.Refresh()
    $exitCode = $proc.ExitCode
    if ($null -eq $exitCode -or [string]$exitCode -eq "") {
        $candidate = Get-ChildItem -LiteralPath $reportsDir -Filter "g0_lane0_build_*.summary.txt" |
            Where-Object { $_.LastWriteTime -ge $buildStart.AddSeconds(-5) } |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if ($null -ne $candidate) {
            $candidateText = Get-Content -LiteralPath $candidate.FullName -Raw -ErrorAction SilentlyContinue
            if ($candidateText -match "G0_LANE0_BUILD_DONE=1" -and $candidateText -match "VARIANT=$($Config.Variant)") {
                $exitCode = 0
                Write-SummaryLine "BUILD_EXIT_INFERRED target=$($Config.Name) summary=$($candidate.FullName)"
            }
        }
    }
    Write-SummaryLine "BUILD_EXIT target=$($Config.Name) exit=$exitCode"
    if ($exitCode -ne 0) {
        throw "Build failed for $($Config.Name) with exit code $exitCode"
    }
    Write-SummaryLine "BUILD_TARGET_DONE=$($Config.Name) time=$(Get-Date -Format o)"
    Package-CurrentArtifacts -Config $Config
}

New-Item -ItemType Directory -Force -Path $reportsDir, $deliverablesDir, $packageRoot, $evidenceDir, $backupRoot | Out-Null
"LANE1_PERIODIC_TX_ARTIFACTS_BEGIN $(Get-Date -Format o)" | Set-Content -LiteralPath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "PACKAGE_ROOT=$packageRoot"
Write-SummaryLine "BACKUP_ROOT=$backupRoot"
Write-SummaryLine "INTERVAL_US=$IntervalUs"
Write-SummaryLine "B_GAP_CYCLES=$BGapCycles"
Write-SummaryLine "STAGE_SECONDS=$StageSeconds"

foreach ($path in @($VivadoPath, $XsctPath, $buildScript, $ps7InitPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path missing: $path"
    }
}

Write-SummaryLine "WORKSPACE_BACKUP_BEGIN=$(Get-Date -Format o)"
foreach ($rel in $backupItems) {
    Copy-PathPreservingRelative -RelativePath $rel -DestinationRoot $backupRoot
}
Write-SummaryLine "WORKSPACE_BACKUP_END=$(Get-Date -Format o)"

try {
    Invoke-TargetBuild -Config (Get-TargetConfig -Name "A_periodic_tx_lane1")
    Invoke-TargetBuild -Config (Get-TargetConfig -Name "B_periodic_tx_lane1")

    Copy-Item -LiteralPath $summaryLog -Destination (Join-Path $evidenceDir (Split-Path -Leaf $summaryLog)) -Force

    $readmeTemplate = @'
# RF_COMM lane1 periodic TX programming artifacts

Generated: __STAMP__

This package contains two lane1 periodic-transmit artifacts:

- `A_periodic_tx_lane1`: A endpoint sends lane1 packets periodically.
- `B_periodic_tx_lane1`: B endpoint free-runs lane1 packets periodically.

Default interval:

- A sender: `PSPS_INTER_PACKET_US=__INTERVAL_US__`.
- B sender: `IR_B_TX_GAP_CYCLES=__B_GAP_CYCLES__`.

The artifacts include JTAG programming files (`design_shiboqi_wrapper.bit`,
`rf_comm_ps_ps_loopback.elf`, `ps7_init.tcl`, and `program_this_artifact.tcl`).
When bootgen succeeds, each folder also contains `BOOT.BIN` for SD-card boot.

Program over JTAG from the repository root:

```powershell
D:\Xilinx\Vitis\2023.1\bin\xsct.bat .\deliverables\lane1_periodic_tx_programming_artifacts___STAMP__\A_periodic_tx_lane1\program_this_artifact.tcl localhost:3121
D:\Xilinx\Vitis\2023.1\bin\xsct.bat .\deliverables\lane1_periodic_tx_programming_artifacts___STAMP__\B_periodic_tx_lane1\program_this_artifact.tcl localhost:3121
```

After a manual JTAG run, return the TFDU pins to shutdown:

```powershell
D:\Xilinx\Vivado\2023.1\bin\vivado.bat -mode batch -source .\tools\program_tfdu_shutdown.tcl
```

Boundary: existing P7A lane1 evidence showed far-end raw RX absent. These files
are TX stimulus artifacts for lane1 physical/debug work, not a connectivity PASS.
'@
    $readme = $readmeTemplate.
        Replace("__STAMP__", $stamp).
        Replace("__INTERVAL_US__", [string]$IntervalUs).
        Replace("__B_GAP_CYCLES__", [string]$BGapCycles)
    Set-Content -LiteralPath (Join-Path $packageRoot "README.md") -Value $readme -Encoding ascii

    $shaLines = foreach ($file in Get-ChildItem -LiteralPath $packageRoot -Recurse -File) {
        $rel = $file.FullName.Substring($packageRoot.Length + 1).Replace("\", "/")
        "{0}  {1}" -f (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash, $rel
    }
    $shaLines | Set-Content -LiteralPath (Join-Path $packageRoot "SHA256SUMS.txt") -Encoding ascii

    $zipPath = "$packageRoot.zip"
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -Force
    if (-not (Test-Path -LiteralPath $zipPath -PathType Leaf)) {
        throw "ZIP_CREATE_FAILED path=$zipPath"
    }
    Write-SummaryLine "PACKAGE_ZIP=$zipPath"
    Write-SummaryLine "PACKAGE_ZIP_SHA256=$((Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash)"
    Write-SummaryLine "LANE1_PERIODIC_TX_ARTIFACTS_RESULT=PASS"
} finally {
    Restore-Backup
    Write-SummaryLine "LANE1_PERIODIC_TX_ARTIFACTS_END $(Get-Date -Format o)"
}
