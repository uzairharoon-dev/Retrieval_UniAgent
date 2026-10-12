# Initial BM25 baseline

Completed run: `bm25-20261012-231608`.

The official PyTerrier baseline was built in Docker; all 20 upstream tests
passed. Retrieval and evaluation completed with networking disabled. All 65
queries received results, and all three TREC run files passed format and ID
validation. Baseline source revision:
`aaba38d87063016fa2b6b76fd43dc8b077ba7648`.

| Dataset | Documents | Queries | TIRA local nDCG@10 | ir_measures nDCG@10 | Recall@100 | MAP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| German university | 30,983 | 25 | 0.697856 | 0.480303 | 1.000000 | 0.388666 |
| English university | 24,171 | 25 | 0.762747 | 0.762747 | 1.000000 | 0.716313 |
| Hessian law | 2,829 | 15 | 0.399989 | 0.399989 | 0.800000 | 0.341545 |

## Why the German scores differ

The local TIRA evaluator passes the run's file order directly to trectools.
ir_measures uses document IDs to break equal-score ties. Reordering equal-score
documents by descending document ID reproduces the ir_measures score exactly;
preserving file order reproduces the TIRA score exactly. Sixteen German queries
are affected. This is an evaluation tie-ordering difference, not a failed run.

Evidence: [tie diagnostics](bm25-20261012-231608/retrieval-de-spot-check-ties.json).
Both metric outputs are retained. Use one fixed tie convention when comparing
future systems; avoid claiming improvement caused only by tie ordering.

## Interpretation and next work

There is only one judged relevant document per query, and these spot-check
queries and judgments are synthetic. Treat unjudged documents cautiously;
these measurements establish pipeline functionality, not final-test quality.

The baseline finds every judged relevant university document in the top 100.
On the Hessian-law dataset, queries 7, 8, and 9 miss their judged document in
the top 100. Start error analysis there, then investigate the German score ties
and whether identical text appears under different document IDs.

## Artifacts

- [Dataset audit](bm25-20261012-231608/data-audit.json)
- [German evaluation](bm25-20261012-231608/retrieval-de-spot-check-bm25.json)
- [English evaluation](bm25-20261012-231608/retrieval-en-spot-check-bm25.json)
- [Hessian-law evaluation](bm25-20261012-231608/retrieval-hessian-law-de-spot-check-bm25.json)
- Rankings and resource metadata: `../runs/bm25-20261012-231608/`.

No TIRA submission or remote publication has been performed.
