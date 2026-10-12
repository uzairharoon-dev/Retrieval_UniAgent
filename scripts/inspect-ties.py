"""Compare source order and TREC document-ID ordering for equal-score ties."""
import argparse
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run-name", required=True)
parser.add_argument("--dataset", required=True)
args = parser.parse_args()
root = Path("/workspace")
rankings, judgments = defaultdict(list), defaultdict(dict)
with gzip.open(root / "runs" / args.run_name / args.dataset / "run.txt.gz", "rt") as stream:
    for line in stream:
        qid, _, docid, _, score, _ = line.split()
        rankings[qid].append((docid, float(score)))
with (root / "vendor/uniagent-code/cikm26/datasets" / args.dataset / "qrels.txt").open() as stream:
    for line in stream:
        qid, _, docid, relevance = line.split()
        judgments[qid][docid] = int(relevance)


def ndcg(ranking, labels):
    dcg = sum(labels.get(docid, 0) / math.log2(rank + 2)
              for rank, (docid, _) in enumerate(ranking[:10]))
    ideal = sum(relevance / math.log2(rank + 2)
                for rank, relevance in enumerate(sorted(labels.values(), reverse=True)[:10]))
    return dcg / ideal if ideal else 0.0


source_order, document_id_order, affected = [], [], {}
for qid, labels in judgments.items():
    ranking = rankings[qid]
    reordered = sorted(ranking, key=lambda row: (row[1], row[0]), reverse=True)
    source_score = ndcg(ranking, labels)
    reordered_score = ndcg(reordered, labels)
    source_order.append(source_score)
    document_id_order.append(reordered_score)
    if not math.isclose(source_score, reordered_score):
        affected[qid] = {"source_order": source_score, "document_id_order": reordered_score}
report = {
    "dataset": args.dataset,
    "source_order_nDCG@10": sum(source_order) / len(source_order),
    "document_id_tiebreak_nDCG@10": sum(document_id_order) / len(document_id_order),
    "affected_queries": affected,
}
print(json.dumps(report, indent=2))
(root / "reports" / args.run_name / f"{args.dataset}-ties.json").write_text(
    json.dumps(report, indent=2) + "\n", encoding="utf-8"
)
