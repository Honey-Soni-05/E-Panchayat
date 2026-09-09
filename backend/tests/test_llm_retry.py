"""Retrying the language model when the service is merely busy.

A free-tier flash model answers 503 "currently experiencing high demand" often
enough that one attempt is a coin toss at a busy hour, and the failure is close
to invisible: the assistant degrades politely to records-only and says so in
small text. During a live demo that reads as "the AI stopped working".

The distinction these tests protect is between busy and gone. A 503 is worth
another try; a 404 from a retired model name never recovers, and retrying it
only makes the wrong answer slower.
"""

import asyncio

import httpx
import pytest

from app.core.config import settings
from app.services import llm


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = str(self._payload)

    def json(self):
        return self._payload


_OK = {"candidates": [{"content": {"parts": [{"text": "an answer"}]}}]}
_BUSY = {"error": {"code": 503, "message": "This model is currently experiencing high demand."}}
_RETIRED = {"error": {"code": 404, "message": "This model is no longer available to new users."}}


@pytest.fixture
def instant_retries(monkeypatch):
    """Keep the retry logic, drop the waiting."""
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(llm.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key-not-used")


def _client_returning(*responses):
    """An httpx.AsyncClient stand-in that hands back the given responses in
    order, and records how many calls it saw."""
    calls = {"count": 0}
    queue = list(responses)

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *args, **kwargs):
            calls["count"] += 1
            nxt = queue.pop(0) if queue else responses[-1]
            if isinstance(nxt, Exception):
                raise nxt
            return nxt

    return _Client, calls


def test_a_busy_model_is_retried_and_the_answer_still_arrives(monkeypatch, instant_retries):
    client_cls, calls = _client_returning(
        _FakeResponse(503, _BUSY), _FakeResponse(200, _OK)
    )
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: client_cls())

    answer = asyncio.run(llm.generate("a question"))

    assert answer == "an answer"
    assert calls["count"] == 2, "the 503 was not retried"


def test_retries_are_bounded(monkeypatch, instant_retries):
    """A service that is down stays down. Three attempts, then give up and let
    the assistant fall back to the records."""
    client_cls, calls = _client_returning(_FakeResponse(503, _BUSY))
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: client_cls())

    with pytest.raises(llm.LLMUnavailable):
        asyncio.run(llm.generate("a question"))

    assert calls["count"] == len(llm.RETRY_DELAYS) + 1


def test_a_retired_model_is_not_retried(monkeypatch, instant_retries):
    """404 means the name is gone, not busy. Retrying only makes the wrong
    answer slower, and the error text is what tells you to repin."""
    client_cls, calls = _client_returning(_FakeResponse(404, _RETIRED))
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: client_cls())

    with pytest.raises(llm.LLMUnavailable) as raised:
        asyncio.run(llm.generate("a question"))

    assert calls["count"] == 1, "a retired model name was retried"
    assert "GEMINI_MODEL" in str(raised.value), "the error does not say how to fix it"


def test_a_bad_key_is_not_retried(monkeypatch, instant_retries):
    """403 is a configuration error. Retrying it wastes a demo's time."""
    client_cls, calls = _client_returning(
        _FakeResponse(403, {"error": {"code": 403, "message": "API key not valid"}})
    )
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: client_cls())

    with pytest.raises(llm.LLMUnavailable) as raised:
        asyncio.run(llm.generate("a question"))

    assert calls["count"] == 1
    assert "GEMINI_API_KEY" in str(raised.value)


def test_a_dropped_connection_is_retried(monkeypatch, instant_retries):
    """A transport failure is as transient as a 503."""
    client_cls, calls = _client_returning(
        httpx.ConnectError("connection reset"), _FakeResponse(200, _OK)
    )
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kw: client_cls())

    assert asyncio.run(llm.generate("a question")) == "an answer"
    assert calls["count"] == 2


def test_no_key_configured_never_calls_out(monkeypatch):
    """The one case that must not reach the network at all."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    def explode(**kw):  # pragma: no cover - reaching this is the failure
        raise AssertionError("called the API with no key configured")

    monkeypatch.setattr(llm.httpx, "AsyncClient", explode)

    with pytest.raises(llm.LLMUnavailable):
        asyncio.run(llm.generate("a question"))
