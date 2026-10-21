from functools import lru_cache
from threading import Lock
import time

from sklearn.metrics.pairwise import cosine_similarity


class EmbeddingService:

    def __init__(self):

        # Keep imports and app startup cheap. The model is created on first use.
        self._model = None
        self._model_load_failed = False
        self._model_lock = Lock()
        self.model_load_ms = None

    @property
    def model(self):
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    if self._model_load_failed:
                        raise RuntimeError("Embedding model is unavailable; restart the process to retry loading")
                    started = time.perf_counter()
                    try:
                        from sentence_transformers import SentenceTransformer
                        self._model = SentenceTransformer("all-MiniLM-L6-v2")
                    except Exception:
                        self._model_load_failed = True
                        self.model_load_ms = round((time.perf_counter() - started) * 1000, 2)
                        raise
                    self.model_load_ms = round((time.perf_counter() - started) * 1000, 2)
        return self._model

    # ─────────────────────────────────────
    # GET EMBEDDING
    # ─────────────────────────────────────

    @lru_cache(maxsize=1000)
    def encode(self, text):

        return self.model.encode(
            text,
            convert_to_tensor=False
        )

    def encode_many(self, texts):
        """Encode a fixed batch in one model call to avoid per-item overhead."""
        values = [str(text) for text in texts]
        if not values:
            return []
        return self.model.encode(
            values,
            convert_to_tensor=False,
            show_progress_bar=False,
        )

    # ─────────────────────────────────────
    # SIMILARITY
    # ─────────────────────────────────────

    def similarity(
        self,
        emb1,
        emb2
    ):

        score = cosine_similarity(
            [emb1],
            [emb2]
        )[0][0]

        return float(score)


embedding_service = EmbeddingService()
