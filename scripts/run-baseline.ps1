param(
    [switch]$SkipBuild,
    [ValidateSet('baseline', 'long-tokens', 'fusion', 'compound', 'deduplicated', 'passages')]
    [string]$Variant = 'baseline',
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    [string]$RunName = ('bm25-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$officialRoot = Join-Path $projectRoot 'vendor/uniagent-code/cikm26'
$datasetRoot = Join-Path $officialRoot 'datasets'
$outputRoot = Join-Path $projectRoot "runs/$RunName"
$reportRoot = Join-Path $projectRoot "reports/$RunName"
$imageName = 'uniagent-task1-runner:baseline'
if ($Variant -eq 'long-tokens') { $imageName = 'uniagent-task1-bm25:long-tokens' }
if ($Variant -eq 'fusion') { $imageName = 'uniagent-task1-bm25:fusion' }
if ($Variant -in @('compound', 'deduplicated', 'passages')) { $imageName = 'uniagent-task1-bm25:representations' }

function Invoke-Docker {
    param([string[]]$DockerArguments)
    & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) { throw "Docker failed with exit code $LASTEXITCODE" }
}

if (Test-Path -LiteralPath $outputRoot) {
    throw "Run directory already exists. Choose a new -RunName: $outputRoot"
}
New-Item -ItemType Directory -Force -Path $outputRoot, $reportRoot | Out-Null
Write-Host "Run: $RunName"
if (-not $SkipBuild) {
    Invoke-Docker -DockerArguments @('build', '--tag', 'uniagent-task1-bm25:baseline',
        (Join-Path $officialRoot 'baselines/retrieval-baseline-pyterrier'))
    Invoke-Docker -DockerArguments @('build', '--tag', 'uniagent-task1-runner:baseline', '--file',
        (Join-Path $PSScriptRoot 'Dockerfile.evaluation'), $PSScriptRoot)
    if ($Variant -ne 'baseline') {
        Invoke-Docker -DockerArguments @('build', '--tag', $imageName, (Join-Path $projectRoot 'retrieval'))
    }
}
$mounts = @('--mount', "type=bind,source=$datasetRoot,target=/datasets,readonly",
    '--mount', "type=bind,source=$outputRoot,target=/outputs",
    '--mount', "type=bind,source=$PSScriptRoot,target=/scripts,readonly",
    '--mount', "type=bind,source=$reportRoot,target=/reports")

Invoke-Docker -DockerArguments (@('run', '--rm', '--network', 'none') + $mounts +
    @('--entrypoint', 'python3', $imageName, '/scripts/report.py', 'audit'))

foreach ($datasetName in @('retrieval-de-spot-check', 'retrieval-en-spot-check',
    'retrieval-hessian-law-de-spot-check')) {
    Write-Host "Running BM25: $datasetName"
    $entryScript = '/app/baseline.py'
    $modelArguments = @('--wmodel', 'BM25')
    if ($Variant -eq 'fusion') { $entryScript = '/app/fusion_system.py'; $modelArguments = @() }
    if ($Variant -in @('compound', 'deduplicated', 'passages')) {
        $entryScript = '/app/representation_system.py'
        $modelArguments = @('--mode', $Variant)
    }
    Invoke-Docker -DockerArguments (@('run', '--rm', '--network', 'none', '--cpus', '4') +
        $mounts + @('--entrypoint', 'python3', $imageName, $entryScript,
        '--dataset', "/datasets/$datasetName", '--output', "/outputs/$datasetName") + $modelArguments)
    Invoke-Docker -DockerArguments (@('run', '--rm', '--network', 'none') + $mounts +
        @('--entrypoint', 'python3', $imageName, '/scripts/report.py', 'evaluate',
        '--dataset', $datasetName))
}
Write-Host "Completed. Reports: $reportRoot"
