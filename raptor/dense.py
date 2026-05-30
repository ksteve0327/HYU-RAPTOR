import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np


@dataclass
class DenseHit:
    rank: int
    doc_id: str
    score: float
    text: str
    metadata: Dict
    contributions: List[Dict]


@dataclass
class DenseResult:
    method: str
    query: str
    hits: List[DenseHit]
    context: str
    elapsed_seconds: float


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    if matrix.size == 0:
        return matrix
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class DenseRetriever:
    """Generic dense retriever backed by the experiment embedding model."""

    def __init__(self, documents, embedding_model, method="dense"):
        self.documents = list(documents)
        self.embedding_model = embedding_model
        self.method = method
        self.context_embeddings = self._encode_documents()

    def _encode_documents(self):
        vectors = [
            self.embedding_model.create_embedding(document["text"])
            for document in self.documents
        ]
        if not vectors:
            return np.empty((0, 0), dtype=np.float32)
        return _normalize_rows(np.array(vectors, dtype=np.float32))

    def _encode_query(self, query):
        vector = np.array(
            [self.embedding_model.create_embedding(query)],
            dtype=np.float32,
        )
        return _normalize_rows(vector)[0]

    def search(
        self,
        query,
        top_k=10,
        max_context_tokens: Optional[int] = None,
        tokenizer=None,
    ):
        started_at = time.time()
        query_embedding = self._encode_query(query)
        if self.context_embeddings.size == 0:
            scores = np.array([], dtype=np.float32)
        else:
            scores = self.context_embeddings @ query_embedding
        order = sorted(range(len(scores)), key=lambda index: (-float(scores[index]), index))

        hits = []
        context_parts = []
        total_tokens = 0
        for index in order:
            document = self.documents[index]
            text = document["text"]
            token_count = len(tokenizer.encode(text)) if tokenizer else len(str(text).split())
            if max_context_tokens is not None and total_tokens + token_count > max_context_tokens:
                continue
            hits.append(
                DenseHit(
                    rank=len(hits) + 1,
                    doc_id=document["id"],
                    score=float(scores[index]),
                    text=text,
                    metadata=document.get("metadata", {}),
                    contributions=[],
                )
            )
            context_parts.append(text)
            total_tokens += token_count
            if len(hits) >= top_k:
                break

        return DenseResult(
            method=self.method,
            query=query,
            hits=hits,
            context="\n\n".join(context_parts),
            elapsed_seconds=time.time() - started_at,
        )
