import numpy as np
import logging
import time
from functools import wraps
from threading import Lock

from backend.services.embedding_service import (
    embedding_service
)

from backend.services.dataset_service import (
    load_youtube_dataset,
    prepare_dataset
)

logger = logging.getLogger(__name__)


def _initialize_once(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._initialization_lock:
            return method(self, *args, **kwargs)
    return wrapped


# ─────────────────────────────────────────────────────
# VECTOR STORE
# ─────────────────────────────────────────────────────

class VectorStore:

    def __init__(self):

        self.df = None

        self.embeddings = None

        self.index = None
        self.faiss = None

        self.loaded = False
        self._initialization_lock = Lock()
        self.initialization_timings_ms = {}

    # ─────────────────────────────────────
    # INITIALIZE
    # ─────────────────────────────────────

    @_initialize_once
    def initialize(self):

        if self.loaded:

            return

        print(
            "Loading FAISS vector store..."
        )

        stage_started = time.perf_counter()
        self.df = prepare_dataset(
            load_youtube_dataset()
        )
        self.initialization_timings_ms["dataset_load_and_prepare"] = round((time.perf_counter() - stage_started) * 1000, 2)

        if self.df.empty:
            self.index = None
            self.embeddings = np.empty((0, 0), dtype="float32")
            self.loaded = True
            return

        try:
            import faiss
            self.faiss = faiss
        except ImportError:
            # NumPy search keeps local development usable without the optional index.
            self.faiss = None

        titles = self.df[
            "title"
        ].tolist()

        try:
            stage_started = time.perf_counter()
            vectors = embedding_service.encode_many([str(title) for title in titles])
            self.initialization_timings_ms["title_batch_encoding"] = round((time.perf_counter() - stage_started) * 1000, 2)
        except Exception as exc:
            # Cache the unavailable-index state. The recommender has a lexical
            # fallback, and repeated requests should not rebuild/retry the index.
            self.index = None
            self.embeddings = np.empty((0, 0), dtype="float32")
            self.loaded = True
            logger.warning(
                "Video category index unavailable; using general category context; exception_type=%s",
                type(exc).__name__,
            )
            return

        stage_started = time.perf_counter()
        self.embeddings = np.asarray(vectors, dtype="float32")
        if self.embeddings.ndim != 2 or not np.isfinite(self.embeddings).all():
            self.loaded = False
            raise ValueError("Video dataset produced invalid embedding vectors")

        dim = self.embeddings.shape[1]

        norms = np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        self.embeddings = np.divide(self.embeddings, norms, out=np.zeros_like(self.embeddings), where=norms != 0)
        if self.faiss is not None:
            self.index = self.faiss.IndexFlatIP(dim)
            self.index.add(self.embeddings)
        self.initialization_timings_ms["normalization_and_index_build"] = round((time.perf_counter() - stage_started) * 1000, 2)

        self.loaded = True

        print(
            "FAISS vector store ready."
        )

    # ─────────────────────────────────────
    # SEARCH TOP-K
    # ─────────────────────────────────────

    def search(
        self,
        query,
        k=5
    ):

        if not isinstance(k, int) or k <= 0:
            return []

        # lazy initialize
        if not self.loaded:

            self.initialize()

        if self.index is None and (self.embeddings is None or self.embeddings.shape[0] == 0):
            return []

        query_embedding = (
            embedding_service.encode(
                query
            )
        )

        query_embedding = np.array([
            query_embedding
        ]).astype("float32")

        embedding_dim = self.index.d if self.index is not None else self.embeddings.shape[1]
        if (query_embedding.ndim != 2 or query_embedding.shape[1] != embedding_dim
                or not np.isfinite(query_embedding).all()):
            return []

        query_norm = np.linalg.norm(query_embedding, axis=1, keepdims=True)
        query_embedding = np.divide(query_embedding, query_norm, out=np.zeros_like(query_embedding), where=query_norm != 0)
        if self.index is not None:
            k = min(k, self.index.ntotal)
            scores, indices = self.index.search(query_embedding, k)
        else:
            similarities = self.embeddings @ query_embedding[0]
            indices = np.argsort(-similarities, kind="stable")[:min(k, len(similarities))].reshape(1, -1)
            scores = similarities[indices]

        results = []

        for i in range(min(k, len(indices[0]))):

            idx = indices[0][i]

            score = scores[0][i]

            if idx < 0 or idx >= len(self.df):
                continue
            row = self.df.iloc[idx]

            results.append(

                (
                    row,
                    float(score)
                )
            )

        return results


# ─────────────────────────────────────────────────────
# GLOBAL INSTANCE
# ─────────────────────────────────────────────────────

vector_store = VectorStore()
