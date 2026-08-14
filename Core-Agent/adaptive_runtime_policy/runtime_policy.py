"""Small, framework-independent runtime policy for an agent harness."""

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any, Mapping, Optional, Tuple


class RuntimeAction(str, Enum):
    CONTINUE = "continue"
    REPLAN = "replan"
    STOP = "stop"


@dataclass
class RuntimeState:
    step_count: int = 0
    consecutive_errors: int = 0
    repeated_tool_calls: int = 0


@dataclass(frozen=True)
class RuntimeDecision:
    action: RuntimeAction
    reason: str


class AdaptiveRuntimePolicy:
    """Evaluate a runtime snapshot using a small set of ordered rules."""

    def __init__(
        self,
        max_steps: int = 10,
        max_consecutive_errors: int = 2,
        max_repeated_tool_calls: int = 3,
    ) -> None:
        for name, value in (
            ("max_steps", max_steps),
            ("max_consecutive_errors", max_consecutive_errors),
            ("max_repeated_tool_calls", max_repeated_tool_calls),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        self.max_steps = max_steps
        self.max_consecutive_errors = max_consecutive_errors
        self.max_repeated_tool_calls = max_repeated_tool_calls

    def evaluate(self, state: RuntimeState) -> RuntimeDecision:
        # Rule order makes the priority explicit: STOP > REPLAN > CONTINUE.
        if state.step_count >= self.max_steps:
            return RuntimeDecision(RuntimeAction.STOP, "max_steps_exceeded")
        if state.consecutive_errors >= self.max_consecutive_errors:
            return RuntimeDecision(RuntimeAction.REPLAN, "consecutive_tool_errors")
        if state.repeated_tool_calls >= self.max_repeated_tool_calls:
            return RuntimeDecision(RuntimeAction.REPLAN, "repeated_tool_calls")
        return RuntimeDecision(RuntimeAction.CONTINUE, "runtime_healthy")


class ToolCallTracker:
    """Count consecutive identical calls after normalizing argument key order."""

    def __init__(self) -> None:
        self._last_call: Optional[Tuple[str, str]] = None
        self.repeated_tool_calls = 0

    def record(self, tool_name: str, arguments: Mapping[str, Any]) -> int:
        call = (tool_name, json.dumps(arguments, sort_keys=True, separators=(",", ":")))
        if call == self._last_call:
            self.repeated_tool_calls += 1
        else:
            self._last_call = call
            self.repeated_tool_calls = 1
        return self.repeated_tool_calls
