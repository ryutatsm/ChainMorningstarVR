param(
    [string]$GameDirectory = "",
    [string]$OutputDirectory = $PSScriptRoot
)
$ErrorActionPreference = 'Stop'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$stage = Join-Path $OutputDirectory "CMS-feedback-$timestamp"
New-Item -ItemType Directory -Path $stage -Force | Out-Null
$documents = [Environment]::GetFolderPath('MyDocuments')
$logRoot = Join-Path $documents 'My Games\Skyrim VR'
$logFiles = @('SKSE\ChainMorningstarVR.log', 'SKSE\sksevr.log', 'SKSE\higgs_vr.log', 'SKSE\activeragdoll.log', 'Logs\Script\Papyrus.0.log')
$report = [System.Collections.Generic.List[string]]::new()
$report.Add('ChainMorningstarVR 0.5.0 audit-preview feedback')
$report.Add("Collected: $timestamp")
foreach ($relative in $logFiles) {
    $source = Join-Path $logRoot $relative
    if (Test-Path -LiteralPath $source -PathType Leaf) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $stage ([IO.Path]::GetFileName($relative)))
        $report.Add("LOG FOUND: $relative")
    } else { $report.Add("LOG MISSING: $relative") }
}
if ($GameDirectory) {
    $files = @('SkyrimVR.exe', 'Data\ChainMorningstarVR.esp', 'Data\SKSE\Plugins\ChainMorningstarVR.dll', 'Data\meshes\weapons\ChainMorningstarVR\ChainMorningstar.nif')
    foreach ($relative in $files) {
        $source = Join-Path $GameDirectory $relative
        if (Test-Path -LiteralPath $source -PathType Leaf) {
            $hash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower()
            $report.Add("SHA256 $hash  $relative")
        } else { $report.Add("FILE MISSING: $relative") }
    }
}
$report | Set-Content -LiteralPath (Join-Path $stage 'collection.txt') -Encoding UTF8
$archive = "$stage.zip"
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $archive
Write-Host "Created: $archive"
Write-Host 'Attach this ZIP and a screenshot of the equipped weapon to the conversation.'
