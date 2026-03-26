"""
Tests for clawmode_integration/task_classifier.py
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clawmode_integration.task_classifier import (
    TaskClassifier,
    _FALLBACK_OCCUPATION,
    _FALLBACK_WAGE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_classifier(occupations: dict | None = None) -> TaskClassifier:
    """Build a TaskClassifier with a mock provider and no file I/O."""
    provider = MagicMock()
    provider.chat = AsyncMock()
    clf = TaskClassifier.__new__(TaskClassifier)
    clf._provider = provider
    clf._occupations = occupations if occupations is not None else {}
    return clf


def _mock_provider_response(content: str) -> MagicMock:
    response = MagicMock()
    response.content = content
    return response


# ---------------------------------------------------------------------------
# _fuzzy_match
# ---------------------------------------------------------------------------

class TestFuzzyMatch:
    def test_empty_occupations_returns_fallback(self):
        clf = _make_classifier(occupations={})
        name, wage = clf._fuzzy_match("anything")
        assert name == _FALLBACK_OCCUPATION
        assert wage == _FALLBACK_WAGE

    def test_exact_match(self):
        occupations = {"Software Developer": 55.0, "Nurse": 35.0}
        clf = _make_classifier(occupations=occupations)
        name, wage = clf._fuzzy_match("Software Developer")
        assert name == "Software Developer"
        assert wage == 55.0

    def test_case_insensitive_match(self):
        occupations = {"Software Developer": 55.0}
        clf = _make_classifier(occupations=occupations)
        name, wage = clf._fuzzy_match("software developer")
        assert name == "Software Developer"
        assert wage == 55.0

    def test_substring_match(self):
        occupations = {"General and Operations Managers": 64.0, "Software Developer": 55.0}
        clf = _make_classifier(occupations=occupations)
        name, wage = clf._fuzzy_match("Operations Managers")
        assert name == "General and Operations Managers"

    def test_no_match_falls_back_to_default(self):
        occupations = {"Software Developer": 55.0, _FALLBACK_OCCUPATION: 64.0}
        clf = _make_classifier(occupations=occupations)
        name, wage = clf._fuzzy_match("Unicorn Trainer")
        assert name == _FALLBACK_OCCUPATION
        assert wage == 64.0

    def test_no_match_falls_back_to_hardcoded_wage_when_fallback_not_in_occupations(self):
        occupations = {"Software Developer": 55.0}
        clf = _make_classifier(occupations=occupations)
        name, wage = clf._fuzzy_match("Unicorn Trainer")
        assert name == _FALLBACK_OCCUPATION
        assert wage == _FALLBACK_WAGE


# ---------------------------------------------------------------------------
# _fallback_result
# ---------------------------------------------------------------------------

class TestFallbackResult:
    def test_returns_expected_structure(self):
        clf = _make_classifier(occupations={_FALLBACK_OCCUPATION: 64.0})
        result = clf._fallback_result("do something")
        assert result["occupation"] == _FALLBACK_OCCUPATION
        assert result["hours_estimate"] == 1.0
        assert result["task_value"] == round(1.0 * 64.0, 2)
        assert result["reasoning"] == "Fallback classification"

    def test_uses_hardcoded_wage_when_occupation_missing(self):
        clf = _make_classifier(occupations={})
        result = clf._fallback_result("do something")
        assert result["hourly_wage"] == _FALLBACK_WAGE


# ---------------------------------------------------------------------------
# classify — no occupations loaded
# ---------------------------------------------------------------------------

class TestClassifyNoOccupations:
    @pytest.mark.asyncio
    async def test_returns_fallback_when_no_occupations(self):
        clf = _make_classifier(occupations={})
        result = await clf.classify("Write a marketing email")
        assert result["occupation"] == _FALLBACK_OCCUPATION


# ---------------------------------------------------------------------------
# classify — successful LLM path
# ---------------------------------------------------------------------------

class TestClassifySuccess:
    @pytest.mark.asyncio
    async def test_successful_classification(self):
        occupations = {
            "Marketing Specialists": 32.0,
            _FALLBACK_OCCUPATION: 64.0,
        }
        clf = _make_classifier(occupations=occupations)
        llm_json = json.dumps({
            "occupation": "Marketing Specialists",
            "hours_estimate": 2.0,
            "reasoning": "Marketing task",
        })
        clf._provider.chat.return_value = _mock_provider_response(llm_json)

        result = await clf.classify("Write a marketing email")
        assert result["occupation"] == "Marketing Specialists"
        assert result["hourly_wage"] == 32.0
        assert result["hours_estimate"] == 2.0
        assert result["task_value"] == round(2.0 * 32.0, 2)
        assert result["reasoning"] == "Marketing task"

    @pytest.mark.asyncio
    async def test_hours_clamped_to_min(self):
        occupations = {"Writer": 25.0}
        clf = _make_classifier(occupations=occupations)
        llm_json = json.dumps({
            "occupation": "Writer",
            "hours_estimate": 0.0,  # below 0.25 minimum
            "reasoning": "Fast task",
        })
        clf._provider.chat.return_value = _mock_provider_response(llm_json)
        result = await clf.classify("Write one sentence")
        assert result["hours_estimate"] == 0.25

    @pytest.mark.asyncio
    async def test_hours_clamped_to_max(self):
        occupations = {"Software Developer": 55.0}
        clf = _make_classifier(occupations=occupations)
        llm_json = json.dumps({
            "occupation": "Software Developer",
            "hours_estimate": 100.0,  # above 40 maximum
            "reasoning": "Very long project",
        })
        clf._provider.chat.return_value = _mock_provider_response(llm_json)
        result = await clf.classify("Rewrite the entire OS")
        assert result["hours_estimate"] == 40.0

    @pytest.mark.asyncio
    async def test_markdown_fences_stripped(self):
        occupations = {"Writer": 25.0}
        clf = _make_classifier(occupations=occupations)
        raw = '```json\n{"occupation": "Writer", "hours_estimate": 1.5, "reasoning": "ok"}\n```'
        clf._provider.chat.return_value = _mock_provider_response(raw)
        result = await clf.classify("Write a report")
        assert result["occupation"] == "Writer"

    @pytest.mark.asyncio
    async def test_fallback_on_json_parse_error(self):
        occupations = {"Writer": 25.0, _FALLBACK_OCCUPATION: 64.0}
        clf = _make_classifier(occupations=occupations)
        clf._provider.chat.return_value = _mock_provider_response("not valid json")
        result = await clf.classify("Write something")
        assert result["occupation"] == _FALLBACK_OCCUPATION

    @pytest.mark.asyncio
    async def test_fallback_on_provider_exception(self):
        occupations = {"Writer": 25.0, _FALLBACK_OCCUPATION: 64.0}
        clf = _make_classifier(occupations=occupations)
        clf._provider.chat.side_effect = RuntimeError("network error")
        result = await clf.classify("Write something")
        assert result["occupation"] == _FALLBACK_OCCUPATION

    @pytest.mark.asyncio
    async def test_unknown_occupation_falls_back_via_fuzzy(self):
        occupations = {
            "General and Operations Managers": 64.0,
            "Software Developer": 55.0,
        }
        clf = _make_classifier(occupations=occupations)
        llm_json = json.dumps({
            "occupation": "Completely Unknown Job",
            "hours_estimate": 2.0,
            "reasoning": "n/a",
        })
        clf._provider.chat.return_value = _mock_provider_response(llm_json)
        result = await clf.classify("Do something weird")
        # Should fall back to the default occupation via _fuzzy_match
        assert result["occupation"] == "General and Operations Managers"


# ---------------------------------------------------------------------------
# _load_occupations — file I/O paths
# ---------------------------------------------------------------------------

class TestLoadOccupations:
    def test_loads_valid_mapping(self, tmp_path):
        data = [
            {"gdpval_occupation": "Accountants and Auditors", "hourly_wage": 38.5},
            {"gdpval_occupation": "Architects", "hourly_wage": 42.0},
        ]
        mapping_file = tmp_path / "occupation_to_wage_mapping.json"
        mapping_file.write_text(json.dumps(data))

        provider = MagicMock()
        clf = TaskClassifier.__new__(TaskClassifier)
        clf._provider = provider
        clf._occupations = {}

        with patch(
            "clawmode_integration.task_classifier._WAGE_MAPPING_PATH",
            mapping_file,
        ):
            clf._load_occupations()

        assert clf._occupations["Accountants and Auditors"] == 38.5
        assert clf._occupations["Architects"] == 42.0

    def test_skips_entries_without_name_or_wage(self, tmp_path):
        data = [
            {"gdpval_occupation": "Accountants and Auditors", "hourly_wage": 38.5},
            {"gdpval_occupation": "", "hourly_wage": 20.0},  # empty name
            {"gdpval_occupation": "Architects"},              # missing wage
        ]
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text(json.dumps(data))

        provider = MagicMock()
        clf = TaskClassifier.__new__(TaskClassifier)
        clf._provider = provider
        clf._occupations = {}

        with patch(
            "clawmode_integration.task_classifier._WAGE_MAPPING_PATH",
            mapping_file,
        ):
            clf._load_occupations()

        assert len(clf._occupations) == 1
        assert "Accountants and Auditors" in clf._occupations

    def test_missing_file_leaves_occupations_empty(self, tmp_path):
        missing = tmp_path / "no_mapping.json"
        provider = MagicMock()
        clf = TaskClassifier.__new__(TaskClassifier)
        clf._provider = provider
        clf._occupations = {}

        with patch(
            "clawmode_integration.task_classifier._WAGE_MAPPING_PATH",
            missing,
        ):
            clf._load_occupations()

        assert clf._occupations == {}
