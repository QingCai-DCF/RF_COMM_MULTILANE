param(
    [string[]]$RequiredLinks = @("A_TO_B_LANE0", "A_TO_B_LANE1", "B_TO_A_LANE0", "B_TO_A_LANE1"),
    [int]$MaxJsonFiles = 16,
    [string[]]$JsonPaths = @()
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $scriptDir "..")).Path
$reportsDir = Join-Path $repoRoot "reports"
$classifier = Join-Path $repoRoot "tools\classify_2lane_physical_matrix.py"

if (-not (Test-Path -LiteralPath $classifier -PathType Leaf)) {
    Write-Output "PHYSICAL_MATRIX_GATE_RESULT=BLOCK_CLASSIFIER_MISSING"
    Write-Output "PHYSICAL_MATRIX_GATE_CLASSIFIER=$classifier"
    exit 22
}

if ($JsonPaths.Count -gt 0) {
    $expandedJsonPaths = @(
        foreach ($pathGroup in $JsonPaths) {
            foreach ($path in ($pathGroup -split "[,;]")) {
                if (-not [string]::IsNullOrWhiteSpace($path)) {
                    $path.Trim()
                }
            }
        }
    )
    $matrixJsons = @(
        foreach ($path in $expandedJsonPaths) {
            (Resolve-Path -LiteralPath $path -ErrorAction Stop).Path
        }
    )
} else {
    $matrixJsons = @(
        Get-ChildItem -Path $reportsDir -Filter "2lane_matrix_safe_*.ila_matrix.json" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First $MaxJsonFiles |
            ForEach-Object { $_.FullName }
    )
}

Write-Output "PHYSICAL_MATRIX_REQUIRED_LINKS=$($RequiredLinks -join ',')"
Write-Output "PHYSICAL_MATRIX_JSON_COUNT=$($matrixJsons.Count)"
Write-Output "PHYSICAL_MATRIX_JSONS=$($matrixJsons -join ';')"

if ($matrixJsons.Count -eq 0) {
    Write-Output "PHYSICAL_MATRIX_GATE_RESULT=BLOCK_NO_JSON_EVIDENCE"
    exit 22
}

$args = @($classifier) + $matrixJsons + @(
    "--require-links",
    ($RequiredLinks -join ","),
    "--latest-by-link"
)

$output = & python @args 2>&1
$exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
foreach ($line in $output) {
    Write-Output "PHYSICAL_MATRIX_CLASSIFIER=$line"
}
Write-Output "PHYSICAL_MATRIX_GATE_EXIT=$exitCode"
if ($exitCode -eq 0) {
    Write-Output "PHYSICAL_MATRIX_GATE_RESULT=PASS"
} else {
    Write-Output "PHYSICAL_MATRIX_GATE_RESULT=BLOCK"
}
exit $exitCode
