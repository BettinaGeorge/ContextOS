from unittest.mock import patch

from src.llm.voyage_client import MAX_TOKENS_PER_BATCH, MIN_SECONDS_BETWEEN_REQUESTS, VoyageClient


class _FakeEncoding:
    def __init__(self, n_tokens: int):
        self._n = n_tokens

    def __len__(self):
        return self._n


class _FakeEmbedResult:
    def __init__(self, embeddings: list[list[float]]):
        self.embeddings = embeddings


class _FakeVoyageSDKClient:
    """Stands in for the real voyageai.Client so batching/pacing logic can
    be tested without live credentials or a real API call."""

    def __init__(self, token_counts: list[int]):
        self._token_counts = token_counts
        self.embed_calls: list[list[str]] = []

    def tokenize(self, texts, model=None):
        assert len(texts) == len(self._token_counts)
        return [_FakeEncoding(n) for n in self._token_counts]

    def embed(self, texts, model, input_type, output_dimension):
        self.embed_calls.append(list(texts))
        return _FakeEmbedResult([[0.1] * output_dimension for _ in texts])


def _client_with_fake_sdk(token_counts: list[int]) -> tuple[VoyageClient, _FakeVoyageSDKClient]:
    client = VoyageClient()
    fake_sdk = _FakeVoyageSDKClient(token_counts)
    client._client = fake_sdk
    return client, fake_sdk


def test_embed_documents_returns_empty_list_without_calling_the_api():
    client, fake_sdk = _client_with_fake_sdk([])
    assert client.embed_documents([]) == []
    assert fake_sdk.embed_calls == []


def test_batches_split_to_stay_under_the_token_budget():
    # Two texts that together exceed MAX_TOKENS_PER_BATCH must land in
    # separate requests, not one oversized batch (T062: this is exactly the
    # shape of failure hit ingesting a real repo).
    big = MAX_TOKENS_PER_BATCH - 100
    texts = ["doc-a", "doc-b"]
    client, fake_sdk = _client_with_fake_sdk([big, big])

    with patch("src.llm.voyage_client.time.sleep") as fake_sleep:
        embeddings = client.embed_documents(texts)

    assert len(fake_sdk.embed_calls) == 2
    assert fake_sdk.embed_calls[0] == ["doc-a"]
    assert fake_sdk.embed_calls[1] == ["doc-b"]
    assert len(embeddings) == 2
    fake_sleep.assert_called_once_with(MIN_SECONDS_BETWEEN_REQUESTS)


def test_texts_under_budget_are_sent_in_a_single_batch():
    texts = ["small-a", "small-b", "small-c"]
    client, fake_sdk = _client_with_fake_sdk([10, 10, 10])

    with patch("src.llm.voyage_client.time.sleep") as fake_sleep:
        embeddings = client.embed_documents(texts)

    assert len(fake_sdk.embed_calls) == 1
    assert fake_sdk.embed_calls[0] == texts
    assert len(embeddings) == 3
    fake_sleep.assert_not_called()
