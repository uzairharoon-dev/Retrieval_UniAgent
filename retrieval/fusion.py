"""Equal-weight reciprocal-rank fusion with fixed k=60 and deterministic ties."""
import math
from collections import defaultdict

import pandas as pd

RRF_K = 60


def fuse_runs(short_run: pd.DataFrame, long_run: pd.DataFrame, depth: int = 1000) -> pd.DataFrame:
    if depth < 1:
        raise ValueError("depth must be positive")
    contributions = defaultdict(lambda: defaultdict(list))
    for run in (short_run, long_run):
        if not {"qid", "docno", "score"}.issubset(run.columns):
            raise ValueError("Each run requires qid, docno, and score columns")
        run = run[["qid", "docno", "score"]].copy()
        run["qid"], run["docno"] = run["qid"].astype(str), run["docno"].astype(str)
        if run.duplicated(["qid", "docno"]).any():
            raise ValueError("Duplicate query/document pair in a component run")
        if not all(math.isfinite(float(score)) for score in run["score"]):
            raise ValueError("Component scores must be finite")
        for qid, group in run.groupby("qid"):
            ordered = group.sort_values(["score", "docno"], ascending=[False, False])
            for rank, docno in enumerate(ordered["docno"], 1):
                contributions[qid][docno].append(1.0 / (RRF_K + rank))
    records = []
    for qid in sorted(contributions):
        scores = {docno: math.fsum(values) for docno, values in contributions[qid].items()}
        ordered = sorted(scores, key=lambda docno: (scores[docno], docno), reverse=True)[:depth]
        records.extend({"qid": qid, "docno": docno, "rank": rank, "score": scores[docno]}
                       for rank, docno in enumerate(ordered))
    return pd.DataFrame(records, columns=["qid", "docno", "rank", "score"])
