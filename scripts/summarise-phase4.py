"""Summarise the fixed Phase 4 experiment set and recommend a Phase 5 candidate."""
import json
from pathlib import Path

from report import DATASETS, json_lines

ROOT = Path("/workspace")
RUNS = ["bm25-20261012-231608", "phase4-long-tokens-64", "phase4-rrf60-isolated",
        "phase4-compound", "phase4-deduplicated", "phase4-passages"]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rank_from_single_positive(ap):
    return round(1 / ap) if ap > 0 else None


def main():
    reference_hashes = {row["dataset"]: row["sha256"] for row in load(ROOT / "reports" / RUNS[0] / "data-audit.json")}
    summaries = []
    ranks = {}
    baseline = {name: load(ROOT / "reports" / RUNS[0] / f"{name}-bm25.json") for name in DATASETS}
    for run in RUNS:
        hashes = {row["dataset"]: row["sha256"] for row in load(ROOT / "reports" / run / "data-audit.json")}
        if hashes != reference_hashes:
            raise ValueError(f"Dataset hashes differ: {run}")
        corpora, regressions, improvements = [], [], []
        for name in DATASETS:
            report = load(ROOT / "reports" / run / f"{name}-bm25.json")
            queries = {str(query["qid"]): query["query"] for query in json_lines(
                ROOT / "vendor/uniagent-code/cikm26/datasets" / name / "queries.jsonl")}
            if set(report["per_query"]) != set(queries):
                raise ValueError(f"Incomplete query evaluation: {run}/{name}")
            corpora.append({"dataset": name, "metrics": report["metrics"], "queries": len(queries),
                            "official_evaluation": report["official_evaluation"]})
            for qid, metrics in report["per_query"].items():
                key = f"{name}/{qid}"
                ranks.setdefault(key, {"query": queries[qid], "ranks": {}})["ranks"][run] = rank_from_single_positive(metrics["AP"])
                difference = metrics["AP"] - baseline[name]["per_query"][qid]["AP"]
                case = {"dataset": name, "qid": qid, "query": queries[qid],
                        "baseline_rank": rank_from_single_positive(baseline[name]["per_query"][qid]["AP"]),
                        "rank": rank_from_single_positive(metrics["AP"])}
                if difference > 1e-12:
                    improvements.append(case)
                elif difference < -1e-12:
                    regressions.append(case)
        summaries.append({"run": run, "corpora": corpora,
                          "macro_nDCG@10": sum(row["metrics"]["nDCG@10"] for row in corpora) / 3,
                          "query_weighted_nDCG@10": sum(row["metrics"]["nDCG@10"] * row["queries"] for row in corpora) / 65,
                          "macro_Recall@100": sum(row["metrics"]["R@100"] for row in corpora) / 3,
                          "improved_queries": improvements, "regressed_queries": regressions})
    best = max(summaries, key=lambda row: (row["macro_nDCG@10"], row["macro_Recall@100"]))
    balanced = [row for row in summaries if all(
        corpus["metrics"]["nDCG@10"] + 1e-12 >= original["metrics"]["nDCG@10"]
        and corpus["metrics"]["R@100"] + 1e-12 >= original["metrics"]["R@100"]
        for corpus, original in zip(row["corpora"], summaries[0]["corpora"]))]
    balanced_best = max(balanced, key=lambda row: row["macro_nDCG@10"])
    result = {"phase": 4, "status": "development experiments complete",
              "recommendation_rule": "equal-weight corpus mean nDCG@10, then mean Recall@100; final selection is Phase 5",
              "recommended_for_phase5": best["run"], "runs": summaries, "query_ranks": ranks,
              "balanced_alternative_for_phase5": balanced_best["run"] if balanced_best["run"] != best["run"] else None,
              "limitation": "Development selection on synthetic, single-positive spot-check judgments; no held-out generalisation claim."}
    (ROOT / "reports/PHASE4-SUMMARY.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for row in summaries:
        print(json.dumps({"run": row["run"], "macro_nDCG@10": row["macro_nDCG@10"],
                          "macro_Recall@100": row["macro_Recall@100"], "improved": len(row["improved_queries"]),
                          "regressed": len(row["regressed_queries"])}))
    print(f"Recommended for Phase 5: {best['run']}")
    names = ["Official BM25", "Long tokens", "RRF fusion", "Compounds", "Shared-text index", "Passages"]
    lines = ["# Phase 4 complete", "",
             "The fixed development experiment set is complete. The recommended candidate for Phase 5 is "
             f"**{best['run']}**. This is a development recommendation, not the final submission selection.", "",
             "## Results", "", "nDCG@10, using the same ir_measures evaluator and descending document-ID tie convention:", "",
             "| System | German university | English university | Hessian law | Mean across corpora |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for label, row in zip(names, summaries):
        values = [corpus["metrics"]["nDCG@10"] for corpus in row["corpora"]]
        lines.append(f"| {label} | " + " | ".join(f"{value:.6f}" for value in values) + f" | {row['macro_nDCG@10']:.6f} |")
    lines += ["", "The recommendation uses the equal-weight mean across the three corpora, fixed in the "
              "[experiment plan](phase4-experiment-plan.json). The JSON summary also reports query-weighted means, "
              "Recall@100, and every query's rank. No parameter sweep or query-specific rules were used.", "",
              "## Recommended candidate versus baseline", "",
              "| Corpus | Baseline Recall@100 | Candidate Recall@100 |",
              "| --- | ---: | ---: |"]
    for before, after in zip(summaries[0]["corpora"], best["corpora"]):
        lines.append(f"| {after['dataset']} | {before['metrics']['R@100']:.6f} | {after['metrics']['R@100']:.6f} |")
    lines += ["", f"Judged ranks improved on {len(best['improved_queries'])} queries and regressed on "
              f"{len(best['regressed_queries'])}; the remaining {65-len(best['improved_queries'])-len(best['regressed_queries'])} are unchanged.", "",
              "## Targeted cases", "", "| Case | Baseline | Long | Fusion | Compound | Shared index | Passages |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for dataset, qid, label in [("retrieval-de-spot-check", "37", "German library query"),
                                ("retrieval-en-spot-check", "16", "English consumables"),
                                *[("retrieval-hessian-law-de-spot-check", str(qid), f"Law {qid}") for qid in (2, 7, 8, 9, 11, 15)]]:
        row = ranks[f"{dataset}/{qid}"]["ranks"]
        lines.append(f"| {label} | " + " | ".join(str(row[name]) if row[name] else "Absent" for name in RUNS) + " |")
    lines += ["", "## What was tested", "",
              "- **Compounds:** a vocabulary learned only from document text, minimum document frequency 5; "
              "original words retained and at most two corpus-supported parts added. German token limit 64; English unchanged.",
              "- **Shared-text indexing:** exact source-text duplicates indexed once, with scores expanded back to every original ID. "
              "This changes collection statistics; it does not remove duplicate IDs from final results.",
              "- **Passages:** compound representation plus retained full documents and 300-word windows at stride 200, "
              "with up to 24 heading words. Retrieve 5,000 representations, aggregate by maximum score, return 1,000 original documents.", "",
              "## Validation and cost", "",
              "All 31 Docker tests passed. All nine new corpus/variant runs completed offline and passed run-format/ID validation. "
              "Input hashes match the original baseline. [Full-corpus verification](PHASE4-VERIFICATION.json) checks source-ID "
              "preservation in every representation, the unchanged English compound control, and the legal deduplication control.", "",
              "| Variant / corpus | Source documents | Indexed representations | End-to-end seconds |",
              "| --- | ---: | ---: | ---: |"]
    for run in RUNS[3:]:
        for dataset in DATASETS:
            config = load(ROOT / "runs" / run / dataset / "system.json")
            lines.append(f"| {run} / {dataset} | {config['source_documents']} | {config['indexed_representations']} | "
                         f"{config['end_to_end_seconds']:.3f} |")
    lines += ["", "These single local times include vocabulary preparation, indexing, retrieval, and run writing, but exclude "
              "adapter loading, Docker startup, and evaluation. Resource tracker files and the comparison JSON retain index/retrieval "
              "process-memory readings. These do not establish full private-test runtime or a process-tree memory peak.", "",
              "## Limits and next phase", "",
              "All scores use synthetic spot-check queries with one judged document per query. Unjudged results can be relevant; "
              "selection on these data does not prove held-out generalisation. Per-query regressions and the HTGV case remain visible "
              "rather than being hidden by the mean score. No new external model, parameter search, or submission was performed.", "",
              "Phase 5 should validate the recommended candidate: deterministic fresh runs, retrieval without qrels, resource limits, "
              "input/output compatibility, and review of its regressions. Phase 6 will package and test the TIRA submission. "
              "The launcher's original default remains unchanged pending that validation.", "",
              "## Reproduce and evidence", "", "Build the shared retrieval image, then invoke one variant with a new run name:", "",
              "```powershell", ".\\scripts\\run-baseline.ps1 -Variant compound -RunName compound-repeat", "```", "",
              "Supported new variants are `compound`, `deduplicated`, and `passages`. "
              "`scripts/run-remaining-phase4.ps1` records the original fixed batch (its run names must not already exist). "
              "Evaluations, hashes and pairwise comparisons are under `reports/phase4-{compound,deduplicated,passages}/`. "
              "Raw rankings, vocabulary files, ID maps, and resource metadata are under the matching ignored `runs/` directories.", "",
              "[Complete comparison and query ranks](PHASE4-SUMMARY.json)."]
    if balanced_best["run"] != best["run"]:
        lines += ["", "## Balanced alternative for Phase 5", "",
                  f"Also retain **{balanced_best['run']}**: it has no corpus-level regression in nDCG@10 or Recall@100 "
                  "versus the original baseline. Its highest mean score among such candidates makes it a useful alternative "
                  "when reviewing the primary candidate's tradeoffs and runtime. This is not a claim of no per-query regressions."]
    (ROOT / "reports/PHASE4-COMPLETE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
