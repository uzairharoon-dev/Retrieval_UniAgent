# UniAgent 2026 — Task 1 retrieval

This project starts with the organizers' PyTerrier BM25 baseline. It indexes
the provided documents, retrieves a ranked list for each query, and writes
`run.txt.gz` in TREC format. It uses no LLM or agent tools.

**Phase 5 is complete.** [Validation and final selection](reports/PHASE5.md)
selects passage BM25 under the declared canonical mean nDCG@10 rule and keeps
shared-text indexing as the cheaper alternative. Six fresh runs reproduced
every ranking row and score with labels excluded, no network, 4 CPUs and a
3 GiB memory cap. The report discloses German regressions and the different
system ordering under local TIRA tie handling. [Phase 4 results](reports/PHASE4-COMPLETE.md)
compare all six systems on the three development corpora.

```powershell
.\scripts\run-baseline.ps1 -Variant passages -RunName passages-repeat
.\scripts\run-baseline.ps1 -Variant deduplicated -RunName shared-index-repeat
```

The initial run completed on all three datasets. Results, validation, and the
German score tie-ordering explanation are in [reports/BASELINE.md](reports/BASELINE.md).

Phase 3 is complete. [reports/PHASE3.md](reports/PHASE3.md) documents token loss,
duplicate pages, vocabulary mismatches, all 13 cases outside the top ten, and
the priorities for the next experiments.

The first Phase 4 experiment is complete: [reports/PHASE4.md](reports/PHASE4.md).
Retaining long German tokens improves legal retrieval and regresses one
university query; the original baseline remains the launcher's default.

```powershell
.\scripts\run-baseline.ps1 -Variant long-tokens -RunName long-tokens-experiment
```

The fixed fusion experiment is also complete:
[reports/PHASE4-FUSION.md](reports/PHASE4-FUSION.md). It restores university
Recall@100 and preserves legal Recall@100, but weakens legal top-ten ranking.

```powershell
.\scripts\run-baseline.ps1 -Variant fusion -RunName fusion-experiment
```

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

## Submit through GitHub Actions

The workflow [Upload Software to TIRA](.github/workflows/upload-software-to-tira.yml)
adapts the downloaded UniAgent template for Task 1 retrieval. It builds from
`retrieval/` using the standalone `Dockerfile.tira`, runs the 31 image tests,
validates output on TIRA's German spot-check dataset, and uploads passage BM25.

In this GitHub repository, open **Settings > Secrets and variables > Actions**
and add a repository secret named **`TIRA_CLIENT_TOKEN`** with the TIRA token
from your registered team's submission page. Then open **Actions > Upload
Software to TIRA > Run workflow**, select `main`, and run it. The workflow
is manual; commits and pushes do not trigger an upload. After it succeeds,
select the uploaded system and dataset on TIRA and click **RUN** to execute it
there. No local `vendor/` datasets or `runs/` artifacts are needed by the action.

The standalone image passed all 31 tests, and the official TIRA CLI dry run
produced valid outputs on `retrieval-de-spot-check-20260816-training`. No
upload or execution on TIRA's servers has been performed locally.

## Next milestone

Phase 6: package the selected passage system with a reproducible image build
and the correct default entrypoint, verify the TIRA input contract, and run
the submission dry run. A real TIRA submission requires participant
registration; nothing has been submitted. Use `-Variant passages` explicitly
to run the selected system; the launcher's default remains the original
baseline for reference.
