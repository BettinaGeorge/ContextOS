import time

import voyageai

from src.core.config import get_settings
from src.models.artifact import EMBEDDING_DIM

# Code-tuned embeddings (research.md §6) — a real quality advantage since
# this product embeds source code, not just prose.
MODEL = "voyage-code-3"

# Voyage's free tier (no payment method on file — the $0 constraint from
# ADR-002) throttles hard: 3 requests/minute, 10K tokens/minute. Found by
# running ingestion against a real repo (T061/T062) — a single batch call
# with a whole repo's files blew straight through the token cap. Batches are
# built to stay under MAX_TOKENS_PER_BATCH with a safety margin (Voyage's
# real cap, not a contractual guarantee), and consecutive batches are paced
# by MIN_SECONDS_BETWEEN_REQUESTS to stay under the request cap.
MAX_TOKENS_PER_BATCH = 9_000
MIN_SECONDS_BETWEEN_REQUESTS = 21  # ceil(60s / 3 RPM)


class VoyageClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = voyageai.Client(api_key=settings.voyage_api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings: list[list[float]] = []
        for i, batch in enumerate(self._batch_by_token_budget(texts)):
            if i > 0:
                time.sleep(MIN_SECONDS_BETWEEN_REQUESTS)
            result = self._client.embed(
                batch, model=MODEL, input_type="document", output_dimension=EMBEDDING_DIM
            )
            embeddings.extend(result.embeddings)
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        result = self._client.embed(
            [text], model=MODEL, input_type="query", output_dimension=EMBEDDING_DIM
        )
        return result.embeddings[0]

    def _batch_by_token_budget(self, texts: list[str]) -> list[list[str]]:
        """Greedily groups texts so each batch's real token count (Voyage's
        own tokenizer, not an estimate) stays under MAX_TOKENS_PER_BATCH. A
        single text that alone exceeds the budget is still sent alone as its
        own batch — rare in practice (chunk_source_file already bounds
        source-file chunk size) and better to surface as a real API error
        than to silently truncate content out of what gets embedded."""
        token_counts = [len(t) for t in self._client.tokenize(texts, model=MODEL)]
        batches: list[list[str]] = []
        current: list[str] = []
        current_tokens = 0
        for text, tokens in zip(texts, token_counts, strict=True):
            if current and current_tokens + tokens > MAX_TOKENS_PER_BATCH:
                batches.append(current)
                current, current_tokens = [], 0
            current.append(text)
            current_tokens += tokens
        if current:
            batches.append(current)
        return batches
