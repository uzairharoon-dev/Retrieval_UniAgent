param(
    [string]$SourceRoot = 'C:\Users\umair\Desktop\uniagent-code'
)

$ErrorActionPreference = 'Stop'
$SourceRoot = (Resolve-Path -LiteralPath $SourceRoot).Path
$projectRoot = Split-Path -Parent $PSScriptRoot
$targetRoot = Join-Path $projectRoot 'vendor/uniagent-code'
$baselineRelative = 'cikm26/baselines/retrieval-baseline-pyterrier'
if (-not (Test-Path -LiteralPath (Join-Path $SourceRoot "$baselineRelative/baseline.py"))) {
    throw 'SourceRoot must contain the official UniAgent repository.'
}
New-Item -ItemType Directory -Force -Path (Join-Path $targetRoot $baselineRelative),
    (Join-Path $targetRoot 'cikm26/datasets') | Out-Null
Copy-Item -LiteralPath (Join-Path $SourceRoot 'AGENTS.md') -Destination $targetRoot
Get-ChildItem -LiteralPath (Join-Path $SourceRoot $baselineRelative) -File -Force |
    Copy-Item -Destination (Join-Path $targetRoot $baselineRelative)
foreach ($datasetName in @('retrieval-de-spot-check', 'retrieval-en-spot-check',
    'retrieval-hessian-law-de-spot-check')) {
    $destination = Join-Path $targetRoot "cikm26/datasets/$datasetName"
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $SourceRoot "cikm26/datasets/$datasetName") -File |
        Copy-Item -Destination $destination
}
foreach ($directoryName in @('evaluation', 'event-logging-contract')) {
    $destination = Join-Path $targetRoot "cikm26/$directoryName"
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $SourceRoot "cikm26/$directoryName") -File |
        Copy-Item -Destination $destination
}
Get-ChildItem -LiteralPath $SourceRoot -File |
    Where-Object { $_.Name -match '^(LICENSE|COPYING|NOTICE)' } |
    Copy-Item -Destination $targetRoot
Write-Host "Task 1 source and data prepared at $targetRoot"
