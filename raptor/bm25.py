import math
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List


TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣][0-9A-Za-z가-힣_\-./+]*")


def tokenize(text: str) -> List[str]:
    return TOKEN_PATTERN.findall((text or "").lower())


@dataclass
class BM25Hit:
    rank: int
    doc_id: str
    score: float
    text: str
    metadata: Dict
    contributions: List[Dict]


@dataclass
class BM25Result:
    method: str
    query: str
    hits: List[BM25Hit]
    context: str
    elapsed_seconds: float


class BM25Retriever:
    def __init__(self, documents, k1=1.5, b=0.75, method="bm25"):
        self.documents = list(documents)
        self.k1 = k1
        self.b = b
        self.method = method
        self.doc_tokens = [tokenize(document["text"]) for document in self.documents]
        self.doc_term_counts = [Counter(tokens) for tokens in self.doc_tokens]
        self.doc_lengths = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_length = (
            sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0
        )
        self.document_frequency = Counter()

        for counts in self.doc_term_counts:
            self.document_frequency.update(counts.keys())

        self.idf = {}
        total_docs = len(self.documents)
        for term, frequency in self.document_frequency.items():
            self.idf[term] = math.log(
                1 + (total_docs - frequency + 0.5) / (frequency + 0.5)
            )

    def _term_score(self, term, doc_index):
        term_frequency = self.doc_term_counts[doc_index].get(term, 0)
        if term_frequency == 0:
            return 0.0
        doc_length = self.doc_lengths[doc_index]
        denominator = term_frequency + self.k1 * (
            1 - self.b + self.b * doc_length / max(self.avg_doc_length, 1)
        )
        return self.idf.get(term, 0.0) * (
            term_frequency * (self.k1 + 1) / denominator
        )

    def _score(self, query_terms, doc_index):
        return sum(self._term_score(term, doc_index) for term in query_terms)

    def _contributions(self, query_terms, doc_index, limit=8):
        rows = []
        for term in sorted(set(query_terms)):
            score = self._term_score(term, doc_index)
            if score <= 0:
                continue
            rows.append(
                {
                    "term": term,
                    "term_frequency": self.doc_term_counts[doc_index].get(term, 0),
                    "document_frequency": self.document_frequency.get(term, 0),
                    "idf": self.idf.get(term, 0.0),
                    "score": score,
                }
            )
        rows.sort(key=lambda row: row["score"], reverse=True)
        return rows[:limit]

    def search(self, query, top_k=10, max_context_tokens=None, tokenizer=None):
        started_at = time.time()
        query_terms = tokenize(query)
        scored = [
            (self._score(query_terms, index), index)
            for index in range(len(self.documents))
        ]
        scored.sort(key=lambda item: (-item[0], item[1]))

        hits = []
        context_parts = []
        total_tokens = 0
        for score, index in scored:
            if score <= 0 and hits:
                break
            document = self.documents[index]
            text = document["text"]
            token_count = len(tokenizer.encode(text)) if tokenizer else len(tokenize(text))
            if max_context_tokens is not None and total_tokens + token_count > max_context_tokens:
                continue
            hits.append(
                BM25Hit(
                    rank=len(hits) + 1,
                    doc_id=document["id"],
                    score=score,
                    text=text,
                    metadata=document.get("metadata", {}),
                    contributions=self._contributions(query_terms, index),
                )
            )
            context_parts.append(text)
            total_tokens += token_count
            if len(hits) >= top_k:
                break

        return BM25Result(
            method=self.method,
            query=query,
            hits=hits,
            context="\n\n".join(context_parts),
            elapsed_seconds=time.time() - started_at,
        )
