param(
    [ValidateSet('login', 'dry-run', 'submit', 'status')]
    [string]$Action = 'dry-run',
    [string]$Team,
    [string]$Dataset = 'retrieval-de-spot-check-20260816-training'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if ($projectRoot -notmatch '^([A-Za-z]):\\(.*)$') { throw 'This launcher expects Docker Desktop on Windows.' }
$linuxRoot = '/run/desktop/mnt/host/' + $Matches[1].ToLowerInvariant() + '/' + $Matches[2].Replace('\', '/')
$stateRoot = Join-Path $projectRoot 'runs/tira'
foreach ($directory in @('cache', 'tmp', 'docker')) {
    New-Item -ItemType Directory -Path (Join-Path $stateRoot $directory) -Force | Out-Null
}
$snapshot = Join-Path $stateRoot 'submission'
$linuxSnapshot = "$linuxRoot/runs/tira/submission"
$dockerArguments = @('run', '--rm', '--mount', 'type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock',
    '--mount', "type=bind,source=$projectRoot,target=$linuxRoot",
    '--env', 'DOCKER_HOST=unix:///var/run/docker.sock', '--env', "DOCKER_CONFIG=$linuxRoot/runs/tira/docker",
    '--env', "TIRA_CACHE_DIR=$linuxRoot/runs/tira/cache", '--env', "TMPDIR=$linuxRoot/runs/tira/tmp",
    '--env', 'TERM=xterm', '--env', 'GIT_CONFIG_COUNT=1', '--env', 'GIT_CONFIG_KEY_0=safe.directory',
    '--env', "GIT_CONFIG_VALUE_0=$linuxSnapshot")

if ($Action -eq 'login') {
    & docker @dockerArguments -it --entrypoint python3 uniagent-tira-client:0.0.203 "$linuxRoot/scripts/tira-login.py"
    if ($LASTEXITCODE -ne 0) { throw 'TIRA login did not succeed.' }
    return
}
if ($Action -eq 'status') {
    & docker @dockerArguments --entrypoint python3 uniagent-tira-client:0.0.203 "$linuxRoot/scripts/tira-status.py"
    if ($LASTEXITCODE -ne 0) { throw 'TIRA status check failed.' }
    return
}
if (-not (Test-Path -LiteralPath $snapshot)) {
    New-Item -ItemType Directory -Path $snapshot | Out-Null
    $files = @('baseline.py', 'fusion.py', 'fusion_system.py', 'representations.py', 'representation_system.py',
        'german-stopwords.txt', 'german-stopwords.NOTICE', 'test_baseline.py', 'test_token_length.py',
        'test_fusion.py', 'test_representations.py', '.dockerignore')
    foreach ($file in $files) { Copy-Item -LiteralPath (Join-Path $projectRoot "retrieval/$file") -Destination $snapshot }
    Copy-Item -LiteralPath (Join-Path $projectRoot 'retrieval/Dockerfile.tira') -Destination (Join-Path $snapshot 'Dockerfile')
    Copy-Item -LiteralPath (Join-Path $projectRoot 'retrieval/TIRA.md') -Destination (Join-Path $snapshot 'README.md')
    & git init --initial-branch main $snapshot
    if ($LASTEXITCODE -ne 0) { throw 'Cannot initialize isolated submission snapshot.' }
    & git -C $snapshot remote add origin $projectRoot
    if ($LASTEXITCODE -ne 0) { throw 'Cannot record local source origin.' }
    & git -C $snapshot add --all
    if ($LASTEXITCODE -ne 0) { throw 'Cannot stage isolated submission snapshot.' }
    & git -C $snapshot -c user.name='UniAgent participant' -c user.email='participant@localhost' -c commit.gpgsign=false commit -m 'Package validated passage BM25 for TIRA'
    if ($LASTEXITCODE -ne 0) { throw 'Cannot commit isolated submission snapshot.' }
}
# A repeat cannot silently submit stale code after source changes.
foreach ($file in (Get-ChildItem -LiteralPath $snapshot -File)) {
    $source = Join-Path $projectRoot "retrieval/$($file.Name)"
    if ($file.Name -eq 'Dockerfile') { $source = Join-Path $projectRoot 'retrieval/Dockerfile.tira' }
    if ($file.Name -eq 'README.md') { $source = Join-Path $projectRoot 'retrieval/TIRA.md' }
    if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $file.FullName).Hash) {
        throw "Submission snapshot differs from current source: $($file.Name)"
    }
}
$submissionArguments = @('code-submission', '--path', $linuxSnapshot, '--task', 'uniagent-2026',
    '--dataset', $Dataset, '--platform', 'linux/amd64', '--build-args=--provenance=false',
    '--command', 'python3 /app/representation_system.py --mode passages --dataset $inputDataset --output $outputDir')
if ($Action -eq 'dry-run') { $submissionArguments += '--dry-run' }
if ($Team) { $submissionArguments += @('--tira-vm-id', $Team) }
& docker @dockerArguments uniagent-tira-client:0.0.203 @submissionArguments
if ($LASTEXITCODE -ne 0) { throw "TIRA $Action failed with exit code $LASTEXITCODE" }
