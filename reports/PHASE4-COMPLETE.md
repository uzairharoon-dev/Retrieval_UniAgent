# Phase 4 complete

The fixed development experiment set is complete. The recommended candidate for Phase 5 is **phase4-passages**. This is a development recommendation, not the final submission selection.

## Results

nDCG@10, using the same ir_measures evaluator and descending document-ID tie convention:

| System | German university | English university | Hessian law | Mean across corpora |
| --- | ---: | ---: | ---: | ---: |
| Official BM25 | 0.480303 | 0.762747 | 0.399989 | 0.547680 |
| Long tokens | 0.460303 | 0.762747 | 0.577995 | 0.600349 |
| RRF fusion | 0.460303 | 0.762747 | 0.424593 | 0.549215 |
| Compounds | 0.510833 | 0.762747 | 0.584595 | 0.619392 |
| Shared-text index | 0.510833 | 0.775757 | 0.584595 | 0.623729 |
| Passages | 0.465432 | 0.874282 | 0.660848 | 0.666854 |

The recommendation uses the equal-weight mean across the three corpora, fixed in the [experiment plan](phase4-experiment-plan.json). The JSON summary also reports query-weighted means, Recall@100, and every query's rank. No parameter sweep or query-specific rules were used.

## Recommended candidate versus baseline

| Corpus | Baseline Recall@100 | Candidate Recall@100 |
| --- | ---: | ---: |
| retrieval-de-spot-check | 1.000000 | 0.960000 |
| retrieval-en-spot-check | 1.000000 | 1.000000 |
| retrieval-hessian-law-de-spot-check | 0.800000 | 0.933333 |

Judged ranks improved on 27 queries and regressed on 7; the remaining 31 are unchanged.

## Targeted cases

| Case | Baseline | Long | Fusion | Compound | Shared index | Passages |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| German library query | 3 | 156 | 11 | 74 | 79 | 101 |
| English consumables | 81 | 81 | 81 | 81 | 85 | 7 |
| Law 2 | 36 | 1 | 11 | 2 | 2 | 1 |
| Law 7 | 148 | 11 | 37 | 7 | 7 | 7 |
| Law 8 | Absent | Absent | Absent | 203 | 203 | 187 |
| Law 9 | 492 | 9 | 34 | 33 | 33 | 1 |
| Law 11 | 2 | 1 | 1 | 1 | 1 | 2 |
| Law 15 | 96 | 1 | 25 | 1 | 1 | 1 |

## What was tested

- **Compounds:** a vocabulary learned only from document text, minimum document frequency 5; original words retained and at most two corpus-supported parts added. German token limit 64; English unchanged.
- **Shared-text indexing:** exact source-text duplicates indexed once, with scores expanded back to every original ID. This changes collection statistics; it does not remove duplicate IDs from final results.
- **Passages:** compound representation plus retained full documents and 300-word windows at stride 200, with up to 24 heading words. Retrieve 5,000 representations, aggregate by maximum score, return 1,000 original documents.

## Validation and cost

All 31 Docker tests passed. All nine new corpus/variant runs completed offline and passed run-format/ID validation. Input hashes match the original baseline. [Full-corpus verification](PHASE4-VERIFICATION.json) checks source-ID preservation in every representation, the unchanged English compound control, and the legal deduplication control.

| Variant / corpus | Source documents | Indexed representations | End-to-end seconds |
| --- | ---: | ---: | ---: |
| phase4-compound / retrieval-de-spot-check | 30983 | 30983 | 128.478 |
| phase4-compound / retrieval-en-spot-check | 24171 | 24171 | 72.718 |
| phase4-compound / retrieval-hessian-law-de-spot-check | 2829 | 2829 | 77.092 |
| phase4-deduplicated / retrieval-de-spot-check | 30983 | 25361 | 104.371 |
| phase4-deduplicated / retrieval-en-spot-check | 24171 | 21297 | 57.395 |
| phase4-deduplicated / retrieval-hessian-law-de-spot-check | 2829 | 2829 | 77.012 |
| phase4-passages / retrieval-de-spot-check | 30983 | 72782 | 202.096 |
| phase4-passages / retrieval-en-spot-check | 24171 | 63061 | 148.103 |
| phase4-passages / retrieval-hessian-law-de-spot-check | 2829 | 52043 | 203.864 |

These single local times include vocabulary preparation, indexing, retrieval, and run writing, but exclude adapter loading, Docker startup, and evaluation. Resource tracker files and the comparison JSON retain index/retrieval process-memory readings. These do not establish full private-test runtime or a process-tree memory peak.

## Limits and next phase

All scores use synthetic spot-check queries with one judged document per query. Unjudged results can be relevant; selection on these data does not prove held-out generalisation. Per-query regressions and the HTGV case remain visible rather than being hidden by the mean score. No new external model, parameter search, or submission was performed.

Phase 5 should validate the recommended candidate: deterministic fresh runs, retrieval without qrels, resource limits, input/output compatibility, and review of its regressions. Phase 6 will package and test the TIRA submission. The launcher's original default remains unchanged pending that validation.

## Reproduce and evidence

Build the shared retrieval image, then invoke one variant with a new run name:

```powershell
.\scripts\run-baseline.ps1 -Variant compound -RunName compound-repeat
```

Supported new variants are `compound`, `deduplicated`, and `passages`. `scripts/run-remaining-phase4.ps1` records the original fixed batch (its run names must not already exist). Evaluations, hashes and pairwise comparisons are under `reports/phase4-{compound,deduplicated,passages}/`. Raw rankings, vocabulary files, ID maps, and resource metadata are under the matching ignored `runs/` directories.

[Complete comparison and query ranks](PHASE4-SUMMARY.json).

## Balanced alternative for Phase 5

Also retain **phase4-deduplicated**: it has no corpus-level regression in nDCG@10 or Recall@100 versus the original baseline. Its highest mean score among such candidates makes it a useful alternative when reviewing the primary candidate's tradeoffs and runtime. This is not a claim of no per-query regressions.
