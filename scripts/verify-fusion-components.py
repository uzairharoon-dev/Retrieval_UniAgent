"""Verify live fusion components reproduce the independently validated runs."""
import argparse
import gzip
import json
import math
import sys
from pathlib import Path

import pyterrier as pt

from report import DATASETS


def pairs(path):
    result = {}
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            qid, _, docid, _, score, _ = line.split()
            key = (qid, docid)
            if key in result:
                raise ValueError(f"Duplicate pair in {path}")
            result[key] = float(score)
    return result


def same_scores(first, second):
    return first.keys() == second.keys() and all(
        math.isclose(first[key], second[key], rel_tol=1e-12, abs_tol=1e-12) for key in first
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", required=True)
    args = parser.parse_args()
    root = Path("/workspace")
    sys.path.insert(0, str(root / "retrieval"))
    from fusion import fuse_runs
    results = []
    for dataset in DATASETS:
        output = root / "runs" / args.run_name / dataset
        short_path = output / "components/short/run.txt.gz"
        short_matches = same_scores(pairs(short_path), pairs(root / "runs/bm25-20261012-231608" / dataset / "run.txt.gz"))
        long_path = output / "components/long/run.txt.gz"
        if not long_path.exists():
            long_path = short_path
        long_matches = same_scores(pairs(long_path), pairs(root / "runs/phase4-long-tokens-64" / dataset / "run.txt.gz"))
        expected = fuse_runs(pt.io.read_results(short_path), pt.io.read_results(long_path))
        expected_pairs = {(str(row.qid), str(row.docno)): float(row.score) for row in expected.itertuples()}
        fusion_matches = same_scores(expected_pairs, pairs(output / "run.txt.gz"))
        if not all((short_matches, long_matches, fusion_matches)):
            raise ValueError(f"Component or fusion reproduction failed: {dataset}")
        results.append({"dataset": dataset, "short_matches_baseline": short_matches,
                        "long_matches_long_token_experiment": long_matches,
                        "fusion_matches_saved_components": fusion_matches})
    path = root / "reports" / args.run_name / "component-verification.json"
    path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
