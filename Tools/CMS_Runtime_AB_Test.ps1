param(
    [ValidateSet('Menu','Disable','Restore','Collect')][string]$Mode = 'Menu',
    [string]$GameRoot = 'E:\Program Files (x86)\Steam\steamapps\common\SkyrimVR',
    [string]$LogRoot = '',
    [switch]$NoPause
)

$ErrorActionPreference = 'Stop'
$expectedHash = '3733450D0EEEA6D93C56040F4ABE422DC3F8DAA177776DAC1DC2F5E4C3C46D32'
$exitCode = 0

function Assert-GameClosed {
    if (Get-Process -Name SkyrimVR -ErrorAction SilentlyContinue) {
        throw 'Close Skyrim VR before changing the DLL. No files were changed.'
    }
}
function Get-CMSHash([string]$Path) {
    $hashAlgorithm = [Security.Cryptography.SHA256]::Create()
    $fileStream = [IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($hashAlgorithm.ComputeHash($fileStream)).Replace('-','') }
    finally { $fileStream.Dispose(); $hashAlgorithm.Dispose() }
}
function Assert-ExpectedFile([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "File not found: $Path" }
    if ((Get-CMSHash $Path) -ne $expectedHash) {
        throw "Unrecognized DLL. No replacement or deletion is permitted: $Path"
    }
}

try {
    $resolvedRoot = (Resolve-Path -LiteralPath $GameRoot).ProviderPath
    $pluginRoot = [IO.Path]::GetFullPath((Join-Path $resolvedRoot 'Data\SKSE\Plugins'))
    $dllPath = [IO.Path]::GetFullPath((Join-Path $pluginRoot 'ChainMorningstarVR.dll'))
    $offPath = [IO.Path]::GetFullPath((Join-Path $pluginRoot 'ChainMorningstarVR.dll.cms-diagnostic-disabled'))
    $rootPrefix = $resolvedRoot.TrimEnd('\') + '\'
    foreach ($targetPath in @($pluginRoot, $dllPath, $offPath)) {
        if (-not $targetPath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Target path escaped the selected game directory.'
        }
    }
    if ($Mode -eq 'Menu') {
        Write-Host 'CMS runtime comparison test (ESP, model, textures and other MODs stay installed).'
        Write-Host '1: Disable CMS DLL only / 2: Restore CMS DLL / 3: Collect current logs'
        $selection = Read-Host 'Choose 1, 2 or 3'
        switch ($selection) {
            '1' { $Mode = 'Disable' }
            '2' { $Mode = 'Restore' }
            '3' { $Mode = 'Collect' }
            default { throw 'Cancelled. No files changed.' }
        }
    }
    if ($Mode -eq 'Disable') {
        Assert-GameClosed
        Assert-ExpectedFile $dllPath
        if (Test-Path -LiteralPath $offPath) {
            throw 'A disabled copy already exists. Choose Restore first; do not deploy with Vortex during this test.'
        }
        Rename-Item -LiteralPath $dllPath -NewName ([IO.Path]::GetFileName($offPath))
        Assert-ExpectedFile $offPath
        Write-Host 'CMS DLL DISABLED. The chain will not simulate. Do not save your game during this comparison.'
        Write-Host 'Keep Vortex deployment unchanged until Restore has completed.'
    } elseif ($Mode -eq 'Restore') {
        Assert-GameClosed
        if (Test-Path -LiteralPath $offPath) {
            Assert-ExpectedFile $offPath
            if (Test-Path -LiteralPath $dllPath) {
                # Vortex may have redeployed the exact accepted DLL. Remove only
                # the proven identical, inactive duplicate; never another DLL.
                Assert-ExpectedFile $dllPath
                Remove-Item -LiteralPath $offPath
            } else {
                Rename-Item -LiteralPath $offPath -NewName ([IO.Path]::GetFileName($dllPath))
            }
        }
        Assert-ExpectedFile $dllPath
        Write-Host 'CMS DLL RESTORED. Original SHA256 verified.'
    } elseif ($Mode -eq 'Collect') {
        Assert-GameClosed
        if (-not $LogRoot) {
            $LogRoot = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'My Games\Skyrim VR\SKSE'
        }
        $resolvedLogs = (Resolve-Path -LiteralPath $LogRoot).ProviderPath
        $label = if (Test-Path -LiteralPath $dllPath) { 'CMS-on' } else { 'CMS-off' }
        $captureRoot = Join-Path $PSScriptRoot ('CMS-comparison-' + $label + '-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
        New-Item -ItemType Directory -Path $captureRoot | Out-Null
        $captured = @()
        $logsToCopy = @('sksevr.log','ChainMorningstarVR.log','CrashLogger.log')
        foreach ($logName in $logsToCopy) {
            $sourcePath = Join-Path $resolvedLogs $logName
            if (Test-Path -LiteralPath $sourcePath -PathType Leaf) {
                Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $captureRoot $logName)
                $captured += $logName
            }
        }
        $recentCrashes = Get-ChildItem -LiteralPath $resolvedLogs -Filter 'crash-*.log' -File |
            Sort-Object LastWriteTime -Descending | Select-Object -First 3
        foreach ($crashFile in $recentCrashes) {
            Copy-Item -LiteralPath $crashFile.FullName -Destination (Join-Path $captureRoot $crashFile.Name)
            $captured += $crashFile.Name
        }
        $status = [ordered]@{
            captured_at = (Get-Date -Format 'o')
            game_root = $resolvedRoot
            cms_dll_enabled = (Test-Path -LiteralPath $dllPath)
            disabled_copy_exists = (Test-Path -LiteralPath $offPath)
            active_dll_sha256 = $(if (Test-Path -LiteralPath $dllPath) { Get-CMSHash $dllPath } else { $null })
            captured_files = $captured
            note = 'Copied logs may be older than this trial. Match their timestamps to the trial; no automatic pass/fail judgement.'
        }
        $status | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $captureRoot 'comparison_status.json') -Encoding UTF8
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::CreateFromDirectory($captureRoot, ($captureRoot + '.zip'))
        Write-Host ('LOGS SAVED: ' + $captureRoot + '.zip')
    }
} catch {
    Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    $exitCode = 1
}
if (-not $NoPause) { [void](Read-Host 'Press Enter to close') }
exit $exitCode
