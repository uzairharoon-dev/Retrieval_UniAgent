param(
    [switch]$SkipBuild,
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
    Invoke-Docker -DockerArguments @('build', '--tag', $imageName, '--file',
        (Join-Path $PSScriptRoot 'Dockerfile.evaluation'), $PSScriptRoot)
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
    Invoke-Docker -DockerArguments (@('run', '--rm', '--network', 'none', '--cpus', '4') +
        $mounts + @('--entrypoint', 'python3', $imageName, '/app/baseline.py',
        '--dataset', "/datasets/$datasetName", '--wmodel', 'BM25',
        '--output', "/outputs/$datasetName"))
    Invoke-Docker -DockerArguments (@('run', '--rm', '--network', 'none') + $mounts +
        @('--entrypoint', 'python3', $imageName, '/scripts/report.py', 'evaluate',
        '--dataset', $datasetName))
}
Write-Host "Completed. Reports: $reportRoot"
