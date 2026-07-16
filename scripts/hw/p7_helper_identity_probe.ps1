[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$CsServer,
    [Parameter(Mandatory = $true)][string]$RdiXsdb,
    [Parameter(Mandatory = $true)][string]$Cmd,
    [Parameter(Mandatory = $true)][string]$Conhost
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-P7HelperIdentity {
    param(
        [Parameter(Mandatory = $true)][string]$Role,
        [Parameter(Mandatory = $true)][string]$LiteralPath
    )

    $item = Get-Item -LiteralPath $LiteralPath -Force -ErrorAction Stop
    if ($item.PSIsContainer) {
        throw "P7 helper identity target is not a regular file: role=$Role path=$LiteralPath"
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $LiteralPath -ErrorAction Stop
    $signer = $signature.SignerCertificate
    $version = $item.VersionInfo
    [ordered]@{
        role = $Role
        path = $item.FullName
        bytes = [int64]$item.Length
        file_version = '{0}.{1}.{2}.{3}' -f $version.FileMajorPart, $version.FileMinorPart, $version.FileBuildPart, $version.FilePrivatePart
        product_version = '{0}.{1}.{2}.{3}' -f $version.ProductMajorPart, $version.ProductMinorPart, $version.ProductBuildPart, $version.ProductPrivatePart
        company_name = [string]$version.CompanyName
        signature_status = [string]$signature.Status
        signature_type = [string]$signature.SignatureType
        signer_subject = if ($null -eq $signer) { '' } else { [string]$signer.Subject }
        signer_thumbprint = if ($null -eq $signer) { '' } else { [string]$signer.Thumbprint }
    }
}

$records = @(
    Get-P7HelperIdentity -Role 'cs_server' -LiteralPath $CsServer
    Get-P7HelperIdentity -Role 'rdi_xsdb' -LiteralPath $RdiXsdb
    Get-P7HelperIdentity -Role 'cmd' -LiteralPath $Cmd
    Get-P7HelperIdentity -Role 'conhost' -LiteralPath $Conhost
)
$probeHostPath = [System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
$probeHost = Get-P7HelperIdentity -Role 'probe_host' -LiteralPath $probeHostPath

[ordered]@{
    schema = 'rf-comm-p7-vivado-helper-identity-probe-v1'
    probe_host = $probeHost
    records = $records
} | ConvertTo-Json -Depth 5 -Compress
