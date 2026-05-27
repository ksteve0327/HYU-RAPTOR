import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from .EmbeddingModels import HashEmbeddingModel


@dataclass
class DPRHit:
    rank: int
    doc_id: str
    score: float
    text: str
    metadata: Dict
    contributions: List[Dict]


@dataclass
class DPRResult:
    method: str
    query: str
    hits: List[DPRHit]
    context: str
    elapsed_seconds: float


class DPRRetriever:
    def __init__(
        self,
        documents,
        question_model_name="facebook/dpr-question_encoder-multiset-base",
        context_model_name="facebook/dpr-ctx_encoder-multiset-base",
        backend="hf",
        method="dpr_leaf",
        batch_size=16,
    ):
        self.documents = list(documents)
        self.question_model_name = question_model_name
        self.context_model_name = context_model_name
        self.backend = backend
        self.method = method
        self.batch_size = batch_size

        if backend == "hash":
            self.embedding_model = HashEmbeddingModel(dimensions=96)
            self.context_embeddings = np.array(
                [self.embedding_model.create_embedding(document["text"]) for document in self.documents],
                dtype=np.float32,
            )
        elif backend == "hf":
            self._load_hf_models()
            self.context_embeddings = self._encode_contexts(
                [document["text"] for document in self.documents]
            )
        else:
            raise ValueError("backend must be 'hf' or 'hash'")

    def _load_hf_models(self):
        try:
            import torch
            from transformers import (
                DPRContextEncoder,
                DPRContextEncoderTokenizer,
                DPRQuestionEncoder,
                DPRQuestionEncoderTokenizer,
            )
        except Exception as exc:  # pragma: no cover - depends on local environment
            raise ImportError(
                "torch and transformers are required for DPRRetriever backend='hf'. "
                "Use --dpr-backend hash for smoke tests."
            ) from exc

        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.question_tokenizer = DPRQuestionEncoderTokenizer.from_pretrained(
            self.question_model_name
        )
        self.question_encoder = DPRQuestionEncoder.from_pretrained(
            self.question_model_name
        ).to(self.device)
        self.context_tokenizer = DPRContextEncoderTokenizer.from_pretrained(
            self.context_model_name
        )
        self.context_encoder = DPRContextEncoder.from_pretrained(
            self.context_model_name
        ).to(self.device)
        self.question_encoder.eval()
        self.context_encoder.eval()

    def _encode_hf_batches(self, texts, tokenizer, encoder):
        vectors = []
        with self.torch.no_grad():
            for start in range(0, len(texts), self.batch_size):
                batch = texts[start : start + self.batch_size]
                encoded = tokenizer(
                    batch,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=512,
                )
                encoded = {key: value.to(self.device) for key, value in encoded.items()}
                output = encoder(**encoded)
                pooled = output.pooler_output.detach().cpu().numpy()
                vectors.append(pooled)
        if not vectors:
            return np.empty((0, 0), dtype=np.float32)
        return np.vstack(vectors).astype(np.float32)

    def _encode_contexts(self, texts):
        return self._encode_hf_batches(texts, self.context_tokenizer, self.context_encoder)

    def _encode_query(self, query):
        if self.backend == "hash":
            return np.array(self.embedding_model.create_embedding(query), dtype=np.float32)
        return self._encode_hf_batches([query], self.question_tokenizer, self.question_encoder)[0]

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
                DPRHit(
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

        return DPRResult(
            method=self.method,
            query=query,
            hits=hits,
            context="\n\n".join(context_parts),
            elapsed_seconds=time.time() - started_at,
        )
