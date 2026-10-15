import tempfile
import unittest
from collections import Counter
from pathlib import Path

import pandas as pd

from representations import CompoundExpander, RepresentationDataset, aggregate_parents
from representation_system import run
from test_baseline import persisted_dataset


class RepresentationTest(unittest.TestCase):
    def test_compounds_keep_full_word_and_corpus_supported_parts(self):
        expander = CompoundExpander(Counter({"trennungsgeld": 8, "verordnung": 9,
                                             "universität": 12, "bibliothek": 13}))
        self.assertEqual(expander.expand("Trennungsgeldverordnung"),
                         "Trennungsgeldverordnung trennungsgeld verordnung")
        self.assertEqual(expander.parts("Universitätsbibliothek"), ("universität", "bibliothek"))
        self.assertEqual(expander.expand("Unbekannteswort"), "Unbekannteswort")

    def test_parts_require_document_frequency_not_repetition(self):
        queries = [{"qid": "q", "query": "text", "original_query": {"language": "de"}}]
        with persisted_dataset(queries, [{"doc_id": "x", "text": "Bibliothek " * 100}]) as dataset:
            self.assertNotIn("bibliothek", CompoundExpander.from_dataset(dataset).lexicon)

    def test_duplicate_ids_survive_parent_mapping(self):
        queries = [{"qid": "q", "query": "text", "original_query": {"language": "de"}}]
        docs = [{"doc_id": "a", "text": "gleich"}, {"doc_id": "b", "text": "gleich"}]
        with persisted_dataset(queries, docs) as dataset:
            view = RepresentationDataset(dataset, None, "deduplicated")
            records = list(view.docs_iter())
            self.assertEqual(len(records), 1)
            result = aggregate_parents(pd.DataFrame([{"qid": "q", "docno": records[0].doc_id, "score": 1}]), view.parent_ids)
            self.assertEqual(result.docno.tolist(), ["b", "a"])

    def test_passages_retain_full_document_and_aggregate_best_score(self):
        queries = [{"qid": "q", "query": "text", "original_query": {"language": "de"}}]
        text = "Kopf\n" + "Wort " * 650
        with persisted_dataset(queries, [{"doc_id": "original", "text": text}]) as dataset:
            view = RepresentationDataset(dataset, None, "passages")
            records = list(view.docs_iter())
            self.assertEqual(records[0].text, text)
            self.assertGreater(len(records), 1)
            raw = pd.DataFrame([{"qid": "q", "docno": doc.doc_id, "score": i + 1} for i, doc in enumerate(records)])
            result = aggregate_parents(raw, view.parent_ids)
            self.assertEqual(result.docno.tolist(), ["original"])
            self.assertEqual(result.score.tolist(), [len(records)])

    def test_live_compound_retrieval_without_qrels(self):
        queries = [{"qid": "q", "query": "Trennungsgeld Verordnung", "original_query": {"language": "de"}}]
        docs = [{"doc_id": "target", "text": "Trennungsgeldverordnung"}]
        docs += [{"doc_id": f"vocab-{i}", "text": "Trennungsgeld Verordnung"} for i in range(5)]
        with persisted_dataset(queries, docs) as dataset, tempfile.TemporaryDirectory() as directory:
            result = run(dataset, Path(directory), "compound")
            self.assertIn("target", set(result.docno))
            self.assertTrue((Path(directory) / "run.txt.gz").exists())


if __name__ == "__main__":
    unittest.main()
