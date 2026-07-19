import voyageai

from src.core.config import get_settings
from src.models.artifact import EMBEDDING_DIM

# Code-tuned embeddings (research.md §6) — a real quality advantage since
# this product embeds source code, not just prose.
MODEL = "voyage-code-3"


class VoyageClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = voyageai.Client(api_key=settings.voyage_api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        result = self._client.embed(
            texts, model=MODEL, input_type="document", output_dimension=EMBEDDING_DIM
        )
        return result.embeddings

    def embed_query(self, text: str) -> list[float]:
        result = self._client.embed(
            [text], model=MODEL, input_type="query", output_dimension=EMBEDDING_DIM
        )
        return result.embeddings[0]
