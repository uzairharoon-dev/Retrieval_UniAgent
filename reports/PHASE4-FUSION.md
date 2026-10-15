# Phase 4, experiment 2: fixed reciprocal-rank fusion

Accepted run: `phase4-rrf60-isolated`. The experiment is complete.
Fusion recovers the library document into the top 100 and preserves the
long-token variant's legal Recall@100, but sacrifices much of its legal
top-ten ranking gain. Keep it as an experimental option, not the new default.

## Method and verification

Two BM25 rankings are generated for each German query: token limits 20 and 64.
Each document receives `1/(60 + rank)` from each list containing it, with
one-based ranks and equal weights. The union is sorted and truncated to 1,000
documents. Component and final ties use descending document ID. The same rule
applies to every query; no labels, exceptions, or parameter sweep were used.

The components run sequentially in separate child processes. A first attempt
changed the token limits inside one Java process and reproduced the short
pipeline in both components. That run is explicitly
[invalidated](phase4-rrf60/INVALID.md). The integration test was strengthened
to require different component winners for a query distinguishing the two
token limits. Only the corrected run is analysed here.

English uses its unchanged 20-character ranking twice, with one actual index
build. Its canonical document order is identical to the baseline, although
the final scores are reciprocal-rank scores rather than BM25 scores.

All 26 tests passed. Full offline retrieval/evaluation completed on all three
datasets. Dataset hashes match the original experiments. The
[component verification](phase4-rrf60-isolated/component-verification.json)
checks every returned query/document score: the short component matches the
original baseline, the long component matches the standalone long-token
experiment, and the fused scores reproduce the saved components.

## Effectiveness

Metrics below use the same ir_measures evaluator and tie convention.

| Dataset | Baseline nDCG@10 | Long-token nDCG@10 | Fusion nDCG@10 | Recall@100 baseline / long / fusion |
| --- | ---: | ---: | ---: | --- |
| German university | 0.480303 | 0.460303 | 0.460303 | 1.000 / 0.960 / 1.000 |
| English university | 0.762747 | 0.762747 | 0.762747 | 1.000 / 1.000 / 1.000 |
| Hessian law | 0.399989 | 0.577995 | 0.424593 | 0.800 / 0.933 / 0.933 |

Fusion MAP is 0.378969 for German university, 0.716313 for English, and
0.384236 for law. Relative to the original baseline, law has five improved
judged ranks, ten unchanged, and no regressions. Relative to long-token-only
retrieval, four of those five improvements weaken. German university has
one regression versus the original baseline, and one improvement versus
the long-token variant. English has no judged-rank changes.

## Targeted query ranks

| Dataset/query | Original | Long tokens | Fusion |
| --- | ---: | ---: | ---: |
| German 37, library journals | 3 | 156 | 11 |
| Law 2, Reisekostenerstattung | 36 | 1 | 11 |
| Law 7, Wegstreckenentschädigung | 148 | 11 | 37 |
| Law 9, Verwaltungsvorschriften | 492 | 9 | 34 |
| Law 11, insurance after hotel fall | 2 | 1 | 1 |
| Law 15, Personalratsmitglieder | 96 | 1 | 25 |

The library recovery is partial: rank 11 restores Recall@100, but remains
outside nDCG@10's cutoff. Law queries 7 and 9 stay within the top 100.
Law 8's judged metadata-only document remains absent. The original query's
incorrect broad matches still contribute to RRF, so documents strong only
in the long-token ranking can be demoted by the combined ordering. This
explains the mechanism of the tradeoff; it is not a score-attribution study.

The local TIRA evaluator agrees with ir_measures for this fusion output.
Comparisons to the original German TIRA score must still account for the
previously documented duplicate/tie-ordering difference. Original TIRA
0.697856 and original ir_measures 0.480303 are not interchangeable.

## Cost

These are single local measurements, not estimates of TIRA performance:

| Dataset | Full system seconds | Short index seconds | Long index seconds | Fusion seconds |
| --- | ---: | ---: | ---: | ---: |
| German university | 129.657 | 46.277 | 48.180 | 0.752 |
| English university | 68.777 | 50.376 | Reused | 0.886 |
| Hessian law | 80.346 | 24.273 | 24.336 | 0.310 |

Full time includes dataset loading, child-process startup, indexing, retrieval,
fusion, and run writing; it excludes Docker startup, the outer data audit,
evaluation, and image building. Earlier single-pipeline reports measured
index/retrieval stages separately, so their durations are not directly
comparable with the full-time column.

Resource summaries retain the tracker's raw process-RAM readings. For example,
German indexing peaks are 1,458,941 for the short child and 1,465,282 for the
long child; the fusion parent peaks at 134,938. These are individually tracked
process stages, not a measured overall process-tree peak, and must not be
summed or compared as total-system memory. Complete stage metadata remains
under the run's component directories.

The main extra cost is two independent German index builds; fusion itself
takes under a second in these measurements.

## Reproduce

```powershell
.\scripts\run-baseline.ps1 -Variant fusion -RunName another-fusion-run
docker run --rm --network none --mount "type=bind,source=$PWD,target=/workspace" --entrypoint python3 uniagent-task1-runner:baseline /workspace/scripts/compare-runs.py --candidate another-fusion-run
```

Add `-SkipBuild` only with the corrected image already built. Use a new run
name. The launcher builds the shared retrieval image and invokes
`/app/fusion_system.py`; the Dockerfile's default entrypoint is still the
long-token baseline.

Saved evidence:

- [Comparison against original BM25](phase4-rrf60-isolated/comparison.json)
- [Comparison against long-token BM25](phase4-rrf60-isolated/comparison-long-tokens.json)
- [Component reproduction checks](phase4-rrf60-isolated/component-verification.json)
- Per-dataset evaluations and hashes: `reports/phase4-rrf60-isolated/`.
- Rankings, system configuration, and raw resource metadata:
  `runs/phase4-rrf60-isolated/` (ignored by Git).

## Decision and next work

Equal-weight RRF with constant 60 did not achieve complete library recovery
while retaining legal top-ten gains. No weights or constants were selected
after looking at these judgments. Keep both the stronger legal long-token
variant and this fusion variant for comparison; the launcher still defaults
to the original baseline.

Next, test German compound handling as a separate change. Retain whole terms
while adding useful component-word matches, then evaluate the library query,
the five legal improvements, and all previous successes together. The
remaining HTGV miss also motivates compound matching. Duplicate handling
and passage scoring remain later controlled experiments.

Spot-check queries and labels are synthetic with one judged document per
query. These measurements do not establish effectiveness on the private
administrative test set. No submission or publication was performed.
