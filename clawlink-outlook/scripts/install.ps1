[CmdletBinding()]
param(
    [string]$HermesHome = $(
        if ($env:HERMES_HOME) { $env:HERMES_HOME }
        elseif ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'hermes' }
        else { Join-Path $HOME '.hermes' }
    ),
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $projectRoot 'skill\outlook-clawlink-triage'
$target = Join-Path $HermesHome 'skills\email\outlook-clawlink-triage'
$skillFile = Join-Path $source 'SKILL.md'

if (-not (Test-Path -LiteralPath $skillFile)) {
    throw "Skill source not found: $skillFile"
}

Write-Output "Skill source: $source"
Write-Output "Hermes target: $target"

if ($DryRun) {
    Write-Output 'Dry run: no changes made.'
    return
}

$parent = Split-Path -Parent $target
New-Item -ItemType Directory -Force -Path $parent | Out-Null

if (Test-Path -LiteralPath $target) {
    $item = Get-Item -LiteralPath $target -Force
    if ($item.LinkType -eq 'Junction' -or $item.LinkType -eq 'SymbolicLink') {
        [System.IO.Directory]::Delete($target, $false)
        Write-Output 'Removed existing skill link.'
    }
    else {
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $backup = "$target.bak-$stamp"
        Move-Item -LiteralPath $target -Destination $backup
        Write-Output "Moved existing skill directory to $backup"
    }
}

New-Item -ItemType Junction -Path $target -Target $source | Out-Null

if (-not (Test-Path -LiteralPath (Join-Path $target 'SKILL.md'))) {
    throw "Skill link verification failed: $target"
}

Write-Output 'Linked skill into the Hermes profile.'
if (Get-Command hermes -ErrorAction SilentlyContinue) {
    hermes skills list --source local
}
