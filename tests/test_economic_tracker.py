"""
Tests for livebench/agent/economic_tracker.py

These are proper pytest tests for the EconomicTracker class and the
standalone track_response_tokens() helper, replacing the old ad-hoc
scripts/test_economic_tracker.py runner.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from livebench.agent.economic_tracker import EconomicTracker, track_response_tokens


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tracker(tmp_path):
    """Return an EconomicTracker backed by a temporary directory."""
    t = EconomicTracker(
        signature="test-agent",
        initial_balance=1000.0,
        input_token_price=2.5,
        output_token_price=10.0,
        data_path=str(tmp_path / "economic"),
    )
    t.initialize()
    return t


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInitialization:
    def test_initial_balance(self, tracker):
        assert tracker.get_balance() == 1000.0

    def test_survival_status_thriving(self, tracker):
        assert tracker.get_survival_status() == "thriving"

    def test_not_bankrupt(self, tracker):
        assert not tracker.is_bankrupt()

    def test_session_cost_zero(self, tracker):
        assert tracker.get_session_cost() == 0.0

    def test_summary_structure(self, tracker):
        s = tracker.get_summary()
        assert "balance" in s
        assert "survival_status" in s
        assert "total_token_cost" in s
        assert s["signature"] == "test-agent"

    def test_loads_existing_state(self, tmp_path):
        """If a balance file already exists, the second tracker loads it."""
        data_dir = str(tmp_path / "economic")
        t1 = EconomicTracker(
            signature="agent", initial_balance=500.0, data_path=data_dir
        )
        t1.initialize()
        t1.add_trading_profit(200.0)
        # Persist current balance so the second tracker can read it
        t1.save_daily_state("2025-06-01", trading_profit=200.0)

        t2 = EconomicTracker(
            signature="agent", initial_balance=500.0, data_path=data_dir
        )
        t2.initialize()
        assert t2.get_balance() == pytest.approx(700.0)


# ---------------------------------------------------------------------------
# Token tracking
# ---------------------------------------------------------------------------

class TestTrackTokens:
    def test_cost_computed_from_prices(self, tracker):
        cost = tracker.track_tokens(1_000_000, 0)
        assert cost == pytest.approx(2.5)
        assert tracker.get_balance() == pytest.approx(1000.0 - 2.5)

    def test_output_tokens_cost(self, tracker):
        cost = tracker.track_tokens(0, 1_000_000)
        assert cost == pytest.approx(10.0)

    def test_precomputed_cost_used_directly(self, tracker):
        cost = tracker.track_tokens(999_999, 999_999, cost=0.01)
        assert cost == pytest.approx(0.01)
        assert tracker.get_balance() == pytest.approx(999.99)

    def test_session_cost_accumulates(self, tracker):
        tracker.track_tokens(1_000_000, 0)
        tracker.track_tokens(1_000_000, 0)
        assert tracker.get_session_cost() == pytest.approx(5.0)

    def test_within_task_updates_task_costs(self, tracker):
        tracker.start_task("task-1")
        tracker.track_tokens(1_000_000, 0)
        assert tracker.task_costs["llm_tokens"] == pytest.approx(2.5)

    def test_outside_task_does_not_raise(self, tracker):
        # current_task_id is None — no task context
        tracker.track_tokens(100, 50)  # should not raise


# ---------------------------------------------------------------------------
# API call tracking
# ---------------------------------------------------------------------------

class TestTrackApiCall:
    def test_per_token_api_cost(self, tracker):
        cost = tracker.track_api_call(tokens=500_000, price_per_1m=5.0, api_name="JINA")
        assert cost == pytest.approx(2.5)
        assert tracker.get_balance() == pytest.approx(997.5)

    def test_api_categorised_as_search(self, tracker):
        tracker.start_task("t1")
        tracker.track_api_call(1_000_000, 1.0, api_name="tavily_search")
        assert tracker.task_costs["search_api"] == pytest.approx(1.0)

    def test_api_categorised_as_ocr(self, tracker):
        tracker.start_task("t1")
        tracker.track_api_call(1_000_000, 1.0, api_name="ocr_service")
        assert tracker.task_costs["ocr_api"] == pytest.approx(1.0)

    def test_api_categorised_as_other(self, tracker):
        tracker.start_task("t1")
        tracker.track_api_call(1_000_000, 1.0, api_name="some_api")
        assert tracker.task_costs["other_api"] == pytest.approx(1.0)


class TestTrackFlatApiCall:
    def test_flat_rate_deducted(self, tracker):
        cost = tracker.track_flat_api_call(0.001, api_name="tavily")
        assert cost == pytest.approx(0.001)
        assert tracker.get_balance() == pytest.approx(999.999)

    def test_flat_rate_search_channel(self, tracker):
        tracker.start_task("t1")
        tracker.track_flat_api_call(0.005, api_name="jina_search")
        assert tracker.task_costs["search_api"] == pytest.approx(0.005)

    def test_flat_rate_ocr_channel(self, tracker):
        tracker.start_task("t1")
        tracker.track_flat_api_call(0.002, api_name="ocr_endpoint")
        assert tracker.task_costs["ocr_api"] == pytest.approx(0.002)


# ---------------------------------------------------------------------------
# Work income & evaluation threshold
# ---------------------------------------------------------------------------

class TestAddWorkIncome:
    def test_payment_above_threshold_increases_balance(self, tracker):
        payment = tracker.add_work_income(50.0, "task-1", evaluation_score=0.8)
        assert payment == pytest.approx(50.0)
        assert tracker.get_balance() == pytest.approx(1050.0)

    def test_payment_exactly_at_threshold(self, tracker):
        payment = tracker.add_work_income(50.0, "task-1", evaluation_score=0.6)
        assert payment == pytest.approx(50.0)

    def test_payment_below_threshold_is_zero(self, tracker):
        payment = tracker.add_work_income(50.0, "task-1", evaluation_score=0.59)
        assert payment == pytest.approx(0.0)
        # Balance should not have increased
        assert tracker.get_balance() == pytest.approx(1000.0)

    def test_zero_score_rejected(self, tracker):
        payment = tracker.add_work_income(100.0, "task-x", evaluation_score=0.0)
        assert payment == pytest.approx(0.0)

    def test_perfect_score_paid(self, tracker):
        payment = tracker.add_work_income(100.0, "task-x", evaluation_score=1.0)
        assert payment == pytest.approx(100.0)

    def test_custom_threshold(self, tmp_path):
        t = EconomicTracker(
            signature="agent2",
            initial_balance=100.0,
            data_path=str(tmp_path / "economic"),
            min_evaluation_threshold=0.8,
        )
        t.initialize()
        payment = t.add_work_income(50.0, "task-1", evaluation_score=0.75)
        assert payment == pytest.approx(0.0)
        payment = t.add_work_income(50.0, "task-1", evaluation_score=0.80)
        assert payment == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Trading profit
# ---------------------------------------------------------------------------

class TestAddTradingProfit:
    def test_positive_profit_increases_balance(self, tracker):
        tracker.add_trading_profit(25.0)
        assert tracker.get_balance() == pytest.approx(1025.0)

    def test_loss_decreases_balance(self, tracker):
        tracker.add_trading_profit(-100.0)
        assert tracker.get_balance() == pytest.approx(900.0)

    def test_total_trading_profit_accumulates(self, tracker):
        tracker.add_trading_profit(10.0)
        tracker.add_trading_profit(-5.0)
        assert tracker.total_trading_profit == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Survival status
# ---------------------------------------------------------------------------

class TestSurvivalStatus:
    @pytest.mark.parametrize(
        "balance,expected",
        [
            (1000.0, "thriving"),
            (500.0, "thriving"),
            (499.99, "stable"),
            (100.0, "stable"),
            (99.99, "struggling"),
            (1.0, "struggling"),
            (0.0, "bankrupt"),
            (-1.0, "bankrupt"),
        ],
    )
    def test_status_thresholds(self, tmp_path, balance, expected):
        t = EconomicTracker(
            signature="agent", initial_balance=balance, data_path=str(tmp_path / "economic")
        )
        t.initialize()
        assert t.get_survival_status() == expected

    def test_is_bankrupt_false_when_positive(self, tracker):
        assert not tracker.is_bankrupt()

    def test_is_bankrupt_true_when_zero(self, tmp_path):
        t = EconomicTracker(
            signature="agent", initial_balance=0.0, data_path=str(tmp_path / "economic")
        )
        t.initialize()
        assert t.is_bankrupt()


# ---------------------------------------------------------------------------
# Task lifecycle (start / end)
# ---------------------------------------------------------------------------

class TestTaskLifecycle:
    def test_start_task_sets_current_task(self, tracker):
        tracker.start_task("my-task", date="2025-01-01")
        assert tracker.current_task_id == "my-task"
        assert tracker.current_task_date == "2025-01-01"

    def test_end_task_clears_current_task(self, tracker):
        tracker.start_task("my-task")
        tracker.end_task()
        assert tracker.current_task_id is None

    def test_end_task_writes_record(self, tmp_path):
        t = EconomicTracker(
            signature="agent", initial_balance=100.0, data_path=str(tmp_path / "economic")
        )
        t.initialize()
        t.start_task("task-abc", date="2025-06-01")
        t.track_tokens(100_000, 50_000)
        t.end_task()
        # token_costs.jsonl should have at least one line
        costs_file = tmp_path / "economic" / "token_costs.jsonl"
        assert costs_file.exists()
        lines = costs_file.read_text().splitlines()
        assert len(lines) >= 1
        record = json.loads(lines[0])
        assert record["task_id"] == "task-abc"

    def test_end_task_without_active_task_is_noop(self, tracker):
        # Should not raise
        tracker.end_task()


# ---------------------------------------------------------------------------
# Daily state & balance file
# ---------------------------------------------------------------------------

class TestSaveDailyState:
    def test_saves_balance_record(self, tmp_path):
        t = EconomicTracker(
            signature="agent", initial_balance=500.0, data_path=str(tmp_path / "economic")
        )
        t.initialize()
        t.save_daily_state("2025-06-01", work_income=100.0, trading_profit=10.0)

        balance_file = tmp_path / "economic" / "balance.jsonl"
        records = [json.loads(line) for line in balance_file.read_text().splitlines()]
        # Should have at least 2 records (init + daily state)
        assert len(records) >= 2
        last = records[-1]
        assert last["date"] == "2025-06-01"
        assert last["balance"] == pytest.approx(500.0)

    def test_resets_daily_cost(self, tracker):
        tracker.track_tokens(1_000_000, 0)
        assert tracker.get_daily_cost() > 0
        tracker.save_daily_state("2025-06-01")
        assert tracker.get_daily_cost() == 0.0


# ---------------------------------------------------------------------------
# record_task_completion
# ---------------------------------------------------------------------------

class TestRecordTaskCompletion:
    def test_writes_completion_record(self, tmp_path):
        t = EconomicTracker(
            signature="agent", initial_balance=100.0, data_path=str(tmp_path / "economic")
        )
        t.initialize()
        t.start_task("task-1", date="2025-06-01")
        t.record_task_completion(
            task_id="task-1",
            work_submitted=True,
            wall_clock_seconds=120.5,
            evaluation_score=0.85,
            money_earned=40.0,
            date="2025-06-01",
        )
        completions_file = tmp_path / "economic" / "task_completions.jsonl"
        assert completions_file.exists()
        record = json.loads(completions_file.read_text().strip())
        assert record["task_id"] == "task-1"
        assert record["work_submitted"] is True
        assert record["evaluation_score"] == pytest.approx(0.85)
        assert record["money_earned"] == pytest.approx(40.0)
        assert record["wall_clock_seconds"] == pytest.approx(120.5)

    def test_replaces_existing_record_for_same_task(self, tmp_path):
        t = EconomicTracker(
            signature="agent", initial_balance=100.0, data_path=str(tmp_path / "economic")
        )
        t.initialize()
        t.start_task("task-1")
        t.record_task_completion(
            "task-1", work_submitted=False, wall_clock_seconds=10.0,
            evaluation_score=0.0, money_earned=0.0,
        )
        # Record again (e.g. retry with different score)
        t.record_task_completion(
            "task-1", work_submitted=True, wall_clock_seconds=20.0,
            evaluation_score=0.9, money_earned=50.0,
        )
        completions_file = tmp_path / "economic" / "task_completions.jsonl"
        lines = completions_file.read_text().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["evaluation_score"] == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# reset_session
# ---------------------------------------------------------------------------

class TestResetSession:
    def test_clears_session_tracking(self, tracker):
        tracker.track_tokens(1_000_000, 500_000)
        tracker.reset_session()
        assert tracker.session_input_tokens == 0
        assert tracker.session_output_tokens == 0
        assert tracker.session_cost == 0.0


# ---------------------------------------------------------------------------
# get_cost_analytics
# ---------------------------------------------------------------------------

class TestGetCostAnalytics:
    def test_returns_empty_analytics_when_no_file(self, tmp_path):
        t = EconomicTracker(
            signature="agent", initial_balance=100.0, data_path=str(tmp_path / "economic")
        )
        t.initialize()
        analytics = t.get_cost_analytics()
        assert analytics["total_tasks"] == 0
        assert analytics["total_income"] == 0.0

    def test_income_tracked_for_paid_task(self, tracker):
        tracker.start_task("t1", date="2025-06-01")
        tracker.add_work_income(100.0, "t1", evaluation_score=0.9)
        tracker.end_task()
        analytics = tracker.get_cost_analytics()
        assert analytics["total_income"] == pytest.approx(100.0)
        assert analytics["tasks_paid"] == 1

    def test_rejected_task_counted(self, tracker):
        tracker.start_task("t1", date="2025-06-01")
        tracker.add_work_income(100.0, "t1", evaluation_score=0.3)
        tracker.end_task()
        analytics = tracker.get_cost_analytics()
        assert analytics["tasks_rejected"] == 1
        assert analytics["tasks_paid"] == 0


# ---------------------------------------------------------------------------
# __str__
# ---------------------------------------------------------------------------

class TestStr:
    def test_includes_balance_and_status(self, tracker):
        s = str(tracker)
        assert "test-agent" in s
        assert "1000.00" in s
        assert "thriving" in s


# ---------------------------------------------------------------------------
# track_response_tokens helper
# ---------------------------------------------------------------------------

class TestTrackResponseTokens:
    def _make_response(self, prompt_tokens, completion_tokens, cost=None, use_metadata=False):
        response = MagicMock()
        if use_metadata:
            response.response_metadata = {"token_usage": None}
            response.usage_metadata = {
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
            }
        else:
            response.response_metadata = {
                "token_usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    **({"cost": cost} if cost is not None else {}),
                }
            }
            response.usage_metadata = {
                "input_tokens": prompt_tokens,
                "output_tokens": completion_tokens,
            }
        return response

    def test_tracks_from_api_metadata(self, tracker):
        response = self._make_response(100, 50)
        logger_mock = MagicMock()
        logger_mock.terminal_print = MagicMock()
        track_response_tokens(response, tracker, logger_mock, is_openrouter=False)
        assert tracker.session_input_tokens == 100
        assert tracker.session_output_tokens == 50

    def test_tracks_from_langchain_usage_metadata_fallback(self, tracker):
        response = self._make_response(200, 75, use_metadata=True)
        logger_mock = MagicMock()
        logger_mock.terminal_print = MagicMock()
        track_response_tokens(response, tracker, logger_mock, is_openrouter=False)
        assert tracker.session_input_tokens == 200
        assert tracker.session_output_tokens == 75

    def test_openrouter_cost_passed_directly(self, tmp_path):
        t = EconomicTracker(
            signature="agent", initial_balance=1000.0, data_path=str(tmp_path / "economic")
        )
        t.initialize()
        response = self._make_response(500, 250, cost=0.0042)
        logger_mock = MagicMock()
        logger_mock.terminal_print = MagicMock()
        track_response_tokens(response, t, logger_mock, is_openrouter=True)
        # With a direct cost of 0.0042, balance should decrease by exactly that amount
        assert t.get_balance() == pytest.approx(1000.0 - 0.0042)

    def test_non_openrouter_ignores_cost_field(self, tmp_path):
        t = EconomicTracker(
            signature="agent", initial_balance=1000.0, data_path=str(tmp_path / "economic"),
            input_token_price=0.0, output_token_price=0.0,
        )
        t.initialize()
        response = self._make_response(1_000_000, 0, cost=999.0)
        logger_mock = MagicMock()
        logger_mock.terminal_print = MagicMock()
        # is_openrouter=False → cost field should be ignored; price is 0 so no deduction
        track_response_tokens(response, t, logger_mock, is_openrouter=False)
        assert t.get_balance() == pytest.approx(1000.0)
