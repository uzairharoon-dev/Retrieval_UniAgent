import tempfile
import json
import unittest
from pathlib import Path

import pandas as pd

from fusion import fuse_runs
from fusion_system import run_fusion


def frame(rows):
    return pd.DataFrame(rows, columns=["qid", "docno", "score"])


class FusionTest(unittest.TestCase):
    def test_consensus_and_missing_documents(self):
        result = fuse_runs(frame([("q", "a", 9), ("q", "b", 8)]),
                           frame([("q", "b", 100), ("q", "c", 90)]))
        self.assertEqual(result.docno.tolist(), ["b", "a", "c"])
        self.assertAlmostEqual(result.iloc[0].score, 1 / 62 + 1 / 61)
        self.assertEqual(result["rank"].tolist(), [0, 1, 2])

    def test_equal_score_ties_ignore_input_order_and_component_order(self):
        first = frame([("q", "a", 1), ("q", "b", 1)])
        second = frame([("q", "b", 2), ("q", "c", 2)])
        pd.testing.assert_frame_equal(fuse_runs(first, second),
                                      fuse_runs(second.iloc[::-1], first.iloc[::-1]))
        self.assertEqual(fuse_runs(first, first).docno.tolist(), ["b", "a"])

    def test_duplicate_component_document_is_rejected(self):
        duplicate = frame([("q", "a", 1), ("q", "a", 1)])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            fuse_runs(duplicate, frame([]))

    def test_live_indexes_and_saved_components_reproduce_fusion(self):
        queries = [{"qid": "q", "query": "Reisekostenerstattung HRKG", "original_query": {"language": "de"}}]
        docs = [{"doc_id": "right", "text": "Reisekostenerstattung HRKG"},
                {"doc_id": "broad", "text": "HRKG HRKG"}]
        docs += [{"doc_id": f"noise-{i}", "text": "Labor Sicherheit Anmeldung"} for i in range(4)]
        with tempfile.TemporaryDirectory() as directory:
            import pyterrier as pt
            dataset = Path(directory) / "inputs"
            dataset.mkdir()
            (dataset / "queries.jsonl").write_text("".join(json.dumps(q) + "\n" for q in queries), encoding="utf-8")
            (dataset / "documents.jsonl").write_text("".join(json.dumps(d) + "\n" for d in docs), encoding="utf-8")
            output = Path(directory) / "output"
            actual = run_fusion(str(dataset), output)
            short = pt.io.read_results(output / "components/short/run.txt.gz")
            long = pt.io.read_results(output / "components/long/run.txt.gz")
            self.assertEqual(short.sort_values("rank").iloc[0].docno, "broad")
            self.assertEqual(long.sort_values("rank").iloc[0].docno, "right")
            expected = fuse_runs(short, long)
            pd.testing.assert_frame_equal(actual, expected)
            self.assertTrue((output / "run.txt.gz").exists())


if __name__ == "__main__":
    unittest.main()
