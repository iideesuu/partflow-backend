param(
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$templateRoot = Join-Path $repo 'runtime_templates'
$drift = @()

Get-ChildItem -LiteralPath $templateRoot -Recurse -File -Filter '*.tmpl' | ForEach-Object {
    $relative = $_.FullName.Substring($templateRoot.Length + 1)
    $target = Join-Path $repo $relative.Substring(0, $relative.Length - 5)
    $targetDir = Split-Path -Parent $target
    if (-not (Test-Path -LiteralPath $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }
    $templateHash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    $targetHash = if (Test-Path -LiteralPath $target) { (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash } else { $null }
    if ($templateHash -ne $targetHash) {
        $drift += $relative
        if (-not $Check) { Copy-Item -LiteralPath $_.FullName -Destination $target -Force }
    }
}

if ($Check) {
    if ($drift.Count) {
        Write-Error ("runtime_templates drift detected:`n" + ($drift -join "`n"))
        exit 1
    }
    Write-Output 'runtime_templates and local source are synchronized.'
} elseif ($drift.Count) {
    Write-Output ("Synchronized {0} files from runtime_templates." -f $drift.Count)
} else {
    Write-Output 'runtime_templates and local source were already synchronized.'
}
