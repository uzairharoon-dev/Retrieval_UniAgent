# Phase 5: validation and final selection

**Complete. Selected: passage BM25 with corpus-derived German compounds.** Retain shared-text indexing (`deduplicated`) as the cheaper alternative. Nothing has been submitted.

Selection follows the rule fixed before Phase 4: equal-weight mean canonical ir_measures nDCG@10 across the three corpora, then mean Recall@100. Parameters are unchanged; no further search was performed.

## Quality and evaluator sensitivity

| System | Canonical mean nDCG@10 | Local TIRA mean nDCG@10 |
| --- | ---: | ---: |
| bm25-20261012-231608 | 0.547680 | 0.620197 |
| phase4-long-tokens-64 | 0.600349 | 0.672866 |
| phase4-rrf60-isolated | 0.549215 | 0.549215 |
| phase4-compound | 0.619392 | 0.619392 |
| phase4-deduplicated | 0.623729 | 0.623729 |
| phase4-passages | 0.666854 | 0.666854 |

The selected canonical score is 0.666854, versus 0.547680 originally (21.76% relative). This percentage applies only to canonical evaluation.

**The long-token variant has the highest local TIRA mean.** The local evaluator preserves file order for tied scores; ir_measures orders ties by document ID. Duplicate texts and sparse labels make this consequential. Passage selection is based on the declared common tie convention; it is not a claim to be the best under every evaluator. See [the baseline tie investigation](BASELINE.md).

Passages regresses German nDCG@10 from 0.480303 to 0.465432 and Recall@100 from 1.00 to 0.96; the German library positive is rank 101. It improves English nDCG@10 from 0.762747 to 0.874282 and law from 0.399989 to 0.660848. Against the original, 27 judged-document ranks/AP improve, 7 regress, and 31 are unchanged; these are not counts of nDCG gains.

The deduplicated alternative scores 0.623729 canonical mean, improves corpus-level nDCG and does not reduce corpus-level Recall@100 versus the original. It still has per-query regressions. These are development results from 65 synthetic, single-positive judgments, not a held-out quality estimate.

## Fresh execution proof

Both candidates were repeated on all three corpora in fresh containers. Retrieval received only a read-only directory containing documents and queries, plus a fresh output directory. Labels, evaluator scripts, and the workspace were excluded. Evaluation read qrels in separate containers after retrieval.

All six decompressed TREC outputs exactly reproduce Phase 4, including row order and score strings. Input hashes, image/source hashes, all original source IDs, query coverage, output format and metric agreement passed. The unchanged image previously passed all 31 Docker tests.

The entire retrieval container was capped at 4 CPUs and 3 GiB, with no swap and no network. All six exited successfully without OOM. This covers vocabulary preparation and serialization that the stage trackers omit; it establishes a cap, not an exact peak measurement.

| Mode / corpus | Queries | Returned documents/query, min-max | Full container seconds |
| --- | ---: | ---: | ---: |
| phase5-passages / retrieval-de-spot-check | 25 | 27-1000 | 214.2 |
| phase5-passages / retrieval-en-spot-check | 25 | 1000-1000 | 128.9 |
| phase5-passages / retrieval-hessian-law-de-spot-check | 15 | 827-1000 | 186.0 |
| phase5-deduplicated / retrieval-de-spot-check | 25 | 27-1000 | 89.0 |
| phase5-deduplicated / retrieval-en-spot-check | 25 | 1000-1000 | 42.2 |
| phase5-deduplicated / retrieval-hessian-law-de-spot-check | 15 | 1000-1000 | 53.5 |

Passages retrieves up to 5,000 representations and returns **up to** 1,000 original documents; repeated parents and matching vocabulary can yield fewer. Runtime and memory on private inputs remain unverified.

## Handoff to Phase 6

Use the selected system explicitly:

```powershell
.\scripts\run-baseline.ps1 -Variant passages -RunName selected-check -SkipBuild
```

The launcher default remains the original baseline for reference. Phase 6 must provide the final reproducible image build and selected entrypoint, verify the TIRA input contract (including language handling), and run the submission dry run. Registration/authentication and submission have not been performed.

Evidence: [selection and checks](phase5/selection.json), [input hashes](phase5/inputs.json), [container exit states and timings](phase5/executions.json). Per-corpus metrics and saved retrieval-container inspections are in `phase5-passages/` and `phase5-deduplicated/`. Raw runs remain in ignored `runs/`.

Reproduce fresh execution with `scripts/validate-phase5.ps1` in a clean workspace (fixed run names reject overwriting), then run `scripts/summarise-phase5.py` inside the tested representations image with the workspace mounted at `/workspace`.
