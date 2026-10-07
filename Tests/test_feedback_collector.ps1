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
[info] ChainMorningstarVR 1.0.0-audit5 loading: INVESTIGATION BUILD
[info] CMS native pose restored before sweep: displacementM=0.52 total=1 held=true
[info] CMS head stability: step=500 held=true targetStepM=0 rotationStepRad=0 sweepRecoveryM=0 poseRestores=1
[info] CMS offhand input registered: button=left-trigger mask=0x200000000 priority=65 final-filter=true side-grip=unchanged
[info] Native head attached: generation=1
[info] CMS motion audio: cue=iron-scrape state=start accepted=true volume=0.2
[info] CMS motion audio: cue=air-cut state=start accepted=true volume=0.2
[info] CMS equipment-drop audio: cue=disarm-strike accepted=true
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
[info] CMS certified contact: part=1 slot=head surface=head-body outcome=drop
[info] CMS certified contact: part=2 slot=left-hand surface=left-hand-body outcome=kept-by-one-third-draw
[info] CMS certified contact: part=3 slot=right-hand surface=held-item-mesh outcome=no-eligible-worn-instance
[info] CMS equipment drop: actor=00000001, item=00000002, reference=00000003, impact=3
[warn] CMS equipment drop returned no reference: actor=00000001
'@
[IO.File]::WriteAllText($fixture, $payload)

function Run-Launcher([string]$Launcher, [string]$OutputFolder = (Split-Path $Launcher -Parent)) {
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $env:ComSpec
    $info.Arguments = '/d /s /c ""' + $Launcher + '" --no-pause"'
    $info.UseShellExecute = $false
    $info.EnvironmentVariables['CMS_FEEDBACK_OUTPUT'] = $OutputFolder
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
    foreach ($folder in @('plain', 'folder with spaces', 'ログ収集 用 (テスト)', 'CMS [audit5]', 'archive viewer only CMD')) {
        $target = Join-Path $testRoot $folder
        New-Item -ItemType Directory -Path $target | Out-Null
        foreach ($name in @('Collect_CMS_Logs.cmd')) {
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
            if ($summary.head_stability_entries -ne 1 -or $summary.native_pose_restore_entries -ne 1 -or
                $summary.native_pose_restore_max_displacement_m -ne 0.52 -or
                $summary.scrape_audio_start_entries -ne 1 -or $summary.air_audio_start_entries -ne 1 -or
                $summary.equipment_drop_audio_accepted_entries -ne 1 -or $summary.summary_error -or
                $summary.cms_version -ne '1.0.0-audit5' -or $summary.offhand_held_entries -ne 3 -or
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
                $summary.equipment_lottery_draws -ne 3 -or $summary.equipment_lottery_wins -ne 1 -or
                $summary.equipment_drop_missing_references -ne 1 -or
                $summary.certified_contact_slots.head -ne 1 -or
                $summary.certified_contact_slots.'left-hand' -ne 1 -or
                $summary.certified_contact_slots.'right-hand' -ne 1 -or
                $summary.certified_contact_surfaces.'head-body' -ne 1 -or
                $summary.certified_contact_surfaces.'left-hand-body' -ne 1 -or
                $summary.certified_contact_surfaces.'held-item-mesh' -ne 1 -or
                $summary.certified_contact_outcomes.'no-eligible-worn-instance' -ne 1 -or
                $summary.certified_contact_outcomes.'kept-by-one-third-draw' -ne 2 -or
                $summary.certified_contact_outcomes.drop -ne 1 -or $summary.release_gates_passed) {
                throw 'Runtime evidence was misclassified'
            }
        } finally { $zip.Dispose() }
        Write-Host "COLLECTOR_PATH_PASS $folder"
    }

    # A locked optional log used to stop Copy-Item before any ZIP existed.
    $lockedPath = Join-Path $logRoot 'higgs_vr.log'
    if (Test-Path -LiteralPath $lockedPath) { throw 'Refusing to overwrite an existing HIGGS log' }
    $locked = [IO.File]::Open($lockedPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    try {
        $target = Join-Path $testRoot 'locked optional log'
        New-Item -ItemType Directory -Path $target | Out-Null
        $launcher = Join-Path $target 'Collect_CMS_Logs.cmd'
        Copy-Item (Join-Path $repository 'Tools/Collect_CMS_Logs.cmd') $launcher
        $run = Run-Launcher $launcher
        if ($run.Code -ne 0) { throw "Locked optional log blocked ZIP: $($run.Err)" }
        $archive = @(Get-ChildItem -LiteralPath $target -Filter '*.zip')[0]
        $zip = [IO.Compression.ZipFile]::OpenRead($archive.FullName)
        try {
            $reader = [IO.StreamReader]::new($zip.GetEntry('collection.txt').Open())
            try { if ($reader.ReadToEnd() -notmatch 'LOG ERROR: SKSE\\higgs_vr.log') { throw 'Missing locked-log explanation' } }
            finally { $reader.Dispose() }
            if (-not $zip.GetEntry('ChainMorningstarVR.log')) { throw 'Readable log was not collected' }
        } finally { $zip.Dispose() }
        Write-Host 'COLLECTOR_LOCKED_LOG_PASS'
    } finally { $locked.Dispose(); Remove-Item -LiteralPath $lockedPath -Force }

    # Failure while summarizing must preserve the copied logs and generate ZIP.
    [IO.File]::WriteAllText($fixture,$payload+"`r`nCMS native pose restored before sweep: displacementM=1e9999")
    $target = Join-Path $testRoot 'invalid numeric log'
    New-Item -ItemType Directory -Path $target | Out-Null
    $launcher = Join-Path $target 'Collect_CMS_Logs.cmd'
    Copy-Item (Join-Path $repository 'Tools/Collect_CMS_Logs.cmd') $launcher
    $run = Run-Launcher $launcher
    if ($run.Code -ne 0 -or @(Get-ChildItem -LiteralPath $target -Filter '*.zip').Count -ne 1) {
        throw "Summary error blocked archive: $($run.Err)"
    }
    Write-Host 'COLLECTOR_SUMMARY_FAILURE_PASS'
    [IO.File]::WriteAllText($fixture,$payload)

    # An unwritable/invalid selected output must choose a writable fallback.
    $blocker = Join-Path $testRoot 'file instead of directory'
    [IO.File]::WriteAllText($blocker,'blocks directory creation')
    $run = Run-Launcher $launcher $blocker
    $created = [regex]::Match($run.Out,'(?m)^Created: (.+)')
    if ($run.Code -ne 0 -or -not $created.Success) { throw "No output fallback: $($run.Err)" }
    $fallback = $created.Groups[1].Value.Trim()
    if (-not [IO.File]::Exists($fallback) -or $fallback.StartsWith($blocker)) { throw 'Invalid fallback ZIP' }
    Remove-Item -LiteralPath $fallback -Force
    Remove-Item -LiteralPath ($fallback.Substring(0,$fallback.Length-4)) -Recurse -Force
    Write-Host 'COLLECTOR_OUTPUT_FALLBACK_PASS'

    $failure = Join-Path $testRoot 'expected-failure'
    New-Item -ItemType Directory -Path $failure | Out-Null
    $launcherText = [IO.File]::ReadAllText((Join-Path $repository 'Tools/Collect_CMS_Logs.cmd'))
    $marker = '# CMS_EMBEDDED_POWERSHELL'
    $launcherText = $launcherText.Substring(0,$launcherText.LastIndexOf($marker)+$marker.Length)+"`r`nthrow 'Synthetic failure'`r`n"
    [IO.File]::WriteAllText((Join-Path $failure 'Collect_CMS_Logs.cmd'),$launcherText)
    $failed = Run-Launcher (Join-Path $failure 'Collect_CMS_Logs.cmd')
    if ($failed.Code -eq 0) { throw 'Launcher swallowed the PowerShell failure' }
    Write-Host 'COLLECTOR_ERROR_EXIT_PASS'
} finally {
    Remove-Item -LiteralPath $fixture -Force
    Remove-Item -LiteralPath $testRoot -Recurse -Force
}
