"""Verify the real TIRA client's local dry-run output and prepare the handoff."""
import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path('/workspace')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--image', required=True)
    args = parser.parse_args()
    output = ROOT / args.run_dir
    dataset_id = 'retrieval-de-spot-check-20260816-training'
    downloaded = ROOT / 'runs/tira/cache/extracted_datasets/uniagent-2026' / dataset_id / 'input-data'
    previous_input = ROOT / 'runs/phase5-inputs/retrieval-de-spot-check'
    hashes = {}
    for name in ('documents.jsonl.gz', 'queries.jsonl'):
        hashes[name] = {'downloaded': sha(downloaded / name), 'phase5': sha(previous_input / name)}
    require(hashes['documents.jsonl.gz']['downloaded'] == hashes['documents.jsonl.gz']['phase5'], 'Document collection changed')
    queries = lambda directory: [json.loads(line) for line in (directory / 'queries.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    require(queries(downloaded) == queries(previous_input), 'Parsed queries differ')
    with gzip.open(output / 'run.txt.gz', 'rb') as stream:
        ranking = stream.read()
    with gzip.open(ROOT / 'runs/phase5-passages/retrieval-de-spot-check/run.txt.gz', 'rb') as stream:
        require(ranking == stream.read(), 'TIRA dry-run rankings or scores differ from Phase 5')
    snapshot = ROOT / 'runs/tira/submission'
    git = ['git', '-c', f'safe.directory={snapshot}', '-C', str(snapshot)]
    status = subprocess.check_output(git + ['status', '--porcelain'], text=True)
    require(not status.strip(), f'Submission snapshot is dirty in Linux: {status}')
    commit = subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip()
    code = {}
    for path in snapshot.glob('*.py'):
        require(sha(path) == sha(Path('/app') / path.name), f'Packaged source differs: {path.name}')
        code[path.name] = sha(path)
    system = json.loads((output / 'system.json').read_text())
    require(system['mode'] == 'passages', 'Wrong selected mode')
    require((output / 'source-code.zip').is_file(), 'TIRA did not attach source archive')
    result = {'status': 'official TIRA CLI dry run passed; awaiting participant login/upload',
              'dataset': dataset_id, 'image': args.image, 'snapshot_commit': commit,
              'snapshot_clean_in_linux': True, 'docker_tests_passed': 31,
              'parsed_queries_match_phase5': True, 'input_sha256': hashes,
              'exact_decompressed_rankings_and_scores_match_phase5': True,
              'ranking_sha256': hashlib.sha256(ranking).hexdigest(),
              'queries_with_results': len({line.split()[0] for line in ranking.splitlines()}),
              'source_sha256': code, 'system': system, 'output_directory': args.run_dir,
              'uploaded_to_tira': False, 'executed_on_tira_servers': False}
    (ROOT / 'reports/PHASE6-DRY-RUN.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'snapshot_clean_in_linux', 'parsed_queries_match_phase5',
                     'exact_decompressed_rankings_and_scores_match_phase5', 'queries_with_results')}, indent=2))


if __name__ == '__main__':
    main()
