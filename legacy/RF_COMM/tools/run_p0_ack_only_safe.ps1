param(
    [ValidateSet("lane0", "lane1", "two_lane")]
    [string]$Mode = "lane0",
    [string]$ComPort = "COM3",
    [int]$BaudRate = 115200,
    [string]$VivadoPath = "D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
    [string]$XsctPath = "D:\Xilinx\Vitis\2023.1\bin\xsct.bat",
    [string]$HwServerUrl = "localhost:3121",
    [int]$JtagFrequencyHz = 1000000,
    [int]$PerRunTimeoutSeconds = 300,
    [int]$MaxTfduWindowSeconds = 300,
    [string]$RxEvidencePath = "",
    [switch]$AllowWithoutRxPass,
    [switch]$DryRun,
    [switch]$AllowArtifactMismatch,
    [switch]$StopOnFail
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$stamp = "{0}_{1}" -f (Get-Date -Format "yyyyMMdd_HHmmss_fff"), $PID
$summaryLog = Join-Path $reportsDir "p0_ack_only_safe_$stamp.summary.txt"
$preflightLog = Join-Path $reportsDir "p0_ack_only_safe_$stamp.preflight.log"
$matrixLog = Join-Path $reportsDir "p0_ack_only_safe_$stamp.matrix.log"

$preflightScript = Join-Path $repoRoot "tools\check_hw_target.ps1"
$matrixScript = Join-Path $repoRoot "tools\run_2lane_matrix_safe.ps1"
$analyzerScript = Join-Path $repoRoot "tools\analyze_2lane_ila_csv.py"
$physicalMatrixClassifier = Join-Path $repoRoot "tools\classify_2lane_physical_matrix.py"
$artifactRoot = Join-Path $reportsDir "p0_ack_only_artifacts"
$activeBitPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.bit"
$activeLtxPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.runs\impl_1\design_shiboqi_wrapper.ltx"
$activeXsaPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\design_shiboqi_wrapper.xsa"
$activeElfPath = Join-Path $repoRoot "software\_vitis_ws_ps_ps_loopback\rf_comm_ps_ps_loopback\Debug\rf_comm_ps_ps_loopback.elf"

foreach ($path in @($preflightScript, $matrixScript, $analyzerScript, $physicalMatrixClassifier, $VivadoPath, $XsctPath)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required path is missing: $path"
    }
}

function Write-SummaryLine {
    param([string]$Line)
    Write-Output $Line
    Add-Content -LiteralPath $summaryLog -Value $Line -Encoding ascii
}

function Invoke-LoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$LogPath,
        [int]$TimeoutSeconds
    )

    $proc = Start-Process -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $LogPath `
        -RedirectStandardError ($LogPath + ".err") `
        -WindowStyle Hidden `
        -PassThru
    $finished = $proc.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        return 124
    }
    $proc.Refresh()
    if ($null -eq $proc.ExitCode) {
        return 0
    }
    return $proc.ExitCode
}

function Quote-Arg {
    param([string]$Text)
    if ($Text -match "[\s`"]") {
        return '"' + ($Text -replace '"', '\"') + '"'
    }
    return $Text
}

function Get-Sha256OrMissing {
    param([string]$Path)
    if ($Path -eq "" -or -not (Test-Path -LiteralPath $Path)) {
        return "MISSING"
    }
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash
}

function Get-LatestAckArtifactDir {
    param([string]$ModeName)
    if (-not (Test-Path -LiteralPath $artifactRoot)) {
        return ""
    }
    $dir = Get-ChildItem -LiteralPath $artifactRoot -Directory -Filter ("{0}_*" -f $ModeName) -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $dir) {
        return ""
    }
    return $dir.FullName
}

function Test-AckArtifactGate {
    param([string]$ModeName)

    $latestDir = Get-LatestAckArtifactDir -ModeName $ModeName
    [void](Write-SummaryLine "ACK_ARTIFACT_GATE_MODE=$ModeName")
    [void](Write-SummaryLine "ACK_ARTIFACT_GATE_LATEST_DIR=$latestDir")
    if ($latestDir -eq "") {
        [void](Write-SummaryLine "ACK_ARTIFACT_GATE_PASS=0")
        [void](Write-SummaryLine "ACK_ARTIFACT_GATE_REASON=no latest p0_ack_only_artifacts directory for mode")
        return $false
    }

    $items = @(
        @{Name = "bit"; Active = $activeBitPath; Artifact = (Join-Path $latestDir "design_shiboqi_wrapper.bit")},
        @{Name = "ltx"; Active = $activeLtxPath; Artifact = (Join-Path $latestDir "design_shiboqi_wrapper.ltx")},
        @{Name = "xsa"; Active = $activeXsaPath; Artifact = (Join-Path $latestDir "design_shiboqi_wrapper.xsa")},
        @{Name = "elf"; Active = $activeElfPath; Artifact = (Join-Path $latestDir "rf_comm_ps_ps_loopback.elf")}
    )

    $allMatch = $true
    foreach ($item in $items) {
        $activeHash = Get-Sha256OrMissing -Path $item.Active
        $artifactHash = Get-Sha256OrMissing -Path $item.Artifact
        $match = ($activeHash -ne "MISSING" -and $activeHash -eq $artifactHash)
        if (-not $match) {
            $allMatch = $false
        }
        [void](Write-SummaryLine ("ACK_ARTIFACT_GATE_ITEM name={0} active={1} active_sha256={2} artifact={3} artifact_sha256={4} match={5}" -f $item.Name, $item.Active, $activeHash, $item.Artifact, $artifactHash, [int]$match))
    }

    [void](Write-SummaryLine "ACK_ARTIFACT_GATE_PASS=$([int]$allMatch)")
    return $allMatch
}

function Get-LatestEvidencePath {
    $candidates = @()
    $candidates += Get-ChildItem -Path $reportsDir -Filter "p0_rx_root_cause_safe_*.summary.txt" -ErrorAction SilentlyContinue
    $candidates += Get-ChildItem -Path $reportsDir -Filter "2lane_matrix_safe_*.ila_matrix.md" -ErrorAction SilentlyContinue
    $candidates += Get-ChildItem -Path $reportsDir -Filter "ila_2lane_matrix_analysis*_current.md" -ErrorAction SilentlyContinue
    if ($candidates.Count -eq 0) {
        return ""
    }
    return ($candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
}

function Test-RxPassEvidence {
    param([string]$Path)
    if ($Path -eq "" -or -not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $text = Get-Content -LiteralPath $Path -Raw -ErrorAction SilentlyContinue
    if ($null -eq $text) {
        return $false
    }
    if ($text -match "(?m)^ACK_ONLY_RX_PREREQ_PASS=1\b") {
        return $true
    }
    if ($text -match "(?m)^P0_RX_ONLY_VERDICT=PASS\b") {
        return $true
    }
    if ($text -match "rx_good=([1-9][0-9]*)") {
        return $true
    }
    if (
        $text -match "(?m)^P1_MATRIX_COMPLETE=1\b" -and
        $text -match "(?m)^AB_L0=PASS\b" -and
        $text -match "(?m)^BA_L0=PASS\b"
    ) {
        return $true
    }
    return $false
}

function Get-RequiredPhysicalLinks {
    param([string]$ModeName)
    if ($ModeName -eq "lane0") {
        return @("A_TO_B_LANE0", "B_TO_A_LANE0")
    }
    if ($ModeName -eq "lane1") {
        return @("A_TO_B_LANE1", "B_TO_A_LANE1")
    }
    return @("A_TO_B_LANE0", "A_TO_B_LANE1", "B_TO_A_LANE0", "B_TO_A_LANE1")
}

function Get-LatestPhysicalMatrixJsons {
    $candidates = Get-ChildItem -Path $reportsDir -Filter "2lane_matrix_safe_*.ila_matrix.json" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 16
    return @($candidates | ForEach-Object { $_.FullName })
}

function Invoke-PhysicalMatrixGate {
    param([string[]]$RequiredLinks)

    $matrixJsons = Get-LatestPhysicalMatrixJsons
    [void](Write-SummaryLine "PHYSICAL_MATRIX_REQUIRED_LINKS=$($RequiredLinks -join ',')")
    [void](Write-SummaryLine "PHYSICAL_MATRIX_JSON_COUNT=$($matrixJsons.Count)")
    [void](Write-SummaryLine "PHYSICAL_MATRIX_JSONS=$($matrixJsons -join ';')")
    if ($matrixJsons.Count -eq 0) {
        [void](Write-SummaryLine "PHYSICAL_MATRIX_GATE_EXIT=22")
        [void](Write-SummaryLine "PHYSICAL_MATRIX_GATE_RESULT=BLOCK_NO_JSON_EVIDENCE")
        return 22
    }

    $args = @($physicalMatrixClassifier) + $matrixJsons + @(
        "--require-links",
        ($RequiredLinks -join ","),
        "--latest-by-link"
    )
    $output = & python @args 2>&1
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    foreach ($line in $output) {
        [void](Write-SummaryLine "PHYSICAL_MATRIX_GATE_OUTPUT=$line")
    }
    [void](Write-SummaryLine "PHYSICAL_MATRIX_GATE_EXIT=$exitCode")
    return $exitCode
}

function Get-AckRecipe {
    param([string]$ModeName)
    if ($ModeName -eq "lane0") {
        return @{
            TriggerModes = @("a_tx_lane0", "b_tx_lane0", "b_rx_check_state", "b_rx_flush_state")
            Config = "IR_B_MODE=stream_bidir IR_LANE_COUNT=2 IR_B_SESSION_ID=0x2201 IR_B_RX_LANE_MASK=1 IR_B_EXPECTED_A_LANE_MASK=1 IR_B_TX_LANE_MASK=1 IR_B_ACK_LANE_MASK=1 IR_B2A_ENABLE=0 IR_B2A_FREE_RUN=0"
            Expected = "B rx_good grows, B lane0 ACK TX pulse appears, A ack_seen grows, A tx_fail remains 0"
        }
    }
    if ($ModeName -eq "lane1") {
        return @{
            TriggerModes = @("a_tx_lane1", "b_tx_lane1", "b_rx_check_state", "b_rx_flush_state")
            Config = "IR_B_MODE=stream_bidir IR_LANE_COUNT=2 IR_B_SESSION_ID=0x2202 IR_B_RX_LANE_MASK=2 IR_B_EXPECTED_A_LANE_MASK=2 IR_B_TX_LANE_MASK=2 IR_B_ACK_LANE_MASK=2 IR_B2A_ENABLE=0 IR_B2A_FREE_RUN=0"
            Expected = "B rx_good grows, B lane1 ACK TX pulse appears, A ack_seen grows, A tx_fail remains 0"
        }
    }
    return @{
        TriggerModes = @("a_tx_lane0", "a_tx_lane1", "b_tx_lane0", "b_tx_lane1", "b_rx_check_state", "b_rx_flush_state")
        Config = "IR_B_MODE=stream_bidir IR_LANE_COUNT=2 IR_B_SESSION_ID=0x2203 IR_B_RX_LANE_MASK=3 IR_B_EXPECTED_A_LANE_MASK=3 IR_B_TX_LANE_MASK=3 IR_B_ACK_LANE_MASK=3 IR_B2A_ENABLE=0 IR_B2A_FREE_RUN=0"
        Expected = "Both lanes show RX-good path and ACK TX pulses without B free-run payload"
    }
}

$recipe = Get-AckRecipe -ModeName $Mode
$triggerModes = @($recipe.TriggerModes)
$requiredPhysicalLinks = Get-RequiredPhysicalLinks -ModeName $Mode
if ($RxEvidencePath -eq "") {
    $RxEvidencePath = Get-LatestEvidencePath
}
$rxPass = Test-RxPassEvidence -Path $RxEvidencePath

"P0_ACK_ONLY_SAFE_BEGIN $(Get-Date -Format o)" | Out-File -FilePath $summaryLog -Encoding ascii
Write-SummaryLine "REPO_ROOT=$repoRoot"
Write-SummaryLine "MODE=$Mode"
Write-SummaryLine "COM_PORT=$ComPort"
Write-SummaryLine "BAUD_RATE=$BaudRate"
Write-SummaryLine "HW_SERVER_URL=$HwServerUrl"
Write-SummaryLine "JTAG_FREQUENCY_HZ=$JtagFrequencyHz"
Write-SummaryLine "TRIGGER_MODES=$($triggerModes -join ',')"
Write-SummaryLine "DRY_RUN=$([int]$DryRun.IsPresent)"
Write-SummaryLine "ALLOW_WITHOUT_RX_PASS=$([int]$AllowWithoutRxPass.IsPresent)"
Write-SummaryLine "ALLOW_ARTIFACT_MISMATCH=$([int]$AllowArtifactMismatch.IsPresent)"
Write-SummaryLine "PREFLIGHT_LOG=$preflightLog"
Write-SummaryLine "MATRIX_LOG=$matrixLog"
Write-SummaryLine "RX_EVIDENCE_PATH=$RxEvidencePath"
Write-SummaryLine "RX_EVIDENCE_PASS_PARSED=$([int]$rxPass)"
Write-SummaryLine "REQUIRED_PHYSICAL_LINKS=$($requiredPhysicalLinks -join ',')"
Write-SummaryLine "P0_SCOPE=P0-6 ACK-only return-path orchestration"
Write-SummaryLine "ACK_ONLY_REQUIRED_CONFIG=$($recipe.Config)"
Write-SummaryLine "ACK_ONLY_EXPECTED_RESULT=$($recipe.Expected)"
Write-SummaryLine "ACK_ONLY_LIMITATION=This wrapper proves execution discipline; the bitstream must be built with the required ACK-only config for a valid P0-6 claim."
Write-SummaryLine "NO_FPGA_PROGRAMMING_BEFORE_ARTIFACT_GATE_PASS=1"
Write-SummaryLine "NO_FPGA_PROGRAMMING_BEFORE_PREFLIGHT_PASS=1"
Write-SummaryLine "NO_TFDU_DRIVE_BEFORE_PREFLIGHT_AND_RX_PREREQ=1"

$preflightArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $preflightScript,
    "-VivadoPath",
    $VivadoPath,
    "-ComPort",
    $ComPort,
    "-HwServerUrl",
    $HwServerUrl,
    "-JtagFrequencyHz",
    [string]$JtagFrequencyHz
)

$matrixArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $matrixScript,
    "-ComPort",
    $ComPort,
    "-BaudRate",
    [string]$BaudRate,
    "-XsctPath",
    $XsctPath,
    "-VivadoPath",
    $VivadoPath,
    "-TriggerModes"
    ($triggerModes -join ",")
) + @(
    "-JtagFrequencyHz",
    [string]$JtagFrequencyHz,
    "-PerRunTimeoutSeconds",
    [string]$PerRunTimeoutSeconds,
    "-MaxTfduWindowSeconds",
    [string]$MaxTfduWindowSeconds
)
if ($StopOnFail) {
    $matrixArgs += "-StopOnFail"
}

Write-SummaryLine "PREFLIGHT_COMMAND=powershell $((@($preflightArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"
Write-SummaryLine "MATRIX_COMMAND=powershell $((@($matrixArgs) | ForEach-Object { Quote-Arg $_ }) -join ' ')"

$artifactGatePassed = Test-AckArtifactGate -ModeName $Mode

if ($DryRun) {
    Write-SummaryLine "DRY_RUN_NO_PREFLIGHT_DONE=1"
    Write-SummaryLine "DRY_RUN_NO_HARDWARE_DONE=1"
    Write-SummaryLine "P0_ACK_ONLY_SAFE_END $(Get-Date -Format o)"
    exit 0
}

if (-not $artifactGatePassed -and -not $AllowArtifactMismatch) {
    Write-SummaryLine "P0_ACK_ONLY_BLOCKED_ARTIFACT_MISMATCH=1"
    Write-SummaryLine "P0_ACK_ONLY_SAFE_END $(Get-Date -Format o)"
    exit 23
}
if (-not $artifactGatePassed -and $AllowArtifactMismatch) {
    Write-SummaryLine "P0_ACK_ONLY_ARTIFACT_MISMATCH_BYPASSED=1"
}

$physicalMatrixExit = Invoke-PhysicalMatrixGate -RequiredLinks $requiredPhysicalLinks
if ($physicalMatrixExit -ne 0) {
    Write-SummaryLine "P0_ACK_ONLY_BLOCKED_PHYSICAL_MATRIX=1"
    Write-SummaryLine "P0_ACK_ONLY_SAFE_END $(Get-Date -Format o)"
    exit 22
}

if (-not $rxPass -and -not $AllowWithoutRxPass) {
    Write-SummaryLine "P0_ACK_ONLY_BLOCKED_NO_RX_PASS_EVIDENCE=1"
    Write-SummaryLine "P0_ACK_ONLY_SAFE_END $(Get-Date -Format o)"
    exit 21
}
if (-not $rxPass -and $AllowWithoutRxPass) {
    Write-SummaryLine "P0_ACK_ONLY_RX_PREREQ_BYPASSED=1"
}

Write-SummaryLine "PREFLIGHT_START=$(Get-Date -Format o)"
$preflightExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $preflightArgs -LogPath $preflightLog -TimeoutSeconds 150
Write-SummaryLine "PREFLIGHT_EXIT=$preflightExit"
$preflightText = ""
if (Test-Path -LiteralPath $preflightLog) {
    $preflightText = Get-Content -LiteralPath $preflightLog -Raw -ErrorAction SilentlyContinue
    if ($null -eq $preflightText) {
        $preflightText = ""
    }
    foreach ($line in (($preflightText -split "`r?`n") | Where-Object {
        $_ -match "COM_PORT_PRESENT|PNP_DEVICE|HW_PREFLIGHT_TARGET_COUNT|HW_PREFLIGHT_ZYNQ|HW_PREFLIGHT_RESULT|VIVADO_PREFLIGHT_EXIT"
    })) {
        Write-SummaryLine "PREFLIGHT_MATCH=$line"
    }
}

$preflightPassed = ($preflightText -match "HW_PREFLIGHT_RESULT PASS" -and $preflightText -match "HW_PREFLIGHT_ZYNQ")
$preflightEffectiveExit = $preflightExit
$vivadoExitMatch = [regex]::Match($preflightText, "VIVADO_PREFLIGHT_EXIT\s*=\s*(\d+)")
if ($vivadoExitMatch.Success) {
    $preflightEffectiveExit = [int]$vivadoExitMatch.Groups[1].Value
}
Write-SummaryLine "PREFLIGHT_EFFECTIVE_EXIT=$preflightEffectiveExit"
Write-SummaryLine "PREFLIGHT_PASS_PARSED=$([int]$preflightPassed)"
if (-not $preflightPassed) {
    Write-SummaryLine "P0_ACK_ONLY_BLOCKED_NO_PROGRAMMING=1"
    Write-SummaryLine "P0_ACK_ONLY_SAFE_END $(Get-Date -Format o)"
    exit 20
}

Write-SummaryLine "MATRIX_START=$(Get-Date -Format o)"
$matrixExit = Invoke-LoggedProcess -FilePath "powershell.exe" -Arguments $matrixArgs -LogPath $matrixLog -TimeoutSeconds (($PerRunTimeoutSeconds * [Math]::Max(1, $triggerModes.Count)) + 300)
Write-SummaryLine "MATRIX_EXIT=$matrixExit"
if (Test-Path -LiteralPath $matrixLog) {
    foreach ($line in (Get-Content -LiteralPath $matrixLog -ErrorAction SilentlyContinue | Where-Object {
        $_ -match "MATRIX_PREFLIGHT|MATRIX_ANALYSIS|RUN_RESULT|RUN_SAFETY|LANE2_MATRIX_SAFE_END"
    })) {
        Write-SummaryLine "MATRIX_MATCH=$line"
    }
}

Write-SummaryLine "P0_ACK_ONLY_SAFE_END $(Get-Date -Format o)"
exit $matrixExit
