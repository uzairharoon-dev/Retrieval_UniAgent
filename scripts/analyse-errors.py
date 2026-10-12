"""Read-only analysis of baseline rankings, judged documents, and duplicates."""
import argparse
import gzip
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from report import DATASETS, json_lines


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def snippets(text, query):
    terms = sorted(set(re.findall(r"\w{4,}", query.casefold())), key=len, reverse=True)
    folded = text.casefold()
    excerpts = []
    for term in terms:
        match = folded.find(term)
        if match >= 0:
            excerpt = " ".join(text[max(0, match - 160):match + 640].split())
            if excerpt not in excerpts:
                excerpts.append(excerpt)
        if len(excerpts) == 3:
            break
    return excerpts


def analyse(root, run_name, dataset_name, evidence):
    dataset_path = root / "vendor/uniagent-code/cikm26/datasets" / dataset_name
    queries = list(json_lines(dataset_path / "queries.jsonl"))
    labels = defaultdict(dict)
    with (dataset_path / "qrels.txt").open(encoding="utf-8") as stream:
        for line in stream:
            qid, _, docid, relevance = line.split()
            if int(relevance) > 0:
                labels[qid][docid] = int(relevance)
    source_rankings = defaultdict(list)
    with gzip.open(root / "runs" / run_name / dataset_name / "run.txt.gz", "rt") as stream:
        for line in stream:
            qid, _, docid, _, score, _ = line.split()
            source_rankings[qid].append((docid, float(score)))
    rankings = {qid: sorted(rows, key=lambda row: (row[1], row[0]), reverse=True)
                for qid, rows in source_rankings.items()}
    wanted = {docid for judgments in labels.values() for docid in judgments}
    wanted.update(docid for rows in rankings.values() for docid, _ in rows[:5])
    documents, selected, groups, normalized_groups = {}, {}, defaultdict(list), defaultdict(list)
    lengths = []
    for record in json_lines(dataset_path / "documents.jsonl.gz"):
        text = record.get("text") or ""
        docid = str(record["doc_id"])
        text_hash, normalized_hash = digest(text), digest(" ".join(text.split()))
        length = len(text.split())
        lengths.append(length)
        info = {"doc_id": docid, "title": record.get("title"), "url": record.get("url"),
                "words": length, "characters": len(text), "text_sha256": text_hash,
                "normalized_text_sha256": normalized_hash}
        documents[docid] = info
        if text.strip():
            groups[text_hash].append(docid)
            normalized_groups[normalized_hash].append(docid)
        if docid in wanted:
            selected[docid] = text
            evidence.write(json.dumps({"dataset": dataset_name, **info, "text": text},
                                      ensure_ascii=False) + "\n")
    # Verify that the field analysed is exactly what the baseline indexes.
    from tira.third_party_integrations import ir_datasets
    first = next(ir_datasets.load(str(dataset_path)).docs_iter())
    assert digest(first.default_text()) == documents[str(first.doc_id)]["text_sha256"]

    records = []
    for query in queries:
        qid = str(query["qid"])
        rows, source_rows = rankings[qid], source_rankings[qid]
        positions = {docid: rank for rank, (docid, _) in enumerate(rows, 1)}
        source_positions = {docid: rank for rank, (docid, _) in enumerate(source_rows, 1)}
        scores = dict(rows)
        seen_hashes, group_positions = set(), {}
        for rank, (docid, _) in enumerate(rows, 1):
            text_hash = documents[docid]["text_sha256"]
            if text_hash not in seen_hashes:
                seen_hashes.add(text_hash)
                group_positions[text_hash] = {"first_rank": rank, "unique_text_rank": len(seen_hashes)}

        def describe(docid):
            info, text = documents[docid], selected[docid]
            score = scores.get(docid)
            tied_positions = [rank for rank, (_, candidate_score) in enumerate(rows, 1)
                              if score is not None and candidate_score == score]
            return {
                **info, "rank": positions.get(docid), "source_rank": source_positions.get(docid),
                "score": score,
                "tie_rank_interval": [min(tied_positions), max(tied_positions)] if tied_positions else None,
                "exact_text_group_size": len(groups.get(info["text_sha256"], [])),
                "equivalent_text_retrieved": group_positions.get(info["text_sha256"]),
                "duplicate_url_examples": [documents[member]["url"]
                                           for member in groups.get(info["text_sha256"], [])[:5]],
                "opening": " ".join(text[:1600].split()),
                "query_term_excerpts": snippets(text, query["query"]),
                "query_surface_terms_missing": [term for term in re.findall(r"\w{4,}", query["query"].casefold())
                                                if term not in text.casefold()],
            }

        judged = [describe(docid) for docid in labels[qid]]
        best_rank = min((doc["rank"] for doc in judged if doc["rank"] is not None), default=None)
        bucket = ("not_retrieved" if best_rank is None else "rank_1_10" if best_rank <= 10
                  else "rank_11_100" if best_rank <= 100 else "rank_over_100")
        records.append({"qid": qid, "query": query["query"],
                        "description_for_review": query["original_query"].get("description"),
                        "bucket": bucket, "judged": judged,
                        "top5": [describe(docid) for docid, _ in rows[:5]],
                        "unique_texts_top10": len({documents[docid]["text_sha256"] for docid, _ in rows[:10]}),
                        "unique_texts_top100": len({documents[docid]["text_sha256"] for docid, _ in rows[:100]})})
    baseline_report = json.loads((root / "reports" / run_name / f"{dataset_name}-bm25.json").read_text())
    checked = 0
    for record in records:
        if len(record["judged"]) == 1:
            rank = record["judged"][0]["rank"]
            expected_ap = 1 / rank if rank else 0.0
            measured_ap = baseline_report["per_query"][record["qid"]]["AP"]
            if not math.isclose(expected_ap, measured_ap, abs_tol=1e-12):
                raise ValueError(f"Rank disagrees with baseline AP: {dataset_name}/{record['qid']}")
            checked += 1
    duplicate_sizes = [len(members) for members in groups.values() if len(members) > 1]
    summary = {
        "documents": len(documents), "queries": len(queries),
        "query_ranks_cross_checked_against_baseline_AP": checked,
        "rank_buckets": dict(Counter(record["bucket"] for record in records)),
        "empty_text_documents": sum(length == 0 for length in lengths),
        "median_document_words": statistics.median(lengths),
        "p95_document_words": sorted(lengths)[int((len(lengths) - 1) * .95)],
        "max_document_words": max(lengths),
        "exact_duplicate_groups": len(duplicate_sizes),
        "documents_in_exact_duplicate_groups": sum(duplicate_sizes),
        "redundant_exact_copies": sum(size - 1 for size in duplicate_sizes),
        "normalized_unique_nonempty_texts": len(normalized_groups),
        "queries_with_duplicate_text_in_top10": sum(record["unique_texts_top10"] < min(10, len(rankings[record["qid"]]))
                                                     for record in records),
        "judged_documents_in_duplicate_groups": sum(doc["exact_text_group_size"] > 1
                                                    for record in records for doc in record["judged"]),
    }
    return {"dataset": dataset_name, "summary": summary, "queries": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-name", required=True)
    args = parser.parse_args()
    root = Path("/workspace")
    output = root / "reports" / args.run_name / "phase3"
    output.mkdir(parents=True, exist_ok=True)
    with gzip.open(root / "runs" / args.run_name / "phase3-evidence.jsonl.gz", "wt", encoding="utf-8") as evidence:
        for dataset in DATASETS:
            result = analyse(root, args.run_name, dataset, evidence)
            (output / f"{dataset}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(json.dumps({"dataset": dataset, **result["summary"]}, ensure_ascii=False), flush=True)
    print(f"Evidence and analysis saved for {args.run_name}", flush=True)


if __name__ == "__main__":
    main()
