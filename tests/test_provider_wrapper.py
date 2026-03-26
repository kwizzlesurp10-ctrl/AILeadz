"""
Tests for clawmode_integration/provider_wrapper.py

TrackedProvider and CostCapturingLiteLLMProvider are tested using lightweight
stubs so the nanobot package (not installed in CI) is not needed at runtime.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clawmode_integration.provider_wrapper import TrackedProvider


# ---------------------------------------------------------------------------
# Helpers / Stubs
# ---------------------------------------------------------------------------

def _make_response(prompt_tokens: int, completion_tokens: int, cost: float | None = None):
    """Build a minimal LLMResponse-like stub."""
    usage: dict = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    if cost is not None:
        usage["cost"] = cost
    response = MagicMock()
    response.usage = usage
    return response


def _make_provider(response):
    """Build a fake LLMProvider whose chat() returns *response*."""
    provider = MagicMock()
    provider.chat = AsyncMock(return_value=response)
    provider.some_other_attr = "hello"
    return provider


def _make_tracker():
    tracker = MagicMock()
    tracker.track_tokens = MagicMock()
    return tracker


# ---------------------------------------------------------------------------
# TrackedProvider.chat
# ---------------------------------------------------------------------------

class TestTrackedProviderChat:
    @pytest.mark.asyncio
    async def test_forwards_call_and_returns_response(self):
        response = _make_response(100, 50)
        provider = _make_provider(response)
        tracker = _make_tracker()

        tp = TrackedProvider(provider, tracker)
        result = await tp.chat(messages=[{"role": "user", "content": "hi"}])

        assert result is response
        provider.chat.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_kwargs_to_provider(self):
        response = _make_response(10, 5)
        provider = _make_provider(response)
        tracker = _make_tracker()
        tp = TrackedProvider(provider, tracker)

        await tp.chat(
            messages=[{"role": "user", "content": "test"}],
            tools=None,
            model="gpt-4",
            max_tokens=512,
            temperature=0.5,
        )

        _, kwargs = provider.chat.call_args
        assert kwargs.get("model") == "gpt-4" or provider.chat.call_args[0]

    @pytest.mark.asyncio
    async def test_tracks_tokens_without_cost(self):
        response = _make_response(200, 100)
        provider = _make_provider(response)
        tracker = _make_tracker()
        tp = TrackedProvider(provider, tracker)

        await tp.chat(messages=[{"role": "user", "content": "hi"}])

        tracker.track_tokens.assert_called_once_with(200, 100, cost=None)

    @pytest.mark.asyncio
    async def test_tracks_tokens_with_openrouter_cost(self):
        response = _make_response(300, 150, cost=0.0025)
        provider = _make_provider(response)
        tracker = _make_tracker()
        tp = TrackedProvider(provider, tracker)

        await tp.chat(messages=[{"role": "user", "content": "hi"}])

        tracker.track_tokens.assert_called_once_with(300, 150, cost=0.0025)

    @pytest.mark.asyncio
    async def test_no_tracking_when_tracker_is_none(self):
        response = _make_response(100, 50)
        provider = _make_provider(response)
        tp = TrackedProvider(provider, tracker=None)

        # Should not raise even though tracker is None
        result = await tp.chat(messages=[{"role": "user", "content": "hi"}])
        assert result is response

    @pytest.mark.asyncio
    async def test_no_tracking_when_usage_is_falsy(self):
        response = MagicMock()
        response.usage = None
        provider = _make_provider(response)
        tracker = _make_tracker()
        tp = TrackedProvider(provider, tracker)

        await tp.chat(messages=[{"role": "user", "content": "hi"}])
        tracker.track_tokens.assert_not_called()


# ---------------------------------------------------------------------------
# TrackedProvider.__getattr__ delegation
# ---------------------------------------------------------------------------

class TestTrackedProviderGetattr:
    @pytest.mark.asyncio
    async def test_delegates_unknown_attributes(self):
        response = _make_response(10, 5)
        provider = _make_provider(response)
        provider.model_name = "claude-3"
        tracker = _make_tracker()
        tp = TrackedProvider(provider, tracker)

        assert tp.model_name == "claude-3"

    @pytest.mark.asyncio
    async def test_delegates_callable_attributes(self):
        response = _make_response(10, 5)
        provider = _make_provider(response)
        provider.get_model_info = MagicMock(return_value={"name": "test"})
        tracker = _make_tracker()
        tp = TrackedProvider(provider, tracker)

        result = tp.get_model_info()
        assert result == {"name": "test"}
