"""Compare saved retrieval experiments using fixed evaluators and dataset hashes."""
import argparse
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

import yaml

from report import DATASETS, json_lines


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_run(path):
    rows = defaultdict(list)
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            qid, _, docid, _, score, _ = line.split()
            rows[qid].append((docid, float(score)))
    return rows


def resources(path):
    result = {}
    for stage in ("index", "retrieval"):
        metadata_path = path / f"{stage}-ir-metadata.yml"
        if not metadata_path.exists():
            continue
        metadata = yaml.safe_load(metadata_path.read_text())
        tracked = metadata.get("resources", {})
        result[stage] = {"wallclock": tracked.get("runtime", {}).get("wallclock"),
                         "peak_ram_raw": tracked.get("ram", {}).get("used process", {}).get("max")}
    for component in ("short", "long"):
        component_path = path / "components" / component
        if component_path.exists():
            result[component] = resources(component_path)
    if (path / "system.json").exists():
        system = load_json(path / "system.json")
        if "end_to_end_seconds" in system:
            result["end_to_end_seconds"] = system["end_to_end_seconds"]
    if (path / "fusion-ir-metadata.yml").exists():
        tracked = yaml.safe_load((path / "fusion-ir-metadata.yml").read_text())["resources"]
        result["fusion"] = {"wallclock": tracked["runtime"]["wallclock"],
                            "peak_ram_raw": tracked["ram"]["used process"]["max"]}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="bm25-20261012-231608")
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output-name", default="comparison.json")
    args = parser.parse_args()
    if Path(args.output_name).name != args.output_name:
        parser.error("--output-name must be a filename")
    root = Path("/workspace")
    old_audit = load_json(root / "reports" / args.baseline / "data-audit.json")
    new_audit = load_json(root / "reports" / args.candidate / "data-audit.json")
    if {row["dataset"]: row["sha256"] for row in old_audit} != {row["dataset"]: row["sha256"] for row in new_audit}:
        raise ValueError("Dataset hashes differ; these runs cannot be compared directly")
    output = {"baseline": args.baseline, "candidate": args.candidate, "data_hashes_match": True,
              "tie_convention": "ir_measures: descending document ID for equal scores",
              "datasets": []}
    for dataset in DATASETS:
        old = load_json(root / "reports" / args.baseline / f"{dataset}-bm25.json")
        new = load_json(root / "reports" / args.candidate / f"{dataset}-bm25.json")
        if set(old["per_query"]) != set(new["per_query"]):
            raise ValueError("Evaluation query sets differ")
        queries = {str(q["qid"]): q["query"] for q in json_lines(root / "vendor/uniagent-code/cikm26/datasets" / dataset / "queries.jsonl")}
        judged = defaultdict(set)
        with (root / "vendor/uniagent-code/cikm26/datasets" / dataset / "qrels.txt").open() as stream:
            for line in stream:
                qid, _, docid, grade = line.split()
                if int(grade) > 0:
                    judged[qid].add(docid)
        old_rows = read_run(root / "runs" / args.baseline / dataset / "run.txt.gz")
        new_rows = read_run(root / "runs" / args.candidate / dataset / "run.txt.gz")

        def rank(rows, qid):
            ordered = sorted(rows[qid], key=lambda row: (row[1], row[0]), reverse=True)
            return min((position for position, (docid, _) in enumerate(ordered, 1)
                        if docid in judged[qid]), default=None)

        comparisons = []
        for qid, query in queries.items():
            old_ap, new_ap = old["per_query"][qid]["AP"], new["per_query"][qid]["AP"]
            status = "unchanged" if math.isclose(old_ap, new_ap, abs_tol=1e-12) else "improved" if new_ap > old_ap else "regressed"
            comparisons.append({"qid": qid, "query": query, "status": status,
                                "baseline_rank": rank(old_rows, qid), "candidate_rank": rank(new_rows, qid),
                                "baseline_metrics": old["per_query"][qid], "candidate_metrics": new["per_query"][qid]})
        result = {"dataset": dataset, "baseline_metrics": old["metrics"], "candidate_metrics": new["metrics"],
                  "metric_deltas": {key: new["metrics"][key] - old["metrics"][key] for key in old["metrics"]},
                  "baseline_official_evaluation": old["official_evaluation"],
                  "candidate_official_evaluation": new["official_evaluation"],
                  "improved_queries": sum(row["status"] == "improved" for row in comparisons),
                  "regressed_queries": sum(row["status"] == "regressed" for row in comparisons),
                  "unchanged_queries": sum(row["status"] == "unchanged" for row in comparisons),
                  "same_source_rankings_and_scores": dict(old_rows) == dict(new_rows),
                  "same_canonical_rankings": {
                      qid: [docid for docid, _ in sorted(rows, key=lambda row: (row[1], row[0]), reverse=True)]
                      for qid, rows in old_rows.items()
                  } == {
                      qid: [docid for docid, _ in sorted(rows, key=lambda row: (row[1], row[0]), reverse=True)]
                      for qid, rows in new_rows.items()
                  },
                  "baseline_resources": resources(root / "runs" / args.baseline / dataset),
                  "candidate_resources": resources(root / "runs" / args.candidate / dataset),
                  "per_query": comparisons}
        # Keep the raw resource files separately; their timing includes local machine variation.
        output["datasets"].append(result)
        print(json.dumps({key: value for key, value in result.items() if key != "per_query"}, indent=2), flush=True)
    (root / "reports" / args.candidate / args.output_name).write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
