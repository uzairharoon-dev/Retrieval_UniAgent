"""Verify fresh, label-isolated repeats and record the Phase 5 system selection."""
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from report import DATASETS, json_lines

ROOT = Path('/workspace')


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = ROOT / 'reports/phase5'
    image = load(evidence / 'image.json')[0]['Id']
    code_hashes = {}
    for path in (ROOT / 'retrieval').iterdir():
        if path.suffix == '.py' or path.name.startswith('german-stopwords.'):
            require(digest(path) == digest(Path('/app') / path.name), f'Image code differs: {path.name}')
            code_hashes[path.name] = digest(path)
    reference_audit = {r['dataset']: r for r in load(ROOT / 'reports/bm25-20261012-231608/data-audit.json')}
    for row in load(evidence / 'inputs.json'):
        require(row['sha256'] == reference_audit[row['dataset']]['sha256'][row['file']], 'Input hash mismatch')
        require(digest(ROOT / 'runs/phase5-inputs' / row['dataset'] / row['file']) == row['sha256'], 'Copied input changed')
    executions = {(row['run'], row['dataset']): row for row in load(evidence / 'executions.json')}
    checks = []
    for mode in ('passages', 'deduplicated'):
        run_name = f'phase5-{mode}'
        audits = {r['dataset']: r['sha256'] for r in load(ROOT / 'reports' / run_name / 'data-audit.json')}
        require(audits == {name: row['sha256'] for name, row in reference_audit.items()}, 'Evaluation data changed')
        for name in DATASETS:
            run = ROOT / 'runs' / run_name / name
            old = ROOT / 'runs' / f'phase4-{mode}' / name
            with gzip.open(run / 'run.txt.gz', 'rt') as stream:
                text = stream.read()
            with gzip.open(old / 'run.txt.gz', 'rt') as stream:
                require(text == stream.read(), f'Fresh rankings/scores differ: {mode}/{name}')
            rows = [line.split() for line in text.splitlines()]
            depths = Counter(row[0] for row in rows)
            expected_queries = {str(q['qid']) for q in json_lines(ROOT / 'runs/phase5-inputs' / name / 'queries.jsonl')}
            require(set(depths) == expected_queries, f'Missing query results: {mode}/{name}')
            source_ids = {str(doc['doc_id']) for doc in json_lines(ROOT / 'runs/phase5-inputs' / name / 'documents.jsonl.gz')}
            mapping = load(run / 'representation-map.json')
            require({parent for parents in mapping.values() for parent in parents} == source_ids, 'Source IDs lost')
            require(all(row[2] in source_ids for row in rows), 'Unknown output ID')
            config = load(run / 'system.json')
            require(config['indexed_representations'] == len(mapping), 'Index count differs')
            report = load(ROOT / 'reports' / run_name / f'{name}-bm25.json')
            previous = load(ROOT / 'reports' / f'phase4-{mode}' / f'{name}-bm25.json')
            require(report['per_query'] == previous['per_query'], 'Repeat metrics differ')
            inspect = load(ROOT / 'reports' / run_name / f'{name}-container.json')[0]
            require(inspect['Image'] == image, 'Different container image')
            host = inspect['HostConfig']
            require(host['NetworkMode'] == 'none' and host['NanoCpus'] == 4_000_000_000, 'Execution limits differ')
            require(host['Memory'] == host['MemorySwap'] == 3 * 1024**3, 'Memory cap or no-swap setting differs')
            mounts = {mount['Destination']: mount for mount in inspect['Mounts']}
            require(set(mounts) == {'/input', '/output'} and not mounts['/input']['RW'], 'Unexpected retrieval mounts')
            expected_source = (ROOT / 'runs/phase5-inputs' / name).name
            require(mounts['/input']['Source'].replace('\\', '/').endswith('/phase5-inputs/' + expected_source), 'Wrong input mount')
            require(mounts['/output']['Source'].replace('\\', '/').endswith('/' + run_name + '/' + name), 'Wrong output mount')
            require({p.name for p in (ROOT / 'runs/phase5-inputs' / name).iterdir()} == {'documents.jsonl.gz', 'queries.jsonl'}, 'Labels in input')
            execution = executions[(run_name, name)]
            require(execution['state']['ExitCode'] == 0 and not execution['state']['OOMKilled'], 'Failed or OOM run')
            require(report['queries_without_results'] == [], 'Queries without results')
            checks.append({'run': run_name, 'dataset': name, 'queries': len(depths),
                           'exact_decompressed_run_reproduced': True, 'all_source_ids_preserved': True,
                           'labels_excluded_from_retrieval': True, 'network': 'none',
                           'memory_cap_bytes': host['Memory'], 'swap_enabled': False,
                           'wall_seconds_including_container_startup': execution['wall_seconds'],
                           'depth_min': min(depths.values()), 'depth_max': max(depths.values()),
                           'metrics': report['metrics'], 'official_nDCG@10': report['official_evaluation']['nDCG@10']})
    phase4 = load(ROOT / 'reports/PHASE4-SUMMARY.json')
    candidates = phase4['runs']
    selected = max(candidates, key=lambda row: (row['macro_nDCG@10'], row['macro_Recall@100']))
    require(selected['run'] == 'phase4-passages', 'Declared selection changed')
    scores = [{'run': row['run'], 'canonical_mean_nDCG@10': row['macro_nDCG@10'],
               'local_TIRA_mean_nDCG@10': sum(c['official_evaluation']['nDCG@10'] for c in row['corpora']) / len(DATASETS)}
              for row in candidates]
    selection = {'phase': 5, 'status': 'complete', 'selected_mode': 'passages',
                 'alternative_mode': 'deduplicated', 'image_id': image,
                 'selection_rule': phase4['recommendation_rule'],
                 'entrypoint': ['python3', '/app/representation_system.py'],
                 'arguments': ['--dataset', '<input-directory>', '--output', '<output-directory>', '--mode', 'passages'],
                 'held_out_evaluation': False, 'submitted': False,
                 'tests': '31 tests passed in this unchanged image build; image/source hashes checked',
                 'source_sha256': code_hashes, 'validation': checks, 'evaluator_comparison': scores,
                 'limitations': [
                     'Synthetic development qrels; no held-out generalisation claim.',
                     'Local TIRA file-order ties and canonical ir_measures ties rank systems differently.',
                     'Passages lowers German nDCG@10 and Recall@100 versus original baseline.',
                     'Container cap proves these six runs fit 3 GiB with no swap, not private-test scalability.',
                     'Default image entrypoint and local parent build chain still require Phase 6 packaging.',
                     'Mixed-language queries are unsupported, inherited from the official baseline.']}
    (evidence / 'selection.json').write_text(json.dumps(selection, indent=2) + '\n')
    baseline = scores[0]['canonical_mean_nDCG@10']
    primary = next(r for r in scores if r['run'] == 'phase4-passages')
    lines = ['# Phase 5: validation and final selection', '',
             '**Complete. Selected: passage BM25 with corpus-derived German compounds.** Retain shared-text indexing (`deduplicated`) as the cheaper alternative. Nothing has been submitted.', '',
             'Selection follows the rule fixed before Phase 4: equal-weight mean canonical ir_measures nDCG@10 across the three corpora, then mean Recall@100. Parameters are unchanged; no further search was performed.', '',
             '## Quality and evaluator sensitivity', '',
             '| System | Canonical mean nDCG@10 | Local TIRA mean nDCG@10 |',
             '| --- | ---: | ---: |']
    for row in scores:
        lines.append(f"| {row['run']} | {row['canonical_mean_nDCG@10']:.6f} | {row['local_TIRA_mean_nDCG@10']:.6f} |")
    lines += ['', f"The selected canonical score is {primary['canonical_mean_nDCG@10']:.6f}, versus {baseline:.6f} originally ({(primary['canonical_mean_nDCG@10']/baseline-1)*100:.2f}% relative). This percentage applies only to canonical evaluation.", '',
              '**The long-token variant has the highest local TIRA mean.** The local evaluator preserves file order for tied scores; ir_measures orders ties by document ID. Duplicate texts and sparse labels make this consequential. Passage selection is based on the declared common tie convention; it is not a claim to be the best under every evaluator. See [the baseline tie investigation](BASELINE.md).', '',
              'Passages regresses German nDCG@10 from 0.480303 to 0.465432 and Recall@100 from 1.00 to 0.96; the German library positive is rank 101. It improves English nDCG@10 from 0.762747 to 0.874282 and law from 0.399989 to 0.660848. Against the original, 27 judged-document ranks/AP improve, 7 regress, and 31 are unchanged; these are not counts of nDCG gains.', '',
              'The deduplicated alternative scores 0.623729 canonical mean, improves corpus-level nDCG and does not reduce corpus-level Recall@100 versus the original. It still has per-query regressions. These are development results from 65 synthetic, single-positive judgments, not a held-out quality estimate.', '',
              '## Fresh execution proof', '',
              'Both candidates were repeated on all three corpora in fresh containers. Retrieval received only a read-only directory containing documents and queries, plus a fresh output directory. Labels, evaluator scripts, and the workspace were excluded. Evaluation read qrels in separate containers after retrieval.', '',
              'All six decompressed TREC outputs exactly reproduce Phase 4, including row order and score strings. Input hashes, image/source hashes, all original source IDs, query coverage, output format and metric agreement passed. The unchanged image previously passed all 31 Docker tests.', '',
              'The entire retrieval container was capped at 4 CPUs and 3 GiB, with no swap and no network. All six exited successfully without OOM. This covers vocabulary preparation and serialization that the stage trackers omit; it establishes a cap, not an exact peak measurement.', '',
              '| Mode / corpus | Queries | Returned documents/query, min-max | Full container seconds |',
              '| --- | ---: | ---: | ---: |']
    for row in checks:
        lines.append(f"| {row['run']} / {row['dataset']} | {row['queries']} | {row['depth_min']}-{row['depth_max']} | {row['wall_seconds_including_container_startup']:.1f} |")
    lines += ['', 'Passages retrieves up to 5,000 representations and returns **up to** 1,000 original documents; repeated parents and matching vocabulary can yield fewer. Runtime and memory on private inputs remain unverified.', '',
              '## Handoff to Phase 6', '',
              'Use the selected system explicitly:', '', '```powershell',
              '.\\scripts\\run-baseline.ps1 -Variant passages -RunName selected-check -SkipBuild', '```', '',
              'The launcher default remains the original baseline for reference. Phase 6 must provide the final reproducible image build and selected entrypoint, verify the TIRA input contract (including language handling), and run the submission dry run. Registration/authentication and submission have not been performed.', '',
              'Evidence: [selection and checks](phase5/selection.json), [input hashes](phase5/inputs.json), [container exit states and timings](phase5/executions.json). Per-corpus metrics and saved retrieval-container inspections are in `phase5-passages/` and `phase5-deduplicated/`. Raw runs remain in ignored `runs/`.', '',
              'Reproduce fresh execution with `scripts/validate-phase5.ps1` in a clean workspace (fixed run names reject overwriting), then run `scripts/summarise-phase5.py` inside the tested representations image with the workspace mounted at `/workspace`.']
    (ROOT / 'reports/PHASE5.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'status': 'complete', 'selected_mode': 'passages', 'fresh_runs_verified': len(checks)}, indent=2))


if __name__ == '__main__':
    main()
