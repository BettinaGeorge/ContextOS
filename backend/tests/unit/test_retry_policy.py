"""FR-013 to FR-015 (specs/003): how many attempts, how long between them, and which
failures are not worth retrying."""

import httpx

from src.connectors.base import ConnectorAuthError
from src.core.job_worker import BACKOFF_SECONDS, MAX_ATTEMPTS, is_permanent_failure


def test_backoff_schedule_and_attempt_limit():
    assert BACKOFF_SECONDS == (30, 120)
    assert MAX_ATTEMPTS == 3


def test_each_delay_is_longer_than_the_one_before():
    assert all(
        later > earlier
        for earlier, later in zip(BACKOFF_SECONDS, BACKOFF_SECONDS[1:], strict=False)
    )


def test_there_is_a_delay_for_every_retry():
    assert len(BACKOFF_SECONDS) == MAX_ATTEMPTS - 1


def test_credential_rejection_is_permanent():
    assert is_permanent_failure(ConnectorAuthError("token rejected")) is True


def test_value_error_is_permanent():
    assert is_permanent_failure(ValueError("connector missing")) is True


def test_other_errors_are_transient():
    assert is_permanent_failure(TimeoutError("timed out")) is False
    assert is_permanent_failure(RuntimeError("GitHub API is down")) is False
    assert is_permanent_failure(httpx.ConnectError("connection refused")) is False
