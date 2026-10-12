# UniAgent 2026 — Task 1 retrieval

This project starts with the organizers' PyTerrier BM25 baseline. It indexes
the provided documents, retrieves a ranked list for each query, and writes
`run.txt.gz` in TREC format. It uses no LLM or agent tools.

The initial run completed on all three datasets. Results, validation, and the
German score tie-ordering explanation are in [reports/BASELINE.md](reports/BASELINE.md).

Phase 3 is complete. [reports/PHASE3.md](reports/PHASE3.md) documents token loss,
duplicate pages, vocabulary mismatches, all 13 cases outside the top ten, and
the priorities for the next experiments.

## Run the baseline

Start Docker Desktop, then run from PowerShell:

```powershell
.\scripts\prepare-source.ps1 -SourceRoot C:\Users\umair\Desktop\uniagent-code
.\scripts\run-baseline.ps1
```

To reuse an already-built image:

```powershell
.\scripts\run-baseline.ps1 -SkipBuild
```

The script builds the official image and runs its tests, adds the pinned
`trectools==0.0.50` dependency required by TIRA's local evaluator, audits the three
spot-check datasets, runs BM25 on each, and evaluates each ranking. Execution
uses `--network none`; initial image downloads require internet access.
It stops on any build, retrieval, or evaluation failure.

Each execution uses a new timestamped run name. You can set a descriptive name
with `-RunName bm25-first`; an existing run directory is rejected because the
official resource tracker does not overwrite its metadata files.

Outputs:

- `runs/<run-name>/<dataset>/run.txt.gz`: newly generated rankings.
- `runs/<run-name>/<dataset>/*-ir-metadata.yml`: resource tracking.
- `reports/<run-name>/data-audit.json`: counts, fields, sample queries, and data hashes.
- `reports/<run-name>/<dataset>-bm25.json`: official local nDCG@10 evaluation plus
  ir_measures nDCG@10, Recall@100, MAP, and per-query scores.

Only the evaluation step reads qrels. The unmodified official baseline reads
queries and documents for indexing and retrieval.

## Source and data

Official source: https://github.com/uniagent-webis-de/uniagent-code

Local snapshot copied from `C:\Users\umair\Desktop\uniagent-code`, revision
`aaba38d87063016fa2b6b76fd43dc8b077ba7648`. Relevant files are kept under
`vendor/uniagent-code/cikm26/`; this directory and raw run artifacts are ignored
by Git. This is a selected source snapshot, not a completed Git checkout.

The German, English, and Hessian-law spot-check datasets are included in the
organizers' checkout. Their queries and relevance labels are synthetic.
Use results to validate the pipeline and investigate failures; improvements
on these small datasets do not establish performance on the private test set.

## Next milestone

Phase 4: first test retaining long German tokens in indexing and queries.
Compare each change
against this baseline, recording both effectiveness and resource use. A real
TIRA submission requires participant registration and a separate dry run;
running this script does not submit anything.
