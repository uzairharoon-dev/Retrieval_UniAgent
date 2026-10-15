# Phase 4, experiment 1: retain long German tokens

Run: `phase4-long-tokens-64`, compared with `bm25-20261012-231608`.
This experiment is complete. It improves Hessian-law retrieval substantially,
but has one German university regression. Keep it as a tested experimental
variant rather than adopting it globally as the default.

## Change

The participant implementation is in `retrieval/`. It raises Terrier's German
`max.term.length` from 20 to 64 for both document indexing and query
tokenisation, including the index property. English remains at 20. It
otherwise retains the baseline's input text, stopwords, stemmers, BM25, and
document IDs. `system.json` records the applied limit for each dataset.

The value 64 is a conservative first experiment that covers the observed
21–24-character compounds. It has not been tuned over a range of limits.

## Measured results

Dataset hashes match across the two runs. Metrics use the same ir_measures
implementation and descending document-ID ordering for equal-score ties.

| Dataset | nDCG@10 baseline → variant | Recall@100 baseline → variant | MAP baseline → variant |
| --- | --- | --- | --- |
| German university | 0.480303 → 0.460303 | 1.000000 → 0.960000 | 0.388666 → 0.375589 |
| English university | 0.762747 → 0.762747 | 1.000000 → 1.000000 | 0.716313 → 0.716313 |
| Hessian law | 0.399989 → 0.577995 | 0.800000 → 0.933333 | 0.341545 → 0.518547 |

English rankings and scores are exactly identical, not merely equal in the
aggregate metrics. German university has 24 unchanged judged ranks and one
regression. Law has five improved judged ranks, ten unchanged, and no
regressions. Counts classify changes in per-query average precision; they do
not assert that every unjudged result remains in the same position.

The local TIRA evaluator also improves on law: 0.399989 → 0.577995. It reports
0.697856 → 0.677856 on German university because of the previously documented
duplicate/tie-ordering difference. The same evaluator convention was used on
each side of every comparison.

## Query-level changes

| Dataset/query | Query | Judged rank before → after |
| --- | --- | --- |
| Law 2 | Reisekostenerstattung nach HRKG | 36 → 1 |
| Law 7 | Wegstreckenentschädigung eigenes Auto Dienstreise | 148 → 11 |
| Law 9 | Verwaltungsvorschriften Reisekostengesetz Hessen | 492 → 9 |
| Law 11 | Unfallversicherungsschutz Sturz Hotelzimmer Dienstreise | 2 → 1 |
| Law 15 | Fahrtkostenerstattung Personalratsmitglieder HRKG | 96 → 1 |
| German university 37 | Zeitschriften der Universitätsbibliothek | 3 → 156 |

Law queries 2 and 15 now retain their specific terms and retrieve different
judged documents first. Law 7 and 9 are recovered within the top 100.
Law 8 remains absent: retaining `Trennungsgeldverordnung` does not split it
into the query's separate `Trennungsgeld` and `Verordnung` terms. Its
metadata-only content limitation also remains.

The German library query regresses after `Universitätsbibliothek` is retained.
The experiment changes both query terms and index statistics, so their
individual contributions to this regression have not been isolated. Do not
hardcode this query or use its qrels to decide which tokenizer to apply.

## Validation and efficiency

- All 22 tests passed in the Docker build: 20 upstream tests and two added
  integration checks covering index vocabulary, actual retrieval, and language
  switching.
- Retrieval and evaluation completed with networking disabled on all three
  datasets. All 65 queries received results, and run-format/ID validation
  passed.
- Indexing times were 31.439 seconds for German, 39.060 seconds for English,
  and 16.468 seconds for law. Retrieval times were 0.553, 0.757, and 0.343
  seconds respectively. These are single local measurements from the resource
  tracker, exclude data loading/build/evaluation, and are not speedup claims.
- Original runs and dataset files were preserved. No submission was made.

## Reproduce

From the project root:

```powershell
.\scripts\run-baseline.ps1 -Variant long-tokens -RunName another-long-token-run
docker run --rm --network none --mount "type=bind,source=$PWD,target=/workspace" --entrypoint python3 uniagent-task1-runner:baseline /workspace/scripts/compare-runs.py --candidate another-long-token-run
```

Add `-SkipBuild` only if both baseline and variant images already exist.
The saved [comparison](phase4-long-tokens-64/comparison.json) contains all
65 query comparisons, both evaluator outputs, and resource summaries.
Per-dataset evaluation files and a data audit are in the same report directory.
Raw rankings and resource metadata are under
`runs/phase4-long-tokens-64/` (ignored by Git).

## Next experiment

Test combining the original and long-token rankings with a fixed fusion rule,
or a representation retaining both split and full compounds, to recover long
terms without losing successful short-term matches. Evaluate the library
regression and the five legal improvements together; select no query-specific
exceptions based on judgments. Separate compound splitting, duplicate
handling, and passage scoring into subsequent controlled experiments.

These spot-check topics and qrels remain synthetic and sparsely judged.
The results support the mechanism identified in Phase 3, but do not establish
private-test effectiveness or complete Phase 4's remaining experiments.
