# Phase 3: BM25 error analysis

Analysed baseline run: `bm25-20261012-231608`. All 65 queries were checked.
The next experiment should fix German token loss before introducing semantic
models or reranking. Several failures have a direct preprocessing explanation.

## What was checked

For every query, the analysis compares the judged document with the top five
results, records source-order and TREC tie-order ranks, counts identical text,
and measures document length. Corpus text hashes identify exact duplicates;
whitespace-normalized hashes are also recorded. The first document's analysed
text was checked against the dataset adapter's `default_text()`, which the
baseline indexes. Single-positive-document ranks are cross-checked against the
saved per-query average precision for all 65 queries.

Ranks below use descending document-ID ordering to break score ties, matching
the existing ir_measures evaluation. Duplicate-equivalent text is a diagnostic
only; qrels and document IDs were not changed. Word counts use whitespace
splitting, not Terrier's indexed token count.

## Coverage and rank failures

| Dataset | Judged document in top 10 | Rank 11–100 | Rank over 100 | Absent from returned run |
| --- | ---: | ---: | ---: | ---: |
| German university, 25 queries | 20 | 5 | 0 | 0 |
| English university, 25 queries | 23 | 2 | 0 | 0 |
| Hessian law, 15 queries | 9 | 3 | 2 | 1 |

Thirteen queries have their judged document outside the top ten. The law
dataset has the three misses at depth 100: queries 7, 8, and 9.

## Finding 1: long German words disappear

The installed Terrier tokenizer has `MAX_TERM_LENGTH = 20`. Terms longer than
20 characters are excluded before stemming. The diagnostic uses the same
language-specific tokenizer, configured stemmer, and German stopword list as
the baseline. This is confirmed behaviour, rather than an inferred cause.

| Dataset/query | Dropped words | Effective content terms after stopwords and stemming | Judged rank |
| --- | --- | --- | ---: |
| Law 2 | Reisekostenerstattung (21 characters) | hrkg | 36 |
| Law 7 | Wegstreckenentschädigung (24) | eig, auto, dienstreis | 148 |
| Law 9 | Verwaltungsvorschriften (23) | reisekostengesetz, hess | 492 |
| Law 15 | Fahrtkostenerstattung (21), Personalratsmitglieder (22) | hrkg | 96 |

Law queries 2 and 15 collapse to the same `hrkg` query and receive the same
leading results despite asking different questions. In law query 9, the
requested document type disappears. The desired VV-HRKG document is 5,572
words long and ranks behind court judgments mentioning the surviving terms.

Three further queries lose long words even though they still retrieve their
judged document in the top ten: German university 37
(`Universitätsbibliothek`), law 11 (`Unfallversicherungsschutz`), and law 13
(`Dienstreisegenehmigung`). Seven queries are affected in total.

Evidence: [term diagnostics](bm25-20261012-231608/phase3/term-diagnostics.json).
These diagnostics count content-word occurrences; they do not decompose BM25
scores, and English diagnostic counts retain stopwords.

## Finding 2: duplicates consume result positions and distort sparse evaluation

| Dataset | Exact duplicate text groups | Documents in those groups | Redundant copies | Queries with repeated text in top 10 |
| --- | ---: | ---: | ---: | ---: |
| German university | 3,640 | 9,262 | 5,622 | 24/25 |
| English university | 1,632 | 4,506 | 2,874 | 17/25 |
| Hessian law | 0 | 0 | 0 | 0/15 |

Nineteen of the 25 judged German documents have identical-text copies. The
travel-management page has five IDs for URL variants including a trailing
slash, `.html`, a fragment, and an `index.php?id=...` URL. German query 2 gets
this identical text at rank 1, but its specifically judged ID is rank 4.
German query 1's judged ID is rank 11; an identical copy is already rank 8.

The previously observed German nDCG difference is therefore connected to
identical content and which ID is labelled relevant. The evidence confirms
identical text, not that every differently worded page is redundant.

Simply discarding duplicate IDs can discard the only labelled relevant ID.
Keep the mapping from content groups to original IDs in any future experiment.
Do not choose representatives using qrels or report duplicate-group relevance
as an official metric.

## Finding 3: vocabulary, compounds, and stemming need separate treatment

- **Law 7:** the query says `Auto`; the statute says `Kraftfahrzeug`. The
  most specific query term is also dropped by the length limit. This leaves
  broad travel wording and vehicle vocabulary mismatch.
- **Law 8:** the judged HTGV document contains just 42 words of title and
  amendment metadata, rather than eligibility rules. Its compound
  `Trennungsgeldverordnung` is 23 characters and is dropped. It has no indexed
  `trennungsgeld` or `verordn` term; the common `hess` term survives. The
  document is absent from the returned ranking. Retrieving this ID would not
  by itself supply the substantive rules requested by the query.
- **German 23:** `Vergaberegeln` does not match the judged page's wording
  `Vergaberechtliche Vorschriften`. Both judged and top-ranked pages match
  `beschaff`, but the top page mentions that stem five times, versus once in
  the judged page. The judged procurement-rules page ranks 19.
- **German 40:** the compound `Softwarelizenzen` does not match the judged
  page's wording `Software-/ Campuslizenzen`. A department's software inventory
  ranks first; the central procurement guidance ranks 21.
- **English 16:** Porter stemming maps “consumables” and “consumers” to
  `consum`. A 232-word page about consumers and agroforestry ranks first. The
  4,252-word project-administration page has an explicit section about
  procuring consumables with third-party funding, but ranks 81. Its targeted
  section is diluted within a broad document; the score contribution of
  length versus the stem collision has not been isolated experimentally.

## Finding 4: broad documents and incomplete judgments complicate ranking

The median document length is 147 words in German, 169 in English, and 1,873
in law. Long administrative pages contain several independently useful
sections. Whole-document BM25 can favour a short page focused on matching
words over the requested section of a broad page. Passage retrieval is a
reasonable hypothesis to test, not a measured improvement yet.

Some top results also appear useful but have no label:

- German 36 ranks the publication-fund overview first, while the labelled
  journal-article funding conditions page is rank 20. The short query names
  the fund; its supplied description asks about covered publication fees.
- German 39 ranks a notice about obtaining used office furniture first.
  The labelled sustainability overview is rank 17 and contains a reuse
  section. The notice plausibly satisfies the short query too.
- English 47 ranks a journal-publication page first that explicitly explains
  VAT and invoice handling. The labelled 8,810-word funding glossary is
  rank 19. The second result is the central financial-accounting page.

These are manual plausibility assessments, not new relevance judgments. Each
spot-check query has only one judged document. Unjudged results must not be
treated as proven irrelevant, and the synthetic labels cannot establish
real administrative effectiveness.

## All cases outside the top ten

| Dataset/query | Judged rank | Main observation |
| --- | ---: | --- |
| German 1 | 11 | Identical text at rank 8; short SAP application guide ranks first |
| German 23 | 19 | Procurement rules vocabulary differs from query |
| German 36 | 20 | Fund overview outranks detailed fee conditions; sparse judgments |
| German 39 | 17 | Short used-furniture notice outranks long sustainability overview |
| German 40 | 21 | Software-license compound mismatch; inventory outranks procurement |
| English 16 | 81 | Consumers/consumables stemming collision and broad document |
| English 47 | 19 | Long glossary outranked by directly useful VAT/invoice pages |
| Law 1 | 30 | `Definition` occurs in court discussion, but not the defining statutory section |
| Law 2 | 36 | Specific term dropped; effective query is only HRKG |
| Law 7 | 148 | Specific term dropped plus Auto/Kraftfahrzeug mismatch |
| Law 8 | Absent | Compound dropped and metadata-only judged document |
| Law 9 | 492 | Document-type term dropped; broad statute wording survives |
| Law 15 | 96 | Both specific terms dropped; effective query is only HRKG |

The 52 top-ten cases remain in the machine-readable evidence for regression
checks. A court judgment is not necessarily irrelevant when a statute is
labelled; source type should be guided by query intent, not a universal filter.

## Priorities for Phase 4

1. **Retain long tokens in both indexing and query processing.** Test a higher
   term-length limit, rebuild the index, and evaluate all datasets. Check that
   the two HRKG-only queries become distinct and that the seven affected
   queries retain their long terms. Do not change only query processing.
2. **Keep document-ID mappings and explicit tie behaviour.** Establish a fixed
   tie convention for comparisons. Investigate duplicate-aware indexing and
   candidate diversity while preserving every submitted document ID.
3. **Test vocabulary and compound handling.** Compare conservative German
   compound processing and corpus-supported synonyms. For English, compare
   combined exact-word and stemmed matching to avoid the consumers collision.
4. **Test passages and field weighting.** Preserve document IDs when merging
   passage scores. Evaluate whether headings, titles, and relevant sections
   help broad pages. Any use of richer query fields must be confirmed against
   the actual permitted input contract; synthetic relevance narratives must
   never be used for retrieval.
5. **Consider semantic retrieval/reranking after candidate recall improves.**
   A reranker limited to the top 100 cannot recover law 7, 8, or 9 from this
   baseline candidate set. Compare quality and CPU/runtime cost separately.

Use one change at a time, keep the same evaluator conventions, and inspect
the existing 52 successful cases for regressions. No retrieval changes or
new effectiveness experiments were performed in Phase 3.

## Reproduce the analysis

Run these commands from the project root with Docker Desktop running:

```powershell
docker run --rm --network none --mount "type=bind,source=$PWD,target=/workspace" --entrypoint python3 uniagent-task1-runner:baseline /workspace/scripts/analyse-errors.py --run-name bm25-20261012-231608
docker run --rm --network none --mount "type=bind,source=$PWD,target=/workspace" --entrypoint python3 uniagent-task1-runner:baseline /workspace/scripts/analyse-terms.py --run-name bm25-20261012-231608
```

Machine-readable evidence:

- [German cases](bm25-20261012-231608/phase3/retrieval-de-spot-check.json)
- [English cases](bm25-20261012-231608/phase3/retrieval-en-spot-check.json)
- [Law cases](bm25-20261012-231608/phase3/retrieval-hessian-law-de-spot-check.json)
- Full selected document text: `runs/bm25-20261012-231608/phase3-evidence.jsonl.gz`
  (local artifact, ignored by Git).
