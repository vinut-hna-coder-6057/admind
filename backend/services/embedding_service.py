from functools import lru_cache

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class EmbeddingService:

    def __init__(self):

        self.model = SentenceTransformer(
            "all-MiniLM-L6-v2"
        )

    # ─────────────────────────────────────
    # GET EMBEDDING
    # ─────────────────────────────────────

    @lru_cache(maxsize=1000)
    def encode(self, text):

        return self.model.encode(
            text,
            convert_to_tensor=False
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