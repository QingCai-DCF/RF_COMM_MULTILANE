param(
    [string]$BuildSummaryPath = "",
    [string]$OutPath = "",
    [int]$PayloadBytes = 256,
    [int]$RawPacketBytes = 264,
    [int]$FragmentBytes = 64,
    [int]$MaxRetry = 12,
    [int]$StageSeconds = 24,
    [int]$StreamPhyDebugSelect = 1
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

if (-not $BuildSummaryPath) {
    $latest = Get-ChildItem -LiteralPath $reportsDir -Filter "g0_lane0_build_*.summary.txt" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $latest) {
        throw "No g0_lane0_build summary found"
    }
    $BuildSummaryPath = $latest.FullName
}

if (-not (Test-Path -LiteralPath $BuildSummaryPath)) {
    throw "Missing build summary: $BuildSummaryPath"
}

if (-not $OutPath) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutPath = Join-Path $reportsDir "g1_lane0_smoke_build_validated_$stamp.summary.txt"
}

$expectedConstraintHash = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
$text = Get-Content -LiteralPath $BuildSummaryPath -Raw -Encoding ascii

function Has-Line {
    param([string]$Pattern)
    return ($text -match $Pattern)
}

function Get-ArtifactLine {
    param([string]$Name)
    $match = [regex]::Match($text, "ARTIFACT $Name path=([^ ]+) sha256=([0-9A-Fa-f]+)")
    if (-not $match.Success) {
        return $null
    }
    return [pscustomobject]@{
        Name = $Name
        Path = $match.Groups[1].Value
        Sha256 = $match.Groups[2].Value.ToUpperInvariant()
    }
}

function Get-SummaryValue {
    param([string]$Name)
    $match = [regex]::Match($text, "(?m)^$([regex]::Escape($Name))=(.+)$")
    if (-not $match.Success) {
        return ""
    }
    return $match.Groups[1].Value.Trim()
}

function Test-XciParamValue {
    param(
        [string]$XciPath,
        [string]$ParamName,
        [string]$ExpectedValue
    )
    if (-not (Test-Path -LiteralPath $XciPath)) {
        return $false
    }
    $xciText = Get-Content -LiteralPath $XciPath -Raw -Encoding ascii
    $paramPattern = '"' + [regex]::Escape($ParamName) + '"\s*:\s*\[\s*\{\s*"value"\s*:\s*"' + [regex]::Escape($ExpectedValue) + '"'
    return ($xciText -match $paramPattern)
}

function Test-XciGeneratedParamValue {
    param(
        [string]$XciPath,
        [string]$ParamName,
        [string]$ExpectedValue
    )
    if (-not (Test-Path -LiteralPath $XciPath)) {
        return $false
    }
    $xciText = Get-Content -LiteralPath $XciPath -Raw -Encoding ascii
    $paramPattern = '"' + [regex]::Escape($ParamName) + '"\s*:\s*\[\s*\{\s*"value"\s*:\s*"' + [regex]::Escape($ExpectedValue) + '"\s*,\s*"resolve_type"\s*:\s*"(generated|dependent)"'
    return ($xciText -match $paramPattern)
}

function Test-RtlRxDefaultWindow {
    param(
        [string]$RtlPath,
        [string]$Label
    )
    if (-not (Test-Path -LiteralPath $RtlPath)) {
        $script:missing += "RTL_EXISTS_$Label"
        return
    }
    $rtlText = Get-Content -LiteralPath $RtlPath -Raw -Encoding ascii
    if ($rtlText -notmatch "parameter\s+int\s+RX_DETECT_START_CYCLES\s*=\s*0\s*,") {
        $script:missing += "RTL_${Label}_RX_DETECT_START_DEFAULT=0"
    }
    if ($rtlText -notmatch "parameter\s+int\s+RX_DETECT_END_CYCLES\s*=\s*\(CNT_CHIP_MAX\s*>=\s*15\)\s*\?\s*10\s*:\s*\(\(CNT_CHIP_MAX\s*>=\s*7\)\s*\?\s*\(CNT_CHIP_MAX\s*-\s*2\)\s*:\s*CNT_CHIP_MAX\)\s*,") {
        $script:missing += "RTL_${Label}_RX_DETECT_END_DEFAULT=CNT_CHIP_MAX-2"
    }
    if ($rtlText -notmatch "parameter\s+int\s+RX_PREAMBLE_REALIGN_EDGE\s*=\s*0\s*,") {
        $script:missing += "RTL_${Label}_RX_PREAMBLE_REALIGN_EDGE_DEFAULT=0"
    }
}

$requiredPatterns = @(
    "CONSTRAINT_SHA256=$expectedConstraintHash",
    "BUILD_ENV IR_CNT_PREAMBLE=16",
    "BUILD_ENV IR_MAX_PACKET_BYTES=$RawPacketBytes",
    "BUILD_ENV IR_FRAGMENT_BYTES=$FragmentBytes",
    "BUILD_ENV IR_MAX_RETRY=$MaxRetry",
    "BUILD_ENV IR_HW_MAX_PACKET_BYTES=$RawPacketBytes",
    "BUILD_ENV IR_HW_RX_TRANSFER_BYTES=$RawPacketBytes",
    "BUILD_ENV IR_RX_DETECT_START_CYCLES=0",
    "BUILD_ENV IR_RX_DETECT_END_CYCLES=5",
    "BUILD_ENV IR_RX_PREAMBLE_REALIGN_EDGE=0",
    "BUILD_ENV IR_B_RX_DETECT_START_CYCLES=0",
    "BUILD_ENV IR_B_RX_DETECT_END_CYCLES=7",
    "BUILD_ENV IR_B_RX_PREAMBLE_REALIGN_EDGE=0",
    "BUILD_ENV IR_STREAM_PHY_DBG_SELECT=$StreamPhyDebugSelect",
    "BUILD_ENV PSPS_PAYLOAD_BYTES=$PayloadBytes",
    "BUILD_ENV PSPS_STAGE_SECONDS=$StageSeconds",
    "CONFIG_EXIT=0",
    "ILA_EXIT=0",
    "BITSTREAM_EXIT=0",
    "VITIS_EXIT=0",
    "G0_LANE0_BUILD_DONE=1"
)

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
$constraintPath = Join-Path $repoRoot $constraintFileName
$constraintHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $constraintPath).Hash

$missing = @()
foreach ($pattern in $requiredPatterns) {
    if (-not (Has-Line ([regex]::Escape($pattern)))) {
        $missing += $pattern
    }
}

$artifacts = @()
foreach ($name in @("bit", "ltx", "xsa", "elf")) {
    $artifact = Get-ArtifactLine -Name $name
    if ($null -eq $artifact) {
        $missing += "ARTIFACT $name"
        continue
    }
    if (-not (Test-Path -LiteralPath $artifact.Path)) {
        $missing += "ARTIFACT_EXISTS $name"
        continue
    }
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $artifact.Path).Hash
    if ($actualHash -ne $artifact.Sha256) {
        $missing += "ARTIFACT_HASH_MATCH $name"
    }
    $artifacts += $artifact
}

$configLogPath = Get-SummaryValue -Name "CONFIG_LOG"
if (-not $configLogPath) {
    $missing += "CONFIG_LOG"
} elseif (-not (Test-Path -LiteralPath $configLogPath)) {
    $missing += "CONFIG_LOG_EXISTS"
} else {
    $configText = Get-Content -LiteralPath $configLogPath -Raw -Encoding ascii
    if ($configText -notmatch [regex]::Escape("CONFIG.STREAM_PHY_DBG_SELECT $StreamPhyDebugSelect")) {
        $missing += "CONFIG_LOG_A_STREAM_PHY_DBG_SELECT=$StreamPhyDebugSelect"
    }
    if ($configText -notmatch [regex]::Escape("CONFIG.MAX_RETRY $MaxRetry")) {
        $missing += "CONFIG_LOG_A_MAX_RETRY=$MaxRetry"
    }
    if ($configText -notmatch [regex]::Escape("CONFIG.RX_DETECT_START_CYCLES 0")) {
        $missing += "CONFIG_LOG_A_RX_DETECT_START_CYCLES=0"
    }
    if ($configText -notmatch [regex]::Escape("CONFIG.RX_DETECT_END_CYCLES 5")) {
        $missing += "CONFIG_LOG_A_RX_DETECT_END_CYCLES=5"
    }
    if ($configText -notmatch [regex]::Escape("CONFIG.RX_PREAMBLE_REALIGN_EDGE 0")) {
        $missing += "CONFIG_LOG_A_RX_PREAMBLE_REALIGN_EDGE=0"
    }
    if ($configText -notmatch [regex]::Escape("CONFIG.B_RX_DETECT_END_CYCLES 7")) {
        $missing += "CONFIG_LOG_B_RX_DETECT_END_CYCLES=7"
    }
}

$xciPath = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.srcs\sources_1\bd\design_shiboqi\ip\design_shiboqi_ir_array_top_axi_0_0\design_shiboqi_ir_array_top_axi_0_0.xci"
if (-not (Test-XciParamValue -XciPath $xciPath -ParamName "STREAM_PHY_DBG_SELECT" -ExpectedValue ([string]$StreamPhyDebugSelect))) {
    $missing += "XCI_STREAM_PHY_DBG_SELECT=$StreamPhyDebugSelect"
}
if (-not (Test-XciGeneratedParamValue -XciPath $xciPath -ParamName "STREAM_PHY_DBG_SELECT" -ExpectedValue ([string]$StreamPhyDebugSelect))) {
    $missing += "XCI_MODEL_STREAM_PHY_DBG_SELECT=$StreamPhyDebugSelect"
}
if (-not (Test-XciParamValue -XciPath $xciPath -ParamName "MAX_RETRY" -ExpectedValue ([string]$MaxRetry))) {
    $missing += "XCI_MAX_RETRY=$MaxRetry"
}
if (-not (Test-XciGeneratedParamValue -XciPath $xciPath -ParamName "MAX_RETRY" -ExpectedValue ([string]$MaxRetry))) {
    $missing += "XCI_MODEL_MAX_RETRY=$MaxRetry"
}
if (-not (Test-XciParamValue -XciPath $xciPath -ParamName "RX_DETECT_START_CYCLES" -ExpectedValue "0")) {
    $missing += "XCI_RX_DETECT_START_CYCLES=0"
}
if (-not (Test-XciGeneratedParamValue -XciPath $xciPath -ParamName "RX_DETECT_START_CYCLES" -ExpectedValue "0")) {
    $missing += "XCI_MODEL_RX_DETECT_START_CYCLES=0"
}
if (-not (Test-XciParamValue -XciPath $xciPath -ParamName "RX_DETECT_END_CYCLES" -ExpectedValue "5")) {
    $missing += "XCI_RX_DETECT_END_CYCLES=5"
}
if (-not (Test-XciGeneratedParamValue -XciPath $xciPath -ParamName "RX_DETECT_END_CYCLES" -ExpectedValue "5")) {
    $missing += "XCI_MODEL_RX_DETECT_END_CYCLES=5"
}
if (-not (Test-XciParamValue -XciPath $xciPath -ParamName "RX_PREAMBLE_REALIGN_EDGE" -ExpectedValue "0")) {
    $missing += "XCI_RX_PREAMBLE_REALIGN_EDGE=0"
}
if (-not (Test-XciGeneratedParamValue -XciPath $xciPath -ParamName "RX_PREAMBLE_REALIGN_EDGE" -ExpectedValue "0")) {
    $missing += "XCI_MODEL_RX_PREAMBLE_REALIGN_EDGE=0"
}

$rtlDefaultChecks = @(
    @{ Label = "SRC_ARRAY_AXI"; Path = Join-Path $repoRoot "IPs\ip_ir_array\src\ir_array_top_axi.sv" },
    @{ Label = "SRC_STREAM_AXI"; Path = Join-Path $repoRoot "IPs\ip_ir_array\src\ir_stream_array_top_axi.sv" },
    @{ Label = "SRC_STREAM_TOP"; Path = Join-Path $repoRoot "IPs\ip_ir_array\src\ir_stream_array_top.sv" }
)
foreach ($item in $rtlDefaultChecks) {
    Test-RtlRxDefaultWindow -RtlPath $item.Path -Label $item.Label
}

$ipsharedRoot = Join-Path $repoRoot "TFDU_VFIR_Client_Array\TFDU_VFIR_Client.gen\sources_1\bd\design_shiboqi\ipshared"
foreach ($fileName in @("ir_array_top_axi.sv", "ir_stream_array_top_axi.sv", "ir_stream_array_top.sv")) {
    $matches = @(Get-ChildItem -LiteralPath $ipsharedRoot -Recurse -Filter $fileName -ErrorAction SilentlyContinue | Sort-Object FullName)
    if ($matches.Count -eq 0) {
        $missing += "RTL_GEN_IPSHARED_$fileName"
        continue
    }
    foreach ($match in $matches) {
        $label = "GEN_" + ($fileName -replace "\.sv$", "" -replace "[^A-Za-z0-9]", "_")
        Test-RtlRxDefaultWindow -RtlPath $match.FullName -Label $label
    }
}

$pass = ($missing.Count -eq 0 -and $constraintHash -eq $expectedConstraintHash)

$lines = @()
$lines += "G1_LANE0_SMOKE_BUILD_VALIDATION_BEGIN $(Get-Date -Format o)"
$lines += "REPO_ROOT=$repoRoot"
$lines += "BUILD_SUMMARY=$BuildSummaryPath"
$lines += "CONSTRAINT_SHA256=$constraintHash"
$lines += "G1_PAYLOAD_BYTES=$PayloadBytes"
$lines += "G1_RAW_PACKET_BYTES=$RawPacketBytes"
$lines += "G1_FRAGMENT_BYTES=$FragmentBytes"
$lines += "G1_MAX_RETRY=$MaxRetry"
$lines += "G1_STREAM_PHY_DBG_SELECT=$StreamPhyDebugSelect"
$lines += "G1_XCI_PATH=$xciPath"
foreach ($artifact in $artifacts) {
    $lines += "ARTIFACT $($artifact.Name) path=$($artifact.Path) sha256=$($artifact.Sha256)"
}
if ($missing.Count -gt 0) {
    foreach ($item in $missing) {
        $lines += "MISSING_OR_BAD=$item"
    }
}
$lines += "G1_LANE0_SMOKE_BUILD_VALIDATED=$([int]$pass)"
$lines += "G1_LANE0_SMOKE_BUILD_VALIDATION_END $(Get-Date -Format o)"

$lines | Out-File -LiteralPath $OutPath -Encoding ascii
$lines | ForEach-Object { Write-Host $_ }

if (-not $pass) {
    exit 1
}
exit 0
