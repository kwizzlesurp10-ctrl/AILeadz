"""
Pytest configuration and shared fixtures.

Sets up module-level mocks for the ``nanobot`` package (not installed in CI)
so that clawmode_integration modules can be imported without errors.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


def _install_nanobot_mocks() -> None:
    """Inject stub modules for nanobot and its sub-packages."""
    # Only mock if nanobot is genuinely missing
    if "nanobot" in sys.modules:
        return

    nanobot_submodules = [
        "nanobot",
        "nanobot.agent",
        "nanobot.agent.loop",
        "nanobot.agent.tools",
        "nanobot.agent.tools.base",
        "nanobot.bus",
        "nanobot.bus.events",
        "nanobot.bus.queue",
        "nanobot.providers",
        "nanobot.providers.base",
        "nanobot.providers.litellm_provider",
        "nanobot.session",
        "nanobot.session.manager",
    ]

    for name in nanobot_submodules:
        sys.modules[name] = MagicMock()

    # Provide real (base) classes that subclasses need to inherit from
    class _FakeBase:
        pass

    sys.modules["nanobot.providers.base"].LLMProvider = _FakeBase
    sys.modules["nanobot.providers.base"].LLMResponse = _FakeBase
    sys.modules["nanobot.providers.litellm_provider"].LiteLLMProvider = _FakeBase
    sys.modules["nanobot.agent.loop"].AgentLoop = _FakeBase
    sys.modules["nanobot.agent.tools.base"].Tool = _FakeBase


# Install mocks at import time so every test file benefits
_install_nanobot_mocks()
