"""Check source-ID preservation and key control comparisons on the full corpora."""
import gzip
import json
import math
from pathlib import Path

from report import DATASETS, json_lines

ROOT = Path("/workspace")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def scores(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return {(fields[0], fields[2]): float(fields[4]) for fields in (line.split() for line in stream)}


def equal(first, second):
    return first.keys() == second.keys() and all(math.isclose(first[key], second[key], rel_tol=1e-12, abs_tol=1e-12)
                                               for key in first)


def main():
    checks = []
    for dataset in DATASETS:
        expected_ids = {str(document["doc_id"]) for document in json_lines(
            ROOT / "vendor/uniagent-code/cikm26/datasets" / dataset / "documents.jsonl.gz")}
        for mode in ("compound", "deduplicated", "passages"):
            directory = ROOT / "runs" / f"phase4-{mode}" / dataset
            mapping = load(directory / "representation-map.json")
            actual_ids = {docid for parents in mapping.values() for docid in parents}
            config = load(directory / "system.json")
            if actual_ids != expected_ids or config["source_documents"] != len(expected_ids):
                raise ValueError(f"Original IDs were lost or changed: {mode}/{dataset}")
            if config["indexed_representations"] != len(mapping):
                raise ValueError(f"Index and representation counts disagree: {mode}/{dataset}")
            checks.append({"dataset": dataset, "mode": mode, "all_original_ids_preserved": True,
                           "source_documents": len(expected_ids), "indexed_representations": len(mapping)})
    dataset = "retrieval-hessian-law-de-spot-check"
    law_control = equal(scores(ROOT / "runs/phase4-compound" / dataset / "run.txt.gz"),
                        scores(ROOT / "runs/phase4-deduplicated" / dataset / "run.txt.gz"))
    if not law_control:
        raise ValueError("Deduplication changed the corpus with no exact duplicates")
    dataset = "retrieval-en-spot-check"
    english_control = equal(scores(ROOT / "runs/bm25-20261012-231608" / dataset / "run.txt.gz"),
                            scores(ROOT / "runs/phase4-compound" / dataset / "run.txt.gz"))
    result = {"mapping_checks": checks, "law_deduplication_noop_verified": law_control,
              "english_compound_control_identical_scores": english_control}
    (ROOT / "reports/PHASE4-VERIFICATION.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
