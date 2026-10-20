"""Passage BM25 (query + description) followed by cross-encoder reranking.

Stage 1 is `representation_system.py --mode passages --use-description`.
Stage 2 scores the best BM25 passage of each of the top `depth` source
documents with a local multilingual cross-encoder and fuses the cross-encoder
rank with the BM25 rank by weighted reciprocal rank fusion (k=60). Documents
below `depth` keep their BM25 order. Queries that do not fit in the time budget
keep their plain BM25 ranking, so the run always completes.
"""
import json
import time
from pathlib import Path

import click
import pandas as pd
import pyterrier as pt
from tira.third_party_integrations import ir_datasets
from tirex_tracker import tracking

from baseline import RETRIEVAL_CONFIGURATION, configure_token_limit, create_index, detect_query_language
from representations import CompoundExpander, RepresentationDataset, aggregate_parents, query_text


def cross_encoder_input(query):
    text = query.default_text()
    original = getattr(query, "original_query", None)
    if isinstance(original, dict):
        description = original.get("description")
        if isinstance(description, str) and description.strip():
            return f"{text}. {description.strip()}"
    return text


def best_passages(raw, parent_ids):
    """Map (qid, source docno) to its highest-scoring representation id."""
    best = {}
    for row in raw.sort_values("score", ascending=False).itertuples():
        for parent in parent_ids[str(row.docno)]:
            best.setdefault((str(row.qid), parent), str(row.docno))
    return best


def fuse(ranking, ce_scores, depth, weight, k=60):
    """Re-sort the top `depth` documents of one query by weighted RRF of BM25 and CE ranks."""
    head = ranking[:depth]
    ce_order = sorted(range(len(head)), key=lambda position: (-ce_scores[position], position))
    ce_rank = {position: rank for rank, position in enumerate(ce_order)}
    fused = sorted(range(len(head)), key=lambda position: (
        -(weight / (k + ce_rank[position] + 1) + (1 - weight) / (k + position + 1)), position))
    return [head[position] for position in fused] + ranking[depth:]


def run(dataset, output, model_path, depth, weight, max_length, budget_seconds):
    from sentence_transformers import CrossEncoder
    started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=True)
    language = detect_query_language(dataset)
    expander = None
    if language == "de":
        expander = CompoundExpander.from_dataset(dataset, RETRIEVAL_CONFIGURATION[language]["stopwords"])
    view = RepresentationDataset(dataset, expander, "passages", keep_texts=True)
    index = create_index(view, language, output)
    configure_token_limit(language)
    tokenizer = pt.TerrierTokeniser.java_tokeniser(RETRIEVAL_CONFIGURATION[language]["tokeniser"])
    queries = list(dataset.queries_iter())
    topics = pd.DataFrame([{"qid": str(query.query_id),
                            "query": " ".join(tokenizer.getTokens(view.transform(query_text(query, True))))}
                           for query in queries])
    raw = pt.terrier.Retriever(index, wmodel="BM25", num_results=5000).transform(topics)
    index.close()
    bm25 = aggregate_parents(raw, view.parent_ids, order=view.order)
    passages = best_passages(raw, view.parent_ids)
    model = CrossEncoder(str(model_path), max_length=max_length, device="cpu", trust_remote_code=True)
    rerank_started = time.perf_counter()
    reranked, skipped, rows = 0, [], []
    with tracking(export_file_path=output / "rerank-ir-metadata.yml"):
        for query in queries:
            qid = str(query.query_id)
            ranking = bm25[bm25.qid == qid].sort_values("rank").docno.tolist()
            if ranking and time.perf_counter() - rerank_started < budget_seconds:
                head = ranking[:depth]
                pairs = [(cross_encoder_input(query), view.texts[passages[(qid, docno)]]) for docno in head]
                scores = [float(value) for value in model.predict(pairs, batch_size=16, show_progress_bar=False)]
                ranking = fuse(ranking, scores, depth, weight)
                reranked += 1
            elif ranking:
                skipped.append(qid)
            rows += [{"qid": qid, "docno": docno, "rank": rank, "score": float(len(ranking) - rank)}
                     for rank, docno in enumerate(ranking)]
    result = pd.DataFrame(rows, columns=["qid", "docno", "rank", "score"])
    pt.io.write_results(result, output / "run.txt.gz")
    (output / "language.txt").write_text(language + "\n", encoding="utf-8")
    config = {"method": "BM25 passages (query+description) + cross-encoder RRF rerank", "language": language,
              "model": str(model_path), "rerank_depth": depth, "ce_weight": weight, "rrf_k": 60,
              "max_length": max_length, "passages_per_document": 1, "budget_seconds": budget_seconds,
              "queries_reranked": reranked, "queries_skipped_for_budget": skipped,
              "rerank_seconds": time.perf_counter() - rerank_started,
              "end_to_end_seconds": time.perf_counter() - started}
    (output / "system.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(config, indent=2), flush=True)
    return result


@click.command()
@click.option("--dataset", required=True)
@click.option("--output", required=True, type=click.Path(path_type=Path, file_okay=False))
@click.option("--model", "model_path", default="/models/reranker", show_default=True)
@click.option("--depth", default=50, show_default=True)
@click.option("--weight", default=0.7, show_default=True, help="Cross-encoder weight in rank fusion.")
@click.option("--max-length", default=512, show_default=True)
@click.option("--budget-seconds", default=5400, show_default=True,
              help="Stop reranking further queries after this many seconds of reranking.")
def main(dataset, output, model_path, depth, weight, max_length, budget_seconds):
    run(ir_datasets.load(dataset), output, model_path, depth, weight, max_length, budget_seconds)


if __name__ == "__main__":
    main()
