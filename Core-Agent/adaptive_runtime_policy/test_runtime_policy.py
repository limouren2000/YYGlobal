import pytest

from runtime_policy import (
    AdaptiveRuntimePolicy,
    RuntimeAction,
    RuntimeState,
    ToolCallTracker,
)


def make_policy() -> AdaptiveRuntimePolicy:
    return AdaptiveRuntimePolicy(
        max_steps=10,
        max_consecutive_errors=2,
        max_repeated_tool_calls=3,
    )


def test_healthy_runtime_continues() -> None:
    decision = make_policy().evaluate(RuntimeState(step_count=2, repeated_tool_calls=1))
    assert decision.action is RuntimeAction.CONTINUE
    assert decision.reason == "runtime_healthy"


def test_consecutive_errors_trigger_replan() -> None:
    decision = make_policy().evaluate(RuntimeState(consecutive_errors=2))
    assert decision.action is RuntimeAction.REPLAN
    assert decision.reason == "consecutive_tool_errors"


def test_repeated_tool_calls_trigger_replan() -> None:
    decision = make_policy().evaluate(RuntimeState(repeated_tool_calls=3))
    assert decision.action is RuntimeAction.REPLAN
    assert decision.reason == "repeated_tool_calls"


def test_step_budget_stops_run() -> None:
    decision = make_policy().evaluate(RuntimeState(step_count=10))
    assert decision.action is RuntimeAction.STOP
    assert decision.reason == "max_steps_exceeded"


def test_stop_has_priority_over_replan() -> None:
    decision = make_policy().evaluate(RuntimeState(step_count=10, consecutive_errors=2))
    assert decision.action is RuntimeAction.STOP


def test_argument_key_order_counts_as_same_call() -> None:
    tracker = ToolCallTracker()
    tracker.record("search_school", {"school": "CMU", "program": "CS"})
    count = tracker.record("search_school", {"program": "CS", "school": "CMU"})
    assert count == 2


def test_different_call_resets_tracker() -> None:
    tracker = ToolCallTracker()
    tracker.record("search_school", {"school": "CMU"})
    tracker.record("search_school", {"school": "CMU"})
    assert tracker.record("search_school", {"school": "MIT"}) == 1


def test_thresholds_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_steps"):
        AdaptiveRuntimePolicy(max_steps=0)
