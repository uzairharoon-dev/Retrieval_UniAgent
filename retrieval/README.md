# BM25 token-length and fusion variants

Phase 4 development is complete. See [the full comparison](../reports/PHASE4-COMPLETE.md)
for the passage candidate and the shared-text-index alternative recommended
for Phase 5 validation.

This is the first participant variant, adapted from the organizers' PyTerrier
baseline at revision `aaba38d87063016fa2b6b76fd43dc8b077ba7648`.

The German maximum token length is raised from 20 to 64 characters before
indexing and query tokenisation. The index also stores the same property.
English keeps the original limit of 20. Language-specific stemming,
stopwords, BM25, result depth, document IDs, and input fields follow the
baseline. Retrieval does not read relevance labels or use an LLM.

## Build and run

From the project root, with the official source prepared and Docker running:

```powershell
.\scripts\run-baseline.ps1 -Variant long-tokens -RunName long-tokens-experiment
```

This builds the official base, its evaluator dependency image, and this
variant. The variant image runs 20 upstream tests and two integration tests
during its build. The integration tests verify long terms in the index,
distinct retrieval for previously collapsed queries, and restoration of
English tokenisation when switching languages.

Once images exist, add `-SkipBuild`. Each run name must be new.

To invoke the container directly, mount your inputs and output directory and
pass `--dataset /input --output /output --wmodel BM25` to
`uniagent-task1-bm25:long-tokens`. Its entrypoint is
`python3 /app/baseline.py`. Outputs include `run.txt.gz`, language and system
configuration, and indexing/retrieval resource metadata.

The Dockerfile depends on the local `uniagent-task1-runner:baseline` image
created by the launcher. TIRA packaging and submission are a later milestone.
No event trace is needed for this statistical pipeline without model/tools,
as explained in the organizers' event-logging contract.

## Status

The experiment improved legal retrieval but regressed one German university
query. It remains an explicitly selected experimental variant; the launcher
still defaults to the original baseline. See [the measured comparison](../reports/PHASE4.md).

The copied German stopword list retains its original notice in
`german-stopwords.NOTICE`.

## Fixed reciprocal-rank fusion

`fusion_system.py` runs the 20- and 64-character German pipelines sequentially
in separate child processes, so Java class-initialisation settings cannot leak
between token limits,
and combines their rankings. For each document, its score is the sum of
`1 / (60 + rank)` over the component lists containing it. Ranks start at one;
component scores are only used to establish order. Every query uses equal
weights and the same constant 60. No labels or query-specific exceptions
enter this calculation.

Component ties and final ties use descending document ID, matching the
comparison convention. The union is truncated to the top 1,000 documents.
English runs the unchanged 20-character pipeline once and reuses its ranking
as both components, avoiding a redundant index build.

```powershell
.\scripts\run-baseline.ps1 -Variant fusion -RunName fusion-experiment
```

The shared image contains both systems. The launcher chooses
`/app/fusion_system.py` for `-Variant fusion`; the Dockerfile's default
entrypoint remains the long-token baseline. For direct container execution,
override the entrypoint with `python3` and invoke `/app/fusion_system.py` with
`--dataset` and `--output`.

Component rankings and resource metadata are stored under `components/short`
and `components/long`. `fusion-ir-metadata.yml` records only the fusion stage;
`system.json` records the full pipeline time including dataset-adapter loading
and child-process startup.
Use these scopes when comparing runtime and memory.

The corrected experiment and its measured tradeoff are documented in
[reports/PHASE4-FUSION.md](../reports/PHASE4-FUSION.md).

## Remaining Phase 4 representation experiments

`representation_system.py` supports three fixed experiments:

- `compound`: keep whole German terms and add two corpus-supported word parts.
  The vocabulary uses only document text and requires a part in at least five
  documents, at least four characters per part. German linking elements are
  allowed between parts. English text is unchanged.
- `deduplicated`: apply the compound representation, index identical source
  text once, and expand scores back to every original document ID. This
  preserves exact-ID evaluation and changes collection statistics; it does
  not enforce diverse result lists.
- `passages`: apply the compound representation to full documents and
  300-word windows with stride 200. Windows include up to 24 heading words.
  The best representation score becomes the source document score.

All modes return at most 1,000 original document IDs per query, sorted by
score and descending document ID for ties. Passage retrieval considers up to
5,000 representations before source-document aggregation. No relevance
labels, synthetic narratives, or external models are used by retrieval.

```powershell
.\scripts\run-baseline.ps1 -Variant compound -RunName compound-repeat
.\scripts\run-baseline.ps1 -Variant deduplicated -RunName shared-index-repeat
.\scripts\run-baseline.ps1 -Variant passages -RunName passages-repeat
```

The launcher builds `uniagent-task1-bm25:representations` and selects the
representation entrypoint. Build tests include the 20 upstream tests plus
11 tokenisation, fusion, and representation checks. Source-ID mappings,
learned vocabularies, and applied settings are saved beside each run.

`scripts/run-remaining-phase4.ps1` executes the fixed three-experiment batch
with existing images; its original run names must not already exist. The
parameter plan is recorded in `reports/phase4-experiment-plan.json`.
