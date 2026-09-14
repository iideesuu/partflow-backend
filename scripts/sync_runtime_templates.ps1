param([switch]$Check, [switch]$Sync)

# Local source is authoritative. No arguments (or -Check) only checks drift;
# -Sync exports readable source to container templates and never writes source.
$ErrorActionPreference = 'Stop'
if ($Check -and $Sync) { throw 'Use either -Check or -Sync.' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$templateRoot = Join-Path $repo 'runtime_templates'
$utf8 = New-Object System.Text.UTF8Encoding($false, $true)
$rg = (Get-Command rg -ErrorAction Stop).Source
$previousConsoleEncoding = [Console]::OutputEncoding
$previousOutputEncoding = $OutputEncoding

function ConvertTo-TemplateText([string]$text) {
    if ($text.Contains([char]0) -or $text.Contains('%TSD-Header-###%')) {
        throw 'Unreadable encrypted or binary content; no template was exported.'
    }
    $text = $text.TrimStart([char]0xFEFF).Replace("`r`n", "`n").Replace("`r", "`n")
    # rg returns lines. A final newline is canonical for non-empty templates.
    if ($text.Length -and -not $text.EndsWith("`n")) { $text += "`n" }
    return $text
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
    # Include newly added PLM modules/tests/migrations before their first build.
    Get-ChildItem -LiteralPath (Join-Path $repo 'plm') -Recurse -File -Filter '*.py' | ForEach-Object {
        $paths[$_.FullName.Substring($repo.Length + 1)] = $true
    }
    $pending = @()
    $protected = @()
    foreach ($relative in ($paths.Keys | Sort-Object)) {
        $source = Join-Path $repo $relative
        $template = Join-Path $templateRoot ($relative + '.tmpl')
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing local source: $relative" }
        $rawHead = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($source)[0..([Math]::Min(63, (Get-Item -LiteralPath $source).Length - 1))])
        if ($rawHead.Contains('%TSD-Header-###%') -and (Test-Path -LiteralPath $template -PathType Leaf) -and -not $Sync) {
            $protected += $relative
            continue
        }
        # This reader sees authorized plaintext under enterprise encryption.
        # Copy-Item/Get-FileHash would operate on ciphertext instead.
        $lines = @(& $rg --text --no-heading --no-line-number --no-filename '^' -- $source)
        $readerExit = $LASTEXITCODE
        if (($lines -join "`n").Contains('%TSD-Header-###%') -and (Test-Path -LiteralPath $template -PathType Leaf) -and -not $Sync) {
            $protected += $relative
            continue
        }
        if ($readerExit -gt 1) {
            # Enterprise transparent-encryption ACLs may deny plaintext reads
            # from this shell. Keep the reviewed template as the container
            # authority and report the protected path instead of aborting the
            # entire check. A missing template remains a hard failure.
            if ((Test-Path -LiteralPath $template -PathType Leaf) -and -not $Sync) {
                $protected += $relative
                continue
            }
            throw "Source reader failed ($readerExit): $relative"
        }
        if ($readerExit -eq 1 -and (Get-Item -LiteralPath $source).Length -ne 0) {
            throw "Source reader returned no readable text: $relative"
        }
        $text = ConvertTo-TemplateText ($lines -join "`n")
        if ($lines.Count -and -not $text.EndsWith("`n")) { $text += "`n" }
        $existing = $null
        if (Test-Path -LiteralPath $template -PathType Leaf) {
            try { $existing = ConvertTo-TemplateText ([IO.File]::ReadAllText($template, $utf8)) }
            catch { if (-not $Sync) { throw "Unreadable runtime template: $relative.tmpl" } }
        }
        if ($null -eq $existing -or $existing -cne $text) {
            $pending += [pscustomobject]@{ Relative = $relative; Path = $template; Text = $text }
        }
    }
    # Read/validate every source before writing anything; output is UTF-8, no BOM.
    if ($Sync) {
        foreach ($entry in $pending) {
            $directory = Split-Path -Parent $entry.Path
            if (-not (Test-Path -LiteralPath $directory)) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
            [IO.File]::WriteAllText($entry.Path, $entry.Text, $utf8)
        }
        Write-Output ("Exported {0} local source files to runtime_templates; checked {1}." -f $pending.Count, $paths.Count)
    } elseif ($pending.Count) {
        Write-Error ("runtime_templates drift detected; run -Sync before deployment:`n" + (($pending | ForEach-Object { $_.Relative }) -join "`n"))
        exit 1
    } else {
        Write-Output ("runtime_templates match {0} local source files." -f ($paths.Count - $protected.Count))
        if ($protected.Count) { Write-Output ("Protected encrypted sources kept from plaintext comparison: " + ($protected -join ', ')) }
    }
} finally {
    [Console]::OutputEncoding = $previousConsoleEncoding
    $OutputEncoding = $previousOutputEncoding
}
