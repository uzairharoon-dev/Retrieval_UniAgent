"""Audit provided data and evaluate runs inside the official Docker image."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

DATASETS = (
    "retrieval-de-spot-check",
    "retrieval-en-spot-check",
    "retrieval-hessian-law-de-spot-check",
)


def json_lines(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_dataset(name):
    directory = Path("/datasets") / name
    queries = list(json_lines(directory / "queries.jsonl"))
    query_ids = {str(query["qid"]) for query in queries}
    if len(query_ids) != len(queries):
        raise ValueError(f"Duplicate query IDs: {name}")
    document_ids = set()
    first_document = None
    for document in json_lines(directory / "documents.jsonl.gz"):
        if first_document is None:
            first_document = document
        identifier = str(document["doc_id"])
        if identifier in document_ids:
            raise ValueError(f"Duplicate document ID: {identifier}")
        document_ids.add(identifier)
    judged_queries, relevant_pairs, judgment_count = set(), set(), 0
    with (directory / "qrels.txt").open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            qid, _, docid, relevance = line.split()
            if qid not in query_ids or docid not in document_ids:
                raise ValueError(f"Unknown ID in qrels: {qid} / {docid}")
            judged_queries.add(qid)
            judgment_count += 1
            if int(relevance) > 0:
                relevant_pairs.add((qid, docid))
    summary = {
        "dataset": name,
        "documents": len(document_ids),
        "queries": len(queries),
        "judged_queries": len(judged_queries),
        "judgments": judgment_count,
        "relevant_query_document_pairs": len(relevant_pairs),
        "languages": sorted({q["original_query"]["language"] for q in queries}),
        "document_fields": sorted(first_document or {}),
        "sample_query": queries[0] if queries else None,
        "sha256": {
            filename: sha256(directory / filename)
            for filename in ("documents.jsonl.gz", "queries.jsonl", "qrels.txt")
        },
    }
    return summary, query_ids, document_ids


def evaluate(name):
    import ir_measures
    from tira.evaluators import evaluate as official_evaluate

    directory = Path("/datasets") / name
    predictions = Path("/outputs") / name
    _, query_ids, document_ids = inspect_dataset(name)
    seen_pairs, seen_ranks, last_scores, retrieved_queries = set(), set(), {}, set()
    with gzip.open(predictions / "run.txt.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            qid, placeholder, docid, rank, score, _ = line.split()
            rank, score = int(rank), float(score)
            if qid not in query_ids or docid not in document_ids:
                raise ValueError(f"Unknown ID in run: {qid} / {docid}")
            if placeholder != "Q0" or rank < 0 or not math.isfinite(score):
                raise ValueError(f"Invalid run row: {line}")
            if (qid, docid) in seen_pairs or (qid, rank) in seen_ranks:
                raise ValueError(f"Duplicate document or rank: {qid} / {docid}")
            if score > last_scores.get(qid, float("inf")):
                raise ValueError(f"Scores are not descending for {qid}")
            seen_pairs.add((qid, docid))
            seen_ranks.add((qid, rank))
            last_scores[qid] = score
            retrieved_queries.add(qid)
    qrels = list(ir_measures.read_trec_qrels(str(directory / "qrels.txt")))
    run = list(ir_measures.read_trec_run(str(predictions / "run.txt.gz")))
    measures = [ir_measures.nDCG @ 10, ir_measures.R @ 100, ir_measures.MAP]
    metrics = ir_measures.calc_aggregate(measures, qrels, run)
    per_query = {}
    for result in ir_measures.iter_calc(measures, qrels, run):
        per_query.setdefault(result.query_id, {})[str(result.measure)] = result.value
    report = {
        "dataset": name,
        "method": (json.loads((predictions / "system.json").read_text())["method"]
                   if (predictions / "system.json").exists() else "official PyTerrier BM25 baseline"),
        "official_evaluation": official_evaluate(predictions, directory, {
            "measures": ["nDCG@10"], "run_format": ["run.txt"], "truth_format": "qrels.txt",
        }),
        "metrics": {str(measure): value for measure, value in metrics.items()},
        "queries_with_results": len(retrieved_queries),
        "queries_without_results": sorted(query_ids - retrieved_queries),
        "run_rows": len(seen_pairs),
        "per_query": per_query,
        "limitation": "Spot-check queries and qrels are synthetic; scores do not establish final-task quality.",
    }
    path = Path("/reports") / f"{name}-bm25.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["audit", "evaluate"])
    parser.add_argument("--dataset", choices=DATASETS)
    arguments = parser.parse_args()
    if arguments.action == "audit":
        summaries = [inspect_dataset(name)[0] for name in DATASETS]
        Path("/reports/data-audit.json").write_text(
            json.dumps(summaries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        for summary in summaries:
            print(f"{summary['dataset']}: {summary['documents']} documents, "
                  f"{summary['queries']} queries, {summary['judgments']} judgments")
    else:
        if arguments.dataset is None:
            parser.error("--dataset is required for evaluate")
        evaluate(arguments.dataset)


if __name__ == "__main__":
    main()
