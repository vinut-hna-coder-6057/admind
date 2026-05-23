import faiss
import numpy as np

from backend.services.embedding_service import (
    embedding_service
)

from backend.services.dataset_service import (
    load_youtube_dataset,
    prepare_dataset
)


# ─────────────────────────────────────────────────────
# VECTOR STORE
# ─────────────────────────────────────────────────────

class VectorStore:

    def __init__(self):

        self.df = None

        self.embeddings = None

        self.index = None

        self.loaded = False

    # ─────────────────────────────────────
    # INITIALIZE
    # ─────────────────────────────────────

    def initialize(self):

        if self.loaded:

            return

        print(
            "Loading FAISS vector store..."
        )

        self.df = prepare_dataset(
            load_youtube_dataset()
        )

        titles = self.df[
            "title"
        ].tolist()

        vectors = [

            embedding_service.encode(
                str(title)
            )

            for title in titles
        ]

        self.embeddings = np.array(
            vectors
        ).astype("float32")

        dim = self.embeddings.shape[1]

        self.index = faiss.IndexFlatIP(
            dim
        )

        faiss.normalize_L2(
            self.embeddings
        )

        self.index.add(
            self.embeddings
        )

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

        # lazy initialize
        if not self.loaded:

            self.initialize()

        query_embedding = (
            embedding_service.encode(
                query
            )
        )

        query_embedding = np.array([
            query_embedding
        ]).astype("float32")

        faiss.normalize_L2(
            query_embedding
        )

        scores, indices = self.index.search(

            query_embedding,

            k
        )

        results = []

        for i in range(min(k, len(indices[0]))):

            idx = indices[0][i]

            score = scores[0][i]

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