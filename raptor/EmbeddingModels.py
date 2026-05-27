import logging
import hashlib
import math
import os
from abc import ABC, abstractmethod

os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("USE_TF", "0")

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - depends on local environment
    OpenAI = None

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - depends on local environment
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_IMPORT_ERROR = exc

from tenacity import retry, stop_after_attempt, wait_random_exponential

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)


class BaseEmbeddingModel(ABC):
    @abstractmethod
    def create_embedding(self, text):
        pass


class OpenAIEmbeddingModel(BaseEmbeddingModel):
    def __init__(self, model="text-embedding-ada-002"):
        if OpenAI is None:
            raise ImportError(
                "openai is required for OpenAIEmbeddingModel. Install requirements.txt or use a local embedding model."
            )
        self.client = OpenAI()
        self.model = model

    @retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
    def create_embedding(self, text):
        text = text.replace("\n", " ")
        return (
            self.client.embeddings.create(input=[text], model=self.model)
            .data[0]
            .embedding
        )


class SBertEmbeddingModel(BaseEmbeddingModel):
    def __init__(self, model_name="sentence-transformers/multi-qa-mpnet-base-cos-v1"):
        if SentenceTransformer is None:
            raise ImportError(
                "sentence-transformers is required for SBertEmbeddingModel. "
                f"Install/fix requirements before running the full experiment. Original error: {SENTENCE_TRANSFORMERS_IMPORT_ERROR}"
            )
        self.model = SentenceTransformer(model_name)

    def create_embedding(self, text):
        return self.model.encode(text, show_progress_bar=False)


class MiniLMKoreanEmbeddingModel(SBertEmbeddingModel):
    def __init__(
        self,
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ):
        super().__init__(model_name=model_name)


class HashEmbeddingModel(BaseEmbeddingModel):
    """
    Deterministic dependency-light embedding for tests and dry runs.
    Do not use this for the final patent experiment.
    """

    def __init__(self, dimensions=64):
        self.dimensions = dimensions

    def create_embedding(self, text):
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]
