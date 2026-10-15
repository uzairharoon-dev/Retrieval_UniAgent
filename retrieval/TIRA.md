# UniAgent 2026 Task 1: passage BM25

Selected after development evaluation and exact fresh repeats on all three
organizer spot-check corpora. BM25 uses whole documents and 300-word passages
at stride 200, with maximum-score aggregation back to original document IDs.
German compounds retain their full term and add corpus-derived components;
the vocabulary uses document text only. No LLM, external API or relevance
labels are used by retrieval. No agent tools are used, so event traces are
not required; index/retrieval resource metadata is saved separately.

The implementation adapts the organizers' PyTerrier baseline from
https://github.com/uniagent-webis-de/uniagent-code at revision
`aaba38d87063016fa2b6b76fd43dc8b077ba7648`.
The standalone image pins the official base-image digest and runs all 31
tests during its build. Each input directory must contain `documents.jsonl.gz`
and `queries.jsonl`; queries must have one supported language, `de` or `en`.
The output contains `run.txt.gz` in TREC format and resource/configuration files.

```sh
docker build --platform linux/amd64 -t uniagent-passages .
docker run --rm --network none -v INPUT:/input:ro -v OUTPUT:/output \
  uniagent-passages --dataset /input --output /output
tira-cli code-submission --path . --task uniagent-2026 \
  --dataset retrieval-de-spot-check-20260816-training \
  --platform linux/amd64 --build-args=--provenance=false \
  --command 'python3 /app/representation_system.py --mode passages --dataset $inputDataset --output $outputDir' \
  --dry-run
```

Remove `--dry-run` to upload after authentication. Uploading code and running
it on TIRA are separate operations. The local snapshot's origin points to
the participant's local workspace; TIRA also embeds the tracked source archive.
No public Git repository has been created or pushed.

The selected method has the highest development mean under a common canonical
tie convention. It regresses one German Recall@100 case; local TIRA file-order
tie handling ranks the long-token control higher on its mean. Synthetic,
single-positive development judgments do not establish private-test quality.
