# Runs only on an ephemeral Windows CI runner; seeds synthetic Skyrim logs.
$ErrorActionPreference = 'Stop'
$repository = Split-Path $PSScriptRoot -Parent
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('CMS-collector-test-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $testRoot | Out-Null
$documents = [Environment]::GetFolderPath('MyDocuments')
$logRoot = Join-Path $documents 'My Games\Skyrim VR\SKSE'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$fixture = Join-Path $logRoot 'ChainMorningstarVR.log'
if (Test-Path -LiteralPath $fixture) { throw 'Refusing to overwrite an existing Skyrim log' }
$payload = @'
[info] ChainMorningstarVR 1.0.0-audit2 loading: INVESTIGATION BUILD
[info] CMS offhand input registered: button=left-trigger mask=0x200000000 priority=65 final-filter=true side-grip=unchanged
[info] Native head attached: generation=1
[info] CMS player-body chain contact: samples=2 total=2 damage=false
[info] CMS offhand grip attempt: result=rejected reason=higgs-not-grabbable distanceM=0.10 captured=false
[info] CMS offhand head grip: held physical-left=true right-weapon=true
[info] CMS offhand head grip: released physical-left=true right-weapon=true
[info] CMS offhand head grip: held reason=ready heldMs=0 physical-left=true right-weapon=true
[info] CMS offhand head grip: released reason=input-stale heldMs=141 physical-left=true right-weapon=true
[info] CMS offhand head grip: held reason=ready heldMs=0 physical-left=true right-weapon=true
[info] CMS offhand hold progress: heldMs=502 inputAgeMs=1
[info] CMS offhand hold progress: heldMs=10004 inputAgeMs=1
[info] CMS offhand head grip: released reason=trigger-released heldMs=11003 button=left-trigger physical-left=true right-weapon=true
[info] CMS offhand selection guard: rejectedPickPairs=2 scope=HIGGS-update
[info] CMS certified contact: part=1 outcome=kept-by-one-third-draw
[info] CMS certified contact: part=1 outcome=drop
[info] CMS equipment drop: actor=00000001, item=00000002, reference=00000003, impact=3
[warn] CMS equipment drop returned no reference: actor=00000001
'@
[IO.File]::WriteAllText($fixture, $payload)

function Run-Launcher([string]$Launcher) {
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $env:ComSpec
    $info.Arguments = '/d /s /c ""' + $Launcher + '" --no-pause"'
    $info.UseShellExecute = $false
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $info
    [void]$process.Start()
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit(30000)) {
        $process.Kill()
        throw 'Collector timed out'
    }
    $result = @{ Code = $process.ExitCode; Out = $stdout.Result; Err = $stderr.Result }
    $process.Dispose()
    return $result
}

try {
    # Reproduce the precise old invocation. The final slash escapes its quote
    # in powershell.exe's native argument parsing and reaches New-Item as ".
    $legacy = Join-Path $testRoot 'legacy'
    New-Item -ItemType Directory -Path $legacy | Out-Null
    Copy-Item (Join-Path $repository 'Tools/Collect_CMS_Logs.ps1') $legacy
    $bad = '@echo off',
        'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Collect_CMS_Logs.ps1" -OutputDirectory "%~dp0"',
        'exit /b %ERRORLEVEL%'
    $bad | Set-Content -LiteralPath (Join-Path $legacy 'Collect_CMS_Logs.cmd') -Encoding ascii
    $old = Run-Launcher (Join-Path $legacy 'Collect_CMS_Logs.cmd')
    if ($old.Code -eq 0 -or $old.Err -notmatch 'New-Item') {
        throw "Old trailing-slash bug was not reproduced: $($old.Out) $($old.Err)"
    }
    Write-Host 'LEGACY_TRAILING_SLASH_FAILURE_REPRODUCED'

    foreach ($folder in @('plain', 'folder with spaces', 'ログ収集 用 (テスト)')) {
        $target = Join-Path $testRoot $folder
        New-Item -ItemType Directory -Path $target | Out-Null
        foreach ($name in @('Collect_CMS_Logs.cmd', 'Collect_CMS_Logs.ps1')) {
            Copy-Item (Join-Path $repository "Tools/$name") $target
        }
        $run = Run-Launcher (Join-Path $target 'Collect_CMS_Logs.cmd')
        if ($run.Code -ne 0) { throw "Collector failed in $folder : $($run.Out) $($run.Err)" }
        $archives = @(Get-ChildItem -LiteralPath $target -Filter 'CMS-feedback-*.zip')
        if ($archives.Count -ne 1) { throw "Expected exactly one ZIP in $folder" }
        $zip = [IO.Compression.ZipFile]::OpenRead($archives[0].FullName)
        try {
            $entry = $zip.GetEntry('ChainMorningstarVR.log')
            if (-not $entry) { throw 'Collected log absent from ZIP' }
            $reader = [IO.StreamReader]::new($entry.Open())
            try { if ($reader.ReadToEnd() -ne $payload) { throw 'Log content changed' } }
            finally { $reader.Dispose() }
            if (-not $zip.GetEntry('collection.txt')) { throw 'Collection report absent' }
            $summaryEntry = $zip.GetEntry('runtime_summary.json')
            if (-not $summaryEntry) { throw 'Runtime evidence summary absent' }
            $summaryReader = [IO.StreamReader]::new($summaryEntry.Open())
            try { $summary = $summaryReader.ReadToEnd() | ConvertFrom-Json }
            finally { $summaryReader.Dispose() }
            if ($summary.cms_version -ne '1.0.0-audit2' -or $summary.offhand_held_entries -ne 3 -or
                $summary.offhand_grab_button -ne 'left-trigger' -or
                $summary.offhand_released_entries -ne 3 -or $summary.equipment_drop_references -ne 1 -or
                $summary.offhand_release_reasons.'input-stale' -ne 1 -or
                $summary.offhand_release_reasons.'trigger-released' -ne 1 -or
                $summary.offhand_release_reason_unknown_entries -ne 1 -or
                $summary.offhand_progress_entries -ne 2 -or $summary.offhand_max_observed_hold_ms -ne 11003 -or
                $summary.warning_or_error_lines -ne 1 -or $summary.native_head_attachments -ne 1 -or
                $summary.player_body_contact_entries -ne 1 -or
                $summary.offhand_rejected_reasons.'higgs-not-grabbable' -ne 1 -or
                $summary.offhand_selection_guard_entries -ne 1 -or
                $summary.certified_contact_outcomes.'kept-by-one-third-draw' -ne 1 -or
                $summary.certified_contact_outcomes.drop -ne 1 -or $summary.release_gates_passed) {
                throw 'Runtime evidence was misclassified'
            }
        } finally { $zip.Dispose() }
        Write-Host "COLLECTOR_PATH_PASS $folder"
    }

    $failure = Join-Path $testRoot 'expected-failure'
    New-Item -ItemType Directory -Path $failure | Out-Null
    Copy-Item (Join-Path $repository 'Tools/Collect_CMS_Logs.cmd') $failure
    "throw 'Synthetic failure for exit-code verification'" |
        Set-Content -LiteralPath (Join-Path $failure 'Collect_CMS_Logs.ps1') -Encoding ascii
    $failed = Run-Launcher (Join-Path $failure 'Collect_CMS_Logs.cmd')
    if ($failed.Code -eq 0) { throw 'Launcher swallowed the PowerShell failure' }
    Write-Host 'COLLECTOR_ERROR_EXIT_PASS'
} finally {
    Remove-Item -LiteralPath $fixture -Force
    Remove-Item -LiteralPath $testRoot -Recurse -Force
}
