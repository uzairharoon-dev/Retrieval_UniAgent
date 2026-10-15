$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$sourceRoot = Join-Path $projectRoot 'vendor/uniagent-code/cikm26/datasets'
$inputRoot = Join-Path $projectRoot 'runs/phase5-inputs'
$validationRoot = Join-Path $projectRoot 'reports/phase5'
$image = 'uniagent-task1-bm25:representations'
$datasets = @('retrieval-de-spot-check', 'retrieval-en-spot-check', 'retrieval-hessian-law-de-spot-check')
function Invoke-Docker {
    param([string[]]$Arguments)
    $result = & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker failed ($LASTEXITCODE): $Arguments" }
    return $result
}
if (Test-Path -LiteralPath $inputRoot) { throw 'Phase 5 inputs already exist; refusing to overwrite validation.' }
New-Item -ItemType Directory -Path $inputRoot, $validationRoot -Force | Out-Null
$inputs = @()
foreach ($dataset in $datasets) {
    $target = Join-Path $inputRoot $dataset
    New-Item -ItemType Directory -Path $target | Out-Null
    foreach ($filename in @('documents.jsonl.gz', 'queries.jsonl')) {
        $source = Join-Path (Join-Path $sourceRoot $dataset) $filename
        $destination = Join-Path $target $filename
        Copy-Item -LiteralPath $source -Destination $destination
        $hash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()) { throw 'Input copy differs' }
        $inputs += @{dataset=$dataset; file=$filename; sha256=$hash}
    }
}
$inputs | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 (Join-Path $validationRoot 'inputs.json')
Invoke-Docker -Arguments @('image', 'inspect', $image) | Set-Content -Encoding UTF8 (Join-Path $validationRoot 'image.json')
$executions = @()
foreach ($mode in @('passages', 'deduplicated')) {
    $runName = "phase5-$mode"
    $outputs = Join-Path $projectRoot "runs/$runName"
    $reports = Join-Path $projectRoot "reports/$runName"
    if (Test-Path -LiteralPath $outputs) { throw "Existing run: $outputs" }
    New-Item -ItemType Directory -Path $outputs, $reports | Out-Null
    $evaluationMounts = @('--mount', "type=bind,source=$sourceRoot,target=/datasets,readonly",
        '--mount', "type=bind,source=$outputs,target=/outputs",
        '--mount', "type=bind,source=$PSScriptRoot,target=/scripts,readonly",
        '--mount', "type=bind,source=$reports,target=/reports")
    Invoke-Docker -Arguments (@('run', '--rm', '--network', 'none') + $evaluationMounts +
        @('--entrypoint', 'python3', $image, '/scripts/report.py', 'audit')) | Out-File (Join-Path $reports 'audit.log')
    foreach ($dataset in $datasets) {
        $inputPath = Join-Path $inputRoot $dataset
        $outputPath = Join-Path $outputs $dataset
        New-Item -ItemType Directory -Path $outputPath | Out-Null
        $container = "$runName-$dataset"
        $create = @('create', '--name', $container, '--network', 'none', '--cpus', '4',
            '--memory', '3g', '--memory-swap', '3g',
            '--mount', "type=bind,source=$inputPath,target=/input,readonly",
            '--mount', "type=bind,source=$outputPath,target=/output",
            '--entrypoint', 'python3', $image, '/app/representation_system.py',
            '--dataset', '/input', '--output', '/output', '--mode', $mode)
        Invoke-Docker -Arguments $create | Out-Null
        Invoke-Docker -Arguments @('inspect', $container) | Set-Content -Encoding UTF8 (Join-Path $reports "$dataset-container.json")
        Write-Host "Validating $mode / $dataset (4 CPUs, 3 GiB, no swap, no labels)"
        $timer = [System.Diagnostics.Stopwatch]::StartNew()
        Invoke-Docker -Arguments @('start', '--attach', $container) | Out-File (Join-Path $reports "$dataset-retrieval.log")
        $timer.Stop()
        $state = (Invoke-Docker -Arguments @('inspect', '--format', '{{json .State}}', $container)) | ConvertFrom-Json
        if ($state.ExitCode -ne 0 -or $state.OOMKilled) { throw "Container failed: $container" }
        $executions += @{run=$runName; dataset=$dataset; wall_seconds=$timer.Elapsed.TotalSeconds; state=$state}
        $executions | ConvertTo-Json -Depth 15 | Set-Content -Encoding UTF8 (Join-Path $validationRoot 'executions.json')
        Invoke-Docker -Arguments @('rm', $container) | Out-Null
        Invoke-Docker -Arguments (@('run', '--rm', '--network', 'none') + $evaluationMounts +
            @('--entrypoint', 'python3', $image, '/scripts/report.py', 'evaluate', '--dataset', $dataset)) |
            Out-File (Join-Path $reports "$dataset-evaluation.log")
        Write-Host "Validated $mode / $dataset in $([math]::Round($timer.Elapsed.TotalSeconds, 1)) seconds"
    }
}
Write-Host 'Phase 5 fresh retrieval and separate evaluation completed.'
