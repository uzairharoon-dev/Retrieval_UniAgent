"""Build BM25 indexes at limits 20/64 and fuse their rankings without qrels."""
import json
import time
import subprocess
import sys
from pathlib import Path

import click
import pyterrier as pt
from tira.third_party_integrations import ir_datasets
from tirex_tracker import tracking

from baseline import detect_query_language
from fusion import RRF_K, fuse_runs


def retrieve_component(dataset_path, output, limit):
    output.mkdir(parents=True, exist_ok=True)
    # Java tokeniser classes retain configuration from class initialisation.
    # A fresh process ensures each limit applies to both indexing and queries.
    subprocess.run([sys.executable, str(Path(__file__).with_name("baseline.py")),
                    "--dataset", str(dataset_path), "--output", str(output),
                    "--max-term-length", str(limit)], check=True)
    return pt.io.read_results(output / "run.txt.gz")


def run_fusion(dataset_path, output: Path):
    started = time.perf_counter()
    language = detect_query_language(ir_datasets.load(str(dataset_path)))
    output.mkdir(parents=True, exist_ok=True)
    (output / "language.txt").write_text(language + "\n", encoding="utf-8")
    short_run = retrieve_component(dataset_path, output / "components/short", 20)
    if language == "de":
        long_run = retrieve_component(dataset_path, output / "components/long", 64)
    else:
        # The two English components are identical; avoid redundant indexing.
        long_run = short_run
    with tracking(export_file_path=output / "fusion-ir-metadata.yml"):
        fused = fuse_runs(short_run, long_run)
        pt.io.write_results(fused, output / "run.txt.gz")
    (output / "system.json").write_text(json.dumps({
        "method": "BM25 reciprocal-rank fusion (20/64)", "language": language,
        "rrf_k": RRF_K, "weights": [1, 1], "depth": 1000,
        "component_limits": [20, 64] if language == "de" else [20, 20],
        "english_component_reused": language == "en",
        "end_to_end_seconds": time.perf_counter() - started,
        "component_process_isolation": True,
        "timing_scope": "dataset loading, language detection, child processes, indexing, retrieval, fusion and run writing",
    }, indent=2) + "\n", encoding="utf-8")
    return fused


@click.command()
@click.option("--dataset", required=True)
@click.option("--output", required=True, type=click.Path(path_type=Path, file_okay=False))
def main(dataset, output):
    run_fusion(dataset, output)


if __name__ == "__main__":
    main()
