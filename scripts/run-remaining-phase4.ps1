$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
foreach ($variant in @('compound', 'deduplicated', 'passages')) {
    $runName = "phase4-$variant"
    & (Join-Path $PSScriptRoot 'run-baseline.ps1') -Variant $variant -RunName $runName -SkipBuild
    $references = @('bm25-20261012-231608', 'phase4-long-tokens-64', 'phase4-rrf60-isolated')
    if ($variant -ne 'compound') { $references += 'phase4-compound' }
    foreach ($reference in $references) {
        & docker run --rm --network none --mount "type=bind,source=$projectRoot,target=/workspace" `
            --entrypoint python3 uniagent-task1-runner:baseline /workspace/scripts/compare-runs.py `
            --baseline $reference --candidate $runName --output-name "comparison-$reference.json"
        if ($LASTEXITCODE -ne 0) { throw "Comparison failed: $reference / $runName" }
    }
}
Write-Host 'All remaining Phase 4 runs and comparisons completed.'
