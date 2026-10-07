@echo off
setlocal
set "CMS_FEEDBACK_SELF=%~f0"
set "CMS_FEEDBACK_NO_PAUSE=0"
if /i "%~1"=="--no-pause" set "CMS_FEEDBACK_NO_PAUSE=1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$s=[IO.File]::ReadAllText($env:CMS_FEEDBACK_SELF); $marker=[char]35+' CMS_EMBEDDED_POWERSHELL'; & ([scriptblock]::Create($s.Substring($s.LastIndexOf($marker)+$marker.Length))) -OutputDirectory $env:CMS_FEEDBACK_OUTPUT -OpenFolder:($env:CMS_FEEDBACK_NO_PAUSE -ne '1')"
set "CMS_COLLECT_EXIT=%ERRORLEVEL%"
if not "%CMS_COLLECT_EXIT%"=="0" echo Log collection failed. Please send a screenshot of the error above.
if not "%CMS_FEEDBACK_NO_PAUSE%"=="1" pause
exit /b %CMS_COLLECT_EXIT%
# CMS_EMBEDDED_POWERSHELL
param(
    [string]$GameDirectory = "",
    [string]$OutputDirectory = "",
    [switch]$OpenFolder
)
$ErrorActionPreference = 'Stop'
$report = [System.Collections.Generic.List[string]]::new()
$pathWarnings = [System.Collections.Generic.List[string]]::new()
# Desktop is persistent even when Windows runs only the CMD from a ZIP viewer.
$desktop = [Environment]::GetFolderPath('DesktopDirectory')
$local = [Environment]::GetFolderPath('LocalApplicationData')
$candidates = @($OutputDirectory)
if ($desktop) { $candidates += [IO.Path]::Combine($desktop, 'CMS-feedback') }
if ($local) { $candidates += [IO.Path]::Combine($local, 'CMS-feedback') }
$candidates += [IO.Path]::Combine([IO.Path]::GetTempPath(), 'CMS-feedback')
$destination = $null
foreach ($candidate in $candidates) {
    if (-not $candidate) { continue }
    try {
        $candidate = [IO.Path]::GetFullPath($candidate)
        [IO.Directory]::CreateDirectory($candidate) | Out-Null
        $probe = [IO.Path]::Combine($candidate, '.cms-write-probe-' + [guid]::NewGuid().ToString('N'))
        [IO.File]::WriteAllText($probe, 'test')
        [IO.File]::Delete($probe)
        $destination = $candidate
        break
    } catch { $pathWarnings.Add('OUTPUT FALLBACK: ' + $_.Exception.Message) }
}
if (-not $destination) { throw 'No writable output folder. Take a screenshot of this error.' }
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$stage = [IO.Path]::Combine($destination, 'CMS-feedback-' + $timestamp + '-' + [guid]::NewGuid().ToString('N').Substring(0,6))
[IO.Directory]::CreateDirectory($stage) | Out-Null
$report.Add('ChainMorningstarVR feedback collector audit5')
$report.Add("Collected: $timestamp")
foreach ($message in $pathWarnings) { $report.Add($message) }
$documents = [Environment]::GetFolderPath('MyDocuments')
if (-not $documents) { $documents = [IO.Path]::Combine($env:USERPROFILE, 'Documents') }
$logRoot = [IO.Path]::Combine($documents, 'My Games\Skyrim VR')
$logFiles = @('SKSE\ChainMorningstarVR.log', 'SKSE\sksevr.log', 'SKSE\higgs_vr.log', 'SKSE\activeragdoll.log', 'Logs\Script\Papyrus.0.log')
foreach ($relative in $logFiles) {
    $source = [IO.Path]::Combine($logRoot, $relative)
    $target = [IO.Path]::Combine($stage, [IO.Path]::GetFileName($relative))
    if (-not [IO.File]::Exists($source)) { $report.Add("LOG MISSING: $relative"); continue }
    $inputStream = $null; $outputStream = $null
    try {
        # Shared reads work for ordinary live logs. An exclusive lock is noted
        # per file; it never prevents other logs and the report from being zipped.
        $inputStream = [IO.File]::Open($source, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete)
        if ($inputStream.Length -gt 32MB) {
            [void]$inputStream.Seek(-32MB, [IO.SeekOrigin]::End)
            $report.Add("LOG TAIL ONLY (32 MiB): $relative")
        }
        $outputStream = [IO.File]::Create($target)
        $inputStream.CopyTo($outputStream)
        $report.Add("LOG FOUND: $relative")
    } catch { $report.Add("LOG ERROR: $relative : $($_.Exception.Message)") }
    finally {
        if ($inputStream) { $inputStream.Dispose() }
        if ($outputStream) { $outputStream.Dispose() }
    }
}
$cmsLog = [IO.Path]::Combine($stage, 'ChainMorningstarVR.log')
$summary = [ordered]@{
    cms_log_present = (Test-Path -LiteralPath $cmsLog -PathType Leaf)
    cms_version = $null
    offhand_grab_button = $null
    evidence_scope = 'Counts are sampled log entries, not complete event totals. Zero means not observed; it is not proof of failure or success.'
    warning_or_error_lines = 0
    native_head_attachments = 0
    head_stability_entries = 0
    native_pose_restore_entries = 0
    native_pose_restore_max_displacement_m = 0.0
    player_body_contact_entries = 0
    offhand_held_entries = 0
    offhand_released_entries = 0
    offhand_release_reasons = [ordered]@{}
    offhand_release_reason_unknown_entries = 0
    offhand_progress_entries = 0
    offhand_max_observed_hold_ms = 0L
    offhand_selection_guard_entries = 0
    offhand_rejected_reasons = [ordered]@{}
    certified_contact_outcomes = [ordered]@{}
    certified_contact_slots = [ordered]@{}
    certified_contact_surfaces = [ordered]@{}
    equipment_lottery_draws = 0
    equipment_lottery_wins = 0
    equipment_drop_references = 0
    equipment_drop_missing_references = 0
    scrape_audio_start_entries = 0
    air_audio_start_entries = 0
    equipment_drop_audio_accepted_entries = 0
    summary_error = $null
    release_gates_passed = $false
}
try {
if ($summary.cms_log_present) {
    $cmsText = [IO.File]::ReadAllText($cmsLog)
    $summary.scrape_audio_start_entries = [regex]::Matches($cmsText, 'CMS motion audio: cue=iron-scrape state=start accepted=true').Count
    $summary.air_audio_start_entries = [regex]::Matches($cmsText, 'CMS motion audio: cue=air-cut state=start accepted=true').Count
    $summary.equipment_drop_audio_accepted_entries = [regex]::Matches($cmsText, 'CMS equipment-drop audio: cue=disarm-strike accepted=true').Count
    $versions = [regex]::Matches($cmsText, 'ChainMorningstarVR ([0-9][^\s]*) loading:')
    if ($versions.Count) { $summary.cms_version = $versions[$versions.Count - 1].Groups[1].Value }
    $buttons = [regex]::Matches($cmsText, 'CMS offhand input registered: button=([^\s]+)')
    if ($buttons.Count) { $summary.offhand_grab_button = $buttons[$buttons.Count - 1].Groups[1].Value }
    $summary.warning_or_error_lines = [regex]::Matches($cmsText, '\[(warn|warning|error|critical)\]').Count
    $summary.native_head_attachments = [regex]::Matches($cmsText, 'Native head attached:').Count
    $summary.head_stability_entries = [regex]::Matches($cmsText, 'CMS head stability:').Count
    $summary.native_pose_restore_entries = [regex]::Matches($cmsText, 'CMS native pose restored before sweep:').Count
    foreach ($match in [regex]::Matches($cmsText, 'CMS native pose restored before sweep: displacementM=([0-9.eE+\-]+)')) {
        $distance = [double]::Parse($match.Groups[1].Value, [Globalization.CultureInfo]::InvariantCulture)
        $summary.native_pose_restore_max_displacement_m = [Math]::Max($summary.native_pose_restore_max_displacement_m, $distance)
    }
    $summary.player_body_contact_entries = [regex]::Matches($cmsText, 'CMS player-body chain contact:').Count
    $summary.offhand_held_entries = [regex]::Matches($cmsText, 'CMS offhand head grip: held\b').Count
    $summary.offhand_released_entries = [regex]::Matches($cmsText, 'CMS offhand head grip: released\b').Count
    $summary.offhand_progress_entries = [regex]::Matches($cmsText, 'CMS offhand hold progress:').Count
    $releases = [regex]::Matches($cmsText, 'CMS offhand head grip: released\b[^\r\n]*')
    foreach ($release in $releases) {
        $reason = [regex]::Match($release.Value, '\breason=([^\s]+)')
        if ($reason.Success) {
            $key = $reason.Groups[1].Value
            if (-not $summary.offhand_release_reasons.Contains($key)) { $summary.offhand_release_reasons[$key] = 0 }
            $summary.offhand_release_reasons[$key]++
        } else { $summary.offhand_release_reason_unknown_entries++ }
    }
    foreach ($match in [regex]::Matches($cmsText, 'CMS offhand (?:head grip: released|hold progress:)[^\r\n]*\bheldMs=([0-9]+)')) {
        $duration = [long]::Parse($match.Groups[1].Value, [Globalization.CultureInfo]::InvariantCulture)
        $summary.offhand_max_observed_hold_ms = [Math]::Max($summary.offhand_max_observed_hold_ms, $duration)
    }
    $summary.offhand_selection_guard_entries = [regex]::Matches($cmsText, 'CMS offhand selection guard: rejectedPickPairs=[1-9][0-9]*\b').Count
    $summary.equipment_drop_references = [regex]::Matches($cmsText, 'CMS equipment drop: actor=[0-9A-Fa-f]+, item=[0-9A-Fa-f]+, reference=[0-9A-Fa-f]+,').Count
    $summary.equipment_drop_missing_references = [regex]::Matches($cmsText, 'CMS equipment drop returned no reference:').Count
    foreach ($match in [regex]::Matches($cmsText, 'CMS offhand grip attempt: result=rejected reason=([^\s]+)')) {
        $key = $match.Groups[1].Value
        if (-not $summary.offhand_rejected_reasons.Contains($key)) { $summary.offhand_rejected_reasons[$key] = 0 }
        $summary.offhand_rejected_reasons[$key]++
    }
    foreach ($match in [regex]::Matches($cmsText, 'CMS certified contact:[^\r\n]*outcome=([^\s]+)')) {
        $key = $match.Groups[1].Value
        if (-not $summary.certified_contact_outcomes.Contains($key)) { $summary.certified_contact_outcomes[$key] = 0 }
        $summary.certified_contact_outcomes[$key]++
        if ($key -eq 'drop' -or $key -eq 'kept-by-one-third-draw') { $summary.equipment_lottery_draws++ }
        if ($key -eq 'drop') { $summary.equipment_lottery_wins++ }
    }
    foreach ($field in @('slot', 'surface')) {
        $counts = if ($field -eq 'slot') { $summary.certified_contact_slots } else { $summary.certified_contact_surfaces }
        foreach ($match in [regex]::Matches($cmsText, ('CMS certified contact:[^\r\n]*\b' + $field + '=([^\s]+)'))) {
            $key = $match.Groups[1].Value
            if (-not $counts.Contains($key)) { $counts[$key] = 0 }
            $counts[$key]++
        }
    }
}
} catch {
    $summary.summary_error = $_.Exception.Message
    $report.Add('SUMMARY ERROR: ' + $_.Exception.Message)
}
$report.Add("CMS version in log: $($summary.cms_version)")
try {
    $summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ([IO.Path]::Combine($stage, 'runtime_summary.json')) -Encoding UTF8
} catch { $report.Add('SUMMARY WRITE ERROR: ' + $_.Exception.Message) }
if ($GameDirectory) {
    foreach ($relative in @('SkyrimVR.exe', 'Data\ChainMorningstarVR.esp', 'Data\SKSE\Plugins\ChainMorningstarVR.dll', 'Data\meshes\weapons\ChainMorningstarVR\ChainMorningstar.nif')) {
        try {
            $source = [IO.Path]::Combine($GameDirectory, $relative)
            if ([IO.File]::Exists($source)) {
                $hash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLower()
                $report.Add("SHA256 $hash  $relative")
            } else { $report.Add("FILE MISSING: $relative") }
        } catch { $report.Add("FILE ERROR: $relative : $($_.Exception.Message)") }
    }
}
$report | Set-Content -LiteralPath ([IO.Path]::Combine($stage, 'collection.txt')) -Encoding UTF8
$archive = "$stage.zip"
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    # Literal .NET paths handle square brackets; Compress-Archive -Path does not.
    [IO.Compression.ZipFile]::CreateFromDirectory($stage, "$archive.partial", [IO.Compression.CompressionLevel]::Optimal, $false)
    [IO.File]::Move("$archive.partial", $archive)
} catch {
    $message = 'ZIP ERROR: ' + $_.Exception.Message + "`r`nLogs remain in: $stage"
    [IO.File]::WriteAllText([IO.Path]::Combine($stage, 'ZIP_ERROR.txt'), $message)
    Write-Host $message
    throw
}
Write-Host "Created: $archive"
Write-Host 'Attach this ZIP to the conversation. Missing or locked logs are listed in collection.txt.'
if ($OpenFolder) {
    try { Start-Process explorer.exe -ArgumentList ('/select,"' + $archive + '"') }
    catch { Write-Host "Open this folder manually: $destination" }
}
