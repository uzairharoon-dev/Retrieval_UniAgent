"""Controlled compound, duplicate-index, and passage-scoring experiments."""
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


def run(dataset, output, mode, use_description=False):
    started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=True)
    language = detect_query_language(dataset)
    expander = None
    lexicon_started = time.perf_counter()
    if language == "de":
        expander = CompoundExpander.from_dataset(dataset, RETRIEVAL_CONFIGURATION[language]["stopwords"])
        (output / "compound-lexicon.json").write_text(json.dumps(expander.lexicon, ensure_ascii=False), encoding="utf-8")
    lexicon_seconds = time.perf_counter() - lexicon_started
    view = RepresentationDataset(dataset, expander, mode)
    index = create_index(view, language, output)
    configure_token_limit(language)
    tokenizer = pt.TerrierTokeniser.java_tokeniser(RETRIEVAL_CONFIGURATION[language]["tokeniser"])
    topics = pd.DataFrame([{"qid": str(query.query_id),
                            "query": " ".join(tokenizer.getTokens(view.transform(query_text(query, use_description))))}
                           for query in dataset.queries_iter()])
    with tracking(export_file_path=output / "retrieval-ir-metadata.yml"):
        raw = pt.terrier.Retriever(index, wmodel="BM25", num_results=5000 if mode == "passages" else 1000).transform(topics)
        result = aggregate_parents(raw, view.parent_ids)
        pt.io.write_results(result, output / "run.txt.gz")
    index.close()
    (output / "language.txt").write_text(language + "\n", encoding="utf-8")
    (output / "representation-map.json").write_text(json.dumps(view.parent_ids), encoding="utf-8")
    config = {"method": f"BM25 corpus-derived compounds: {mode}", "language": language,
              "mode": mode, "query_fields": "query+description" if use_description else "query",
              "max_term_length": 64 if language == "de" else 20,
              "compound_min_document_frequency": 5, "compound_min_part_length": 4,
              "compound_max_parts": 2, "compound_max_word_length": 64,
              "links": ["", "s", "es", "en", "e", "er", "n"],
              "source_documents": view.source_documents, "indexed_representations": view.indexed_documents,
              "lexicon_words": len(expander.lexicon) if expander else 0,
              "lexicon_seconds": lexicon_seconds, "end_to_end_seconds": time.perf_counter() - started,
              "timing_scope": "lexicon building, indexing, retrieval, aggregation and run writing; excludes adapter loading",
              "passage_words": 300 if mode == "passages" else None,
              "passage_stride": 200 if mode == "passages" else None,
              "candidate_depth": 5000 if mode == "passages" else 1000, "document_depth": 1000}
    (output / "system.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(config, indent=2), flush=True)
    return result


@click.command()
@click.option("--dataset", required=True)
@click.option("--output", required=True, type=click.Path(path_type=Path, file_okay=False))
@click.option("--mode", type=click.Choice(["compound", "deduplicated", "passages"]), required=True)
@click.option("--use-description/--no-use-description", default=False, show_default=True,
              help="Append original_query.description to the keyword query when present.")
def main(dataset, output, mode, use_description):
    run(ir_datasets.load(dataset), output, mode, use_description)


if __name__ == "__main__":
    main()
