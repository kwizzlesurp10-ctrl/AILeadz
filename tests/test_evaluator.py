"""
Tests for livebench/work/evaluator.py

WorkEvaluator is tested using mocks for the LLMEvaluator dependency so
no real OpenAI API calls are made during testing.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from livebench.work.evaluator import WorkEvaluator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_evaluator(tmp_path, max_payment: float = 50.0):
    """Create a WorkEvaluator with a mocked LLMEvaluator."""
    with patch("livebench.work.evaluator.WorkEvaluator.__init__", lambda self, **kw: None):
        evaluator = WorkEvaluator.__new__(WorkEvaluator)

    evaluator.max_payment = max_payment
    evaluator.data_path = str(tmp_path)
    evaluator.use_llm_evaluation = True
    evaluator.llm_evaluator = MagicMock()
    return evaluator


def _make_task(task_id: str = "task-001", max_payment: float = 50.0) -> dict:
    return {"task_id": task_id, "max_payment": max_payment, "category": "writing"}


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestWorkEvaluatorConstruction:
    def test_raises_when_llm_evaluation_disabled(self, tmp_path):
        # ValueError is raised before LLMEvaluator is ever imported
        with pytest.raises(ValueError, match="use_llm_evaluation must be True"):
            WorkEvaluator(
                max_payment=50.0,
                data_path=str(tmp_path),
                use_llm_evaluation=False,
            )

    def test_str_representation(self, tmp_path):
        # Use the _make_evaluator helper which bypasses LLMEvaluator entirely
        evaluator = _make_evaluator(tmp_path, max_payment=100.0)
        assert "100" in str(evaluator)


# ---------------------------------------------------------------------------
# evaluate_artifact — edge cases (no LLM call needed)
# ---------------------------------------------------------------------------

class TestEvaluateArtifactEdgeCases:
    def test_missing_artifact_returns_not_accepted(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        task = _make_task()
        accepted, payment, feedback, score = evaluator.evaluate_artifact(
            signature="agent",
            task=task,
            artifact_path="/non/existent/file.txt",
        )
        assert accepted is False
        assert payment == 0.0
        assert score == 0.0
        assert "not found" in feedback.lower()

    def test_empty_artifact_returns_not_accepted(self, tmp_path):
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")
        evaluator = _make_evaluator(tmp_path)
        task = _make_task()
        accepted, payment, feedback, score = evaluator.evaluate_artifact(
            signature="agent",
            task=task,
            artifact_path=str(empty_file),
        )
        assert accepted is False
        assert payment == 0.0
        assert "empty" in feedback.lower()

    def test_accepts_list_of_artifact_paths(self, tmp_path):
        """When a list of paths is provided, at least one existing file passes."""
        good_file = tmp_path / "report.txt"
        good_file.write_text("This is a report.")
        evaluator = _make_evaluator(tmp_path)
        # LLM evaluator returns a good score
        evaluator.llm_evaluator.evaluate_artifact.return_value = (0.9, "Excellent work", 45.0)
        task = _make_task()
        accepted, payment, feedback, score = evaluator.evaluate_artifact(
            signature="agent",
            task=task,
            artifact_path=[str(good_file)],
        )
        assert accepted is True
        assert payment == pytest.approx(45.0)

    def test_all_missing_paths_returns_not_accepted(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        task = _make_task()
        accepted, payment, feedback, score = evaluator.evaluate_artifact(
            signature="agent",
            task=task,
            artifact_path=["/no/file1.txt", "/no/file2.txt"],
        )
        assert accepted is False
        assert payment == 0.0


# ---------------------------------------------------------------------------
# evaluate_artifact — LLM evaluation path
# ---------------------------------------------------------------------------

class TestEvaluateArtifactLLM:
    def test_successful_llm_evaluation(self, tmp_path):
        artifact = tmp_path / "report.docx"
        artifact.write_bytes(b"binary report content")
        evaluator = _make_evaluator(tmp_path, max_payment=100.0)
        evaluator.llm_evaluator.evaluate_artifact.return_value = (0.85, "Good report", 85.0)
        task = _make_task(max_payment=100.0)

        accepted, payment, feedback, score = evaluator.evaluate_artifact(
            signature="agent",
            task=task,
            artifact_path=str(artifact),
            description="I wrote a detailed market analysis",
        )

        assert accepted is True
        assert payment == pytest.approx(85.0)
        assert score == pytest.approx(0.85)
        assert feedback == "Good report"

    def test_zero_payment_means_not_accepted(self, tmp_path):
        artifact = tmp_path / "bad.txt"
        artifact.write_text("Low quality content")
        evaluator = _make_evaluator(tmp_path)
        evaluator.llm_evaluator.evaluate_artifact.return_value = (0.2, "Poor quality", 0.0)
        task = _make_task()

        accepted, payment, feedback, score = evaluator.evaluate_artifact(
            signature="agent",
            task=task,
            artifact_path=str(artifact),
        )

        assert accepted is False
        assert payment == 0.0

    def test_task_max_payment_takes_precedence(self, tmp_path):
        artifact = tmp_path / "doc.txt"
        artifact.write_text("content")
        evaluator = _make_evaluator(tmp_path, max_payment=50.0)
        evaluator.llm_evaluator.evaluate_artifact.return_value = (1.0, "Perfect", 75.0)
        task = _make_task(max_payment=75.0)

        evaluator.evaluate_artifact(
            signature="agent",
            task=task,
            artifact_path=str(artifact),
        )

        # LLMEvaluator should have been called with task-specific max_payment=75.0
        call_kwargs = evaluator.llm_evaluator.evaluate_artifact.call_args[1]
        assert call_kwargs.get("max_payment") == 75.0 or (
            evaluator.llm_evaluator.evaluate_artifact.call_args[0][3] == 75.0
        )


# ---------------------------------------------------------------------------
# _log_evaluation
# ---------------------------------------------------------------------------

class TestLogEvaluation:
    def test_creates_log_file(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        evaluator._log_evaluation(
            signature="agent",
            task_id="task-log-01",
            artifact_path="/tmp/artifact.txt",
            payment=30.0,
            feedback="Looks good",
            evaluation_score=0.75,
        )
        log_file = tmp_path / "work" / "evaluations.jsonl"
        assert log_file.exists()
        record = json.loads(log_file.read_text().strip())
        assert record["task_id"] == "task-log-01"
        assert record["payment"] == pytest.approx(30.0)
        assert record["evaluation_score"] == pytest.approx(0.75)

    def test_appends_multiple_records(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        for i in range(3):
            evaluator._log_evaluation(
                signature="agent",
                task_id=f"task-{i}",
                artifact_path=f"/tmp/artifact{i}.txt",
                payment=float(i * 10),
                feedback="ok",
            )
        log_file = tmp_path / "work" / "evaluations.jsonl"
        lines = log_file.read_text().splitlines()
        assert len(lines) == 3

    def test_list_artifact_path_stored(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        paths = ["/tmp/a.txt", "/tmp/b.txt"]
        evaluator._log_evaluation(
            signature="agent",
            task_id="multi-path",
            artifact_path=paths,
            payment=20.0,
            feedback="multi file",
        )
        log_file = tmp_path / "work" / "evaluations.jsonl"
        record = json.loads(log_file.read_text().strip())
        assert record["artifact_paths"] == paths


# ---------------------------------------------------------------------------
# get_evaluation_history & get_total_earnings
# ---------------------------------------------------------------------------

class TestGetEvaluationHistory:
    def _write_history(self, evaluator, signature, records):
        log_dir = os.path.join(evaluator.data_path, signature, "work")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "evaluations.jsonl")
        with open(log_file, "w") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")

    def test_empty_when_no_file(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        history = evaluator.get_evaluation_history("agent-x")
        assert history == []

    def test_returns_all_records(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        records = [
            {"task_id": "t1", "payment": 30.0},
            {"task_id": "t2", "payment": 0.0},
        ]
        self._write_history(evaluator, "agent-x", records)
        history = evaluator.get_evaluation_history("agent-x")
        assert len(history) == 2

    def test_total_earnings(self, tmp_path):
        evaluator = _make_evaluator(tmp_path)
        records = [
            {"task_id": "t1", "payment": 30.0},
            {"task_id": "t2", "payment": 20.0},
            {"task_id": "t3", "payment": 0.0},
        ]
        self._write_history(evaluator, "agent-x", records)
        total = evaluator.get_total_earnings("agent-x")
        assert total == pytest.approx(50.0)
