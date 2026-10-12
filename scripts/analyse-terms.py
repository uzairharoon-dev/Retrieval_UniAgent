"""Inspect query terms using the baseline's language-specific tokenisation and stemming."""
import argparse
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

import pyterrier as pt

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run-name", required=True)
args = parser.parse_args()
root = Path("/workspace")
sys.path.insert(0, str(root / "vendor/uniagent-code/cikm26/baselines/retrieval-baseline-pyterrier"))
from baseline import RETRIEVAL_CONFIGURATION

selected = {}
with gzip.open(root / "runs" / args.run_name / "phase3-evidence.jsonl.gz", "rt", encoding="utf-8") as stream:
    for line in stream:
        document = json.loads(line)
        selected[(document["dataset"], document["doc_id"])] = document

reports = []
for dataset_name, language in (("retrieval-de-spot-check", "de"), ("retrieval-en-spot-check", "en"),
                               ("retrieval-hessian-law-de-spot-check", "de")):
    audit = json.loads((root / "reports" / args.run_name / "phase3" / f"{dataset_name}.json").read_text())
    tokeniser = pt.TerrierTokeniser.java_tokeniser(RETRIEVAL_CONFIGURATION[language]["tokeniser"])
    stemmer_class = RETRIEVAL_CONFIGURATION[language]["stemmer"].value
    stemmer = pt.java.autoclass(f"org.terrier.terms.{stemmer_class}")(None)
    stopwords = set(RETRIEVAL_CONFIGURATION[language]["stopwords"]) if language == "de" else set()

    def terms(text):
        # English stopwords are not removed here; the targeted diagnostics use content words.
        return Counter(str(stemmer.stem(str(token).lower())) for token in tokeniser.getTokens(text)
                       if str(token).lower() not in stopwords)

    for query in audit["queries"]:
        if query["bucket"] == "rank_1_10":
            continue
        query_terms = terms(query["query"])
        docs = []
        for info in query["judged"] + query["top5"][:1]:
            document = selected[(dataset_name, info["doc_id"])]
            counts = terms(document["text"])
            docs.append({"doc_id": info["doc_id"], "rank": info["rank"], "words": info["words"],
                         "title": info["title"], "query_term_counts": {term: counts[term] for term in query_terms},
                         "vehicle_or_separation_terms": {term: count for term, count in counts.items()
                                                          if any(part in term for part in ("trennung", "kraftfahr", "wegstreck", "consum"))}})
        reports.append({"dataset": dataset_name, "qid": query["qid"], "query": query["query"],
                        "stemmed_query_terms": list(query_terms), "documents": docs})
output = root / "reports" / args.run_name / "phase3/term-diagnostics.json"
output.write_text(json.dumps(reports, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(reports, indent=2, ensure_ascii=False))
