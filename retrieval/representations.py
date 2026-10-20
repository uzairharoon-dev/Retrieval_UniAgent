"""Corpus-derived German compound expansion and document representations."""
import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
LINKS = ("", "s", "es", "en", "e", "er", "n")


class CompoundExpander:
    def __init__(self, document_frequencies, stopwords=()):
        stops = set(stopwords)
        self.lexicon = {word: count for word, count in document_frequencies.items()
                        if count >= 5 and 4 <= len(word) <= 64 and word not in stops}

    @classmethod
    def from_dataset(cls, dataset, stopwords=()):
        counts = Counter()
        for document in dataset.docs_iter():
            counts.update(set(WORD.findall(document.default_text().casefold())))
        return cls(counts, stopwords)

    @lru_cache(maxsize=200000)
    def parts(self, word):
        word = word.casefold()
        if not 10 <= len(word) <= 64:
            return ()
        candidates = []
        for cut in range(4, len(word) - 3):
            left = word[:cut]
            if left not in self.lexicon:
                continue
            for link in LINKS:
                if not word[cut:].startswith(link):
                    continue
                right = word[cut + len(link):]
                if right in self.lexicon:
                    score = math.log(self.lexicon[left]) + math.log(self.lexicon[right])
                    candidates.append((score, -len(link), left, right))
        if not candidates:
            return ()
        _, _, left, right = max(candidates)
        return (left, right)

    def expand(self, text):
        return WORD.sub(lambda match: " ".join((match.group(), *self.parts(match.group()))), text)


def query_text(query, use_description=False):
    """Keyword query, optionally followed by `original_query.description` when present."""
    text = query.default_text()
    original = getattr(query, "original_query", None)
    if use_description and isinstance(original, dict):
        description = original.get("description")
        if isinstance(description, str) and description.strip():
            text = f"{text} {description.strip()}"
    return text


@dataclass
class TextDocument:
    doc_id: str
    text: str

    def default_text(self):
        return self.text


class RepresentationDataset:
    def __init__(self, dataset, expander, mode, keep_texts=False):
        self.dataset, self.expander, self.mode = dataset, expander, mode
        self.keep_texts = keep_texts
        # Untransformed representation text (for rerankers), capped at 400 words.
        self.texts = {}
        self.parent_ids = {}
        # Corpus position of each source document, used to break score ties.
        self.order = {}
        self.source_documents = 0
        self.indexed_documents = 0

    def transform(self, text):
        return self.expander.expand(text) if self.expander else text

    def docs_iter(self):
        seen = {}
        for number, document in enumerate(self.dataset.docs_iter()):
            text, parent = document.default_text(), str(document.doc_id)
            self.order.setdefault(parent, number)
            self.source_documents += 1
            if self.mode == "deduplicated":
                key = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if key in seen:
                    self.parent_ids[seen[key]].append(parent)
                    continue
                seen[key] = f"d{number}"
            identifier = f"d{number}"
            self.parent_ids[identifier] = [parent]
            self.indexed_documents += 1
            words = text.split()
            if self.keep_texts:
                self.texts[identifier] = " ".join(words[:400])
            yield TextDocument(identifier, self.transform(text))
            if self.mode == "passages" and len(words) > 300:
                heading = " ".join(text.splitlines()[0].split()[:24])
                for start in range(0, len(words), 200):
                    piece = words[start:start + 300]
                    if len(piece) < 50:
                        break
                    identifier = f"d{number}p{start}"
                    self.parent_ids[identifier] = [parent]
                    self.indexed_documents += 1
                    passage = heading + "\n" + " ".join(piece)
                    if self.keep_texts:
                        self.texts[identifier] = passage
                    yield TextDocument(identifier, self.transform(passage))

    def queries_iter(self):
        for query in self.dataset.queries_iter():
            yield query


def aggregate_parents(run, parent_ids, depth=1000, order=None):
    """Max score per source document; ties keep corpus order when `order` is given (as Terrier does)."""
    rows = []
    for row in run.itertuples():
        for parent in parent_ids[str(row.docno)]:
            rows.append((str(row.qid), parent, float(row.score)))
    if not rows:
        return pd.DataFrame(columns=["qid", "docno", "score", "rank"])
    result = pd.DataFrame(rows, columns=["qid", "docno", "score"])
    result = result.groupby(["qid", "docno"], as_index=False).score.max()
    if order is not None:
        result["order"] = result.docno.map(order)
        result = result.sort_values(["qid", "score", "order"], ascending=[True, False, True]).drop(columns="order")
    else:
        result = result.sort_values(["qid", "score", "docno"], ascending=[True, False, False])
    result = result.groupby("qid", sort=False).head(depth).copy()
    result["rank"] = result.groupby("qid").cumcount()
    return result.reset_index(drop=True)
