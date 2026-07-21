import time

import voyageai
from voyageai.error import RateLimitError

from src.core.config import get_settings
from src.models.artifact import EMBEDDING_DIM

# Code-tuned embeddings (research.md §6) — a real quality advantage since
# this product embeds source code, not just prose.
MODEL = "voyage-code-3"

# Voyage's free tier (no payment method on file — the $0 constraint from
# ADR-002) throttles hard: 3 requests/minute, 10K tokens/minute — and TPM is
# a rolling per-minute budget across all requests, not a per-request cap
# (found the hard way: a first attempt sized batches at ~9K tokens each,
# assuming per-request, and still hit RateLimitError). At 3 RPM, each
# request needs to fit roughly TPM/RPM tokens to keep the rolling minute
# under budget, hence the much smaller per-batch cap below.
MAX_TOKENS_PER_BATCH = 3_000
MIN_SECONDS_BETWEEN_REQUESTS = 21  # ceil(60s / 3 RPM)
RATE_LIMIT_RETRY_SECONDS = 65  # a full rolling window, plus margin
MAX_RATE_LIMIT_RETRIES = 3


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
            embeddings.extend(self._embed_batch_with_retry(batch))
        return embeddings

    def _embed_batch_with_retry(self, batch: list[str]) -> list[list[float]]:
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            try:
                result = self._client.embed(
                    batch, model=MODEL, input_type="document", output_dimension=EMBEDDING_DIM
                )
                return result.embeddings
            except RateLimitError:
                if attempt == MAX_RATE_LIMIT_RETRIES:
                    raise
                time.sleep(RATE_LIMIT_RETRY_SECONDS)
        raise AssertionError("unreachable")

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
