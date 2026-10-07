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
$report.Add('ChainMorningstarVR feedback (version read from the collected log)')
$report.Add("Collected: $timestamp")
foreach ($relative in $logFiles) {
    $source = Join-Path $logRoot $relative
    if (Test-Path -LiteralPath $source -PathType Leaf) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $stage ([IO.Path]::GetFileName($relative)))
        $report.Add("LOG FOUND: $relative")
    } else { $report.Add("LOG MISSING: $relative") }
}
$cmsLog = Join-Path $stage 'ChainMorningstarVR.log'
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
    equipment_drop_references = 0
    release_gates_passed = $false
}
if ($summary.cms_log_present) {
    $cmsText = [IO.File]::ReadAllText($cmsLog)
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
    foreach ($match in [regex]::Matches($cmsText, 'CMS offhand grip attempt: result=rejected reason=([^\s]+)')) {
        $key = $match.Groups[1].Value
        if (-not $summary.offhand_rejected_reasons.Contains($key)) { $summary.offhand_rejected_reasons[$key] = 0 }
        $summary.offhand_rejected_reasons[$key]++
    }
    foreach ($match in [regex]::Matches($cmsText, 'CMS certified contact:[^\r\n]*outcome=([^\s]+)')) {
        $key = $match.Groups[1].Value
        if (-not $summary.certified_contact_outcomes.Contains($key)) { $summary.certified_contact_outcomes[$key] = 0 }
        $summary.certified_contact_outcomes[$key]++
    }
}
$report.Add("CMS version in log: $($summary.cms_version)")
$summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $stage 'runtime_summary.json') -Encoding UTF8
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
