"""Integration checks that German compounds survive both indexing and retrieval."""
import unittest

import pyterrier as pt

from baseline import configure_token_limit, create_index, retrieve
from test_baseline import persisted_dataset


class TokenLengthTest(unittest.TestCase):
    def test_long_german_terms_are_indexed_and_queries_remain_distinct(self):
        words = ["Reisekostenerstattung", "Wegstreckenentschädigung",
                 "Verwaltungsvorschriften", "Fahrtkostenerstattung",
                 "Personalratsmitglieder", "Trennungsgeldverordnung"]
        queries = [
            {"qid": "reimbursement", "query": "Reisekostenerstattung HRKG", "original_query": {"language": "de"}},
            {"qid": "staff", "query": "Fahrtkostenerstattung Personalratsmitglieder HRKG", "original_query": {"language": "de"}},
        ]
        docs = [{"doc_id": "reimbursement-doc", "text": "Reisekostenerstattung HRKG"},
                {"doc_id": "staff-doc", "text": "Fahrtkostenerstattung Personalratsmitglieder HRKG"},
                {"doc_id": "other-compounds", "text": " ".join(words[1:3] + words[5:])}]
        docs += [{"doc_id": f"distractor-{i}", "text": "Labor Sicherheit Anmeldung"} for i in range(4)]
        with persisted_dataset(queries, docs) as dataset:
            index = create_index(dataset, "de")
            vocabulary = {entry.getKey() for entry in index.getLexicon()}
            for word in words:
                self.assertIn(pt.TerrierStemmer.german.stem(word.lower()), vocabulary)
            run = retrieve(dataset, index, "de")
            top_docs = {qid: group.sort_values("rank").iloc[0]["docno"] for qid, group in run.groupby("qid")}
            self.assertEqual(top_docs, {"reimbursement": "reimbursement-doc", "staff": "staff-doc"})
            tokeniser = pt.TerrierTokeniser.java_tokeniser(pt.TerrierTokeniser.utf)
            self.assertEqual(len(tokeniser.getTokens(" ".join(words))), len(words))

    def test_switching_to_english_restores_original_limit(self):
        self.assertEqual(configure_token_limit("de"), 64)
        self.assertEqual(configure_token_limit("en"), 20)
        tokeniser = pt.TerrierTokeniser.java_tokeniser(pt.TerrierTokeniser.english)
        self.assertEqual(list(tokeniser.getTokens("Fahrtkostenerstattung travel")), ["travel"])


if __name__ == "__main__":
    unittest.main()
