param([switch]$Check, [switch]$Sync)

# Source is authoritative; no arguments means a read-only check.
# Only -Sync exports source. Never copy ciphertext or skip unreadable inputs.
$ErrorActionPreference = 'Stop'
if ($Check -and $Sync) { throw 'Use either -Check or -Sync.' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$templateRoot = Join-Path $repo 'runtime_templates'
$utf8 = New-Object System.Text.UTF8Encoding($false, $true)
$rg = (Get-Command rg -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$previousConsoleEncoding = [Console]::OutputEncoding
$previousOutputEncoding = $OutputEncoding

function ConvertTo-TemplateText([string]$text) {
    if ($text.Contains([char]0) -or $text.Contains('%TSD-Header-###%')) {
        throw 'Encrypted or binary content was returned instead of plaintext.'
    }
    $text = $text.TrimStart([char]0xFEFF).Replace([string][char]13 + [char]10, [string][char]10).Replace([string][char]13, [string][char]10)
    if ($text.Length -and -not $text.EndsWith([string][char]10)) { $text += [char]10 }
    return $text
}

function Read-ContainerTemplate([string]$path) {
    # Docker copies raw bytes; an authorized rg read could hide ciphertext.
    # Strict UTF-8 plus header/NUL validation must succeed without decryption.
    return ConvertTo-TemplateText ($utf8.GetString([IO.File]::ReadAllBytes($path)))
}

function Read-Plaintext([string]$path) {
    # rg is the authorized transparent-encryption reader. JSON preserves blank
    # lines and distinguishes invalid UTF-8 (base64 bytes) from readable text.
    $records = @(& $rg --no-config --json --text --no-mmap --color never '^' -- $path)
    $readerExit = $LASTEXITCODE
    if ($readerExit -notin @(0, 1)) { throw "Plaintext reader failed (exit $readerExit)." }
    if ($readerExit -eq 1) {
        if ((Get-Item -LiteralPath $path).Length -ne 0) { throw 'Non-empty file returned no readable text.' }
        return ''
    }
    $builder = New-Object System.Text.StringBuilder
    $matches = 0
    foreach ($record in $records) {
        $item = $record | ConvertFrom-Json
        if ($item.type -ne 'match') { continue }
        if ($null -eq $item.data.lines.text) { throw 'Plaintext is not valid UTF-8.' }
        [void]$builder.Append([string]$item.data.lines.text)
        $matches += 1
    }
    if (-not $matches) { throw 'Plaintext reader returned no match records.' }
    return ConvertTo-TemplateText $builder.ToString()
}

try {
    [Console]::OutputEncoding = $utf8
    $OutputEncoding = $utf8
    $paths = @{}
    if (Test-Path -LiteralPath $templateRoot) {
        Get-ChildItem -LiteralPath $templateRoot -Recurse -File -Filter '*.tmpl' | ForEach-Object {
            $relative = $_.FullName.Substring($templateRoot.Length + 1)
            $paths[$relative.Substring(0, $relative.Length - 5)] = $true
        }
    }
    # Include new application modules/tests/migrations before their first build.
    foreach ($directory in @('plm', 'config')) {
        $sourceRoot = Join-Path $repo $directory
        if (Test-Path -LiteralPath $sourceRoot) {
            Get-ChildItem -LiteralPath $sourceRoot -Recurse -File -Filter '*.py' | ForEach-Object {
                $paths[$_.FullName.Substring($repo.Length + 1)] = $true
            }
        }
    }
    $pending = @()
    $invalid = @()
    foreach ($relative in ($paths.Keys | Sort-Object)) {
        try {
            $source = Join-Path $repo $relative
            $template = Join-Path $templateRoot ($relative + '.tmpl')
            if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw 'Missing local source.' }
            $text = Read-Plaintext $source
            $exists = Test-Path -LiteralPath $template -PathType Leaf
            $existing = if ($exists) { Read-ContainerTemplate $template } else { $null }
            if (-not $exists -or $existing -cne $text) {
                $pending += [pscustomobject]@{
                    Relative = $relative; Source = $source; Path = $template
                    Text = $text; Existing = $existing; Existed = $exists
                    Stage = $null; Backup = $null; Committed = $false
                }
            }
        } catch {
            # Report failed paths, never protected file contents.
            $invalid += "$relative : $($_.Exception.Message)"
        }
    }
    if ($invalid.Count) {
        $message = "Plaintext validation failed; no templates written:" + [char]10 + ($invalid -join [char]10)
        if ($pending.Count) { $message += [char]10 + "Readable files with drift:" + [char]10 + (($pending | ForEach-Object { $_.Relative }) -join [char]10) }
        throw $message
    }
    if (-not $Sync) {
        if ($pending.Count) { throw ("runtime_templates drift detected (read-only check):" + [char]10 + (($pending | ForEach-Object { $_.Relative }) -join [char]10)) }
        Write-Output ("runtime_templates match {0} readable source files." -f $paths.Count)
        return
    }

    # Validate all inputs before staging. Each same-volume replacement is
    # atomic; retain originals until the batch succeeds for rollback on error.
    $createdDirectories = New-Object 'System.Collections.Generic.List[string]'
    $rollbackErrors = @()
    try {
        foreach ($entry in $pending) {
            $directory = Split-Path -Parent $entry.Path
            $missing = @()
            $cursor = $directory
            while (-not (Test-Path -LiteralPath $cursor -PathType Container)) {
                $missing += $cursor
                $cursor = Split-Path -Parent $cursor
            }
            for ($i = $missing.Count - 1; $i -ge 0; $i--) {
                [void][IO.Directory]::CreateDirectory($missing[$i])
                $createdDirectories.Add($missing[$i])
            }
            $entry.Stage = Join-Path $directory ('.sync-' + [guid]::NewGuid().ToString('N') + '.tmp')
            $entry.Backup = Join-Path $directory ('.sync-' + [guid]::NewGuid().ToString('N') + '.bak')
            [IO.File]::WriteAllText($entry.Stage, $entry.Text, $utf8)
            if ((Read-ContainerTemplate $entry.Stage) -cne $entry.Text) { throw "Staged plaintext mismatch: $($entry.Relative)" }
        }
        # Refuse to overwrite a source/template changed during validation.
        foreach ($entry in $pending) {
            if ((Read-Plaintext $entry.Source) -cne $entry.Text) { throw "Source changed during sync: $($entry.Relative)" }
            $exists = Test-Path -LiteralPath $entry.Path -PathType Leaf
            if ($exists -ne $entry.Existed) { throw "Template changed during sync: $($entry.Relative)" }
            if ($exists -and (Read-ContainerTemplate $entry.Path) -cne $entry.Existing) { throw "Template changed during sync: $($entry.Relative)" }
        }
        foreach ($entry in $pending) {
            if ($entry.Existed) { [IO.File]::Replace($entry.Stage, $entry.Path, $entry.Backup) }
            else { [IO.File]::Move($entry.Stage, $entry.Path) }
            $entry.Committed = $true
        }
    } catch {
        $failure = $_
        for ($i = $pending.Count - 1; $i -ge 0; $i--) {
            $entry = $pending[$i]
            if (-not $entry.Committed) { continue }
            try {
                if ($entry.Existed) { [IO.File]::Replace($entry.Backup, $entry.Path, $entry.Stage) }
                else { [IO.File]::Delete($entry.Path) }
                $entry.Committed = $false
            } catch { $rollbackErrors += "$($entry.Relative) (backup: $($entry.Backup))" }
        }
        if ($rollbackErrors.Count) { throw ("Sync failed; manual rollback needed for:" + [char]10 + ($rollbackErrors -join [char]10)) }
        throw $failure
    } finally {
        foreach ($entry in $pending) {
            if ($entry.Stage -and (Test-Path -LiteralPath $entry.Stage)) { [IO.File]::Delete($entry.Stage) }
            # Preserve backups if rollback itself failed.
            if ($entry.Backup -and (Test-Path -LiteralPath $entry.Backup) -and -not $rollbackErrors.Count) { [IO.File]::Delete($entry.Backup) }
        }
        for ($i = $createdDirectories.Count - 1; $i -ge 0; $i--) {
            $directory = $createdDirectories[$i]
            if ((Test-Path -LiteralPath $directory) -and -not @(Get-ChildItem -LiteralPath $directory -Force).Count) { [IO.Directory]::Delete($directory) }
        }
    }
    Write-Output ("Exported {0} source files to runtime_templates; checked {1}." -f $pending.Count, $paths.Count)
} finally {
    [Console]::OutputEncoding = $previousConsoleEncoding
    $OutputEncoding = $previousOutputEncoding
}
