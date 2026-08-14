# Adaptive Runtime Policy for Agent Harness

## Overview

This directory contains a standalone demo of a small runtime decision layer for an Agent Harness. Given a snapshot of the current run, it returns one of three actions: `CONTINUE`, `REPLAN`, or `STOP`.

The module uses only the Python standard library and does not modify or integrate with YYGlobal's existing execution path.

## Motivation

Agent harnesses commonly control a run with fixed limits such as maximum steps, timeouts, and retries. Those limits are necessary, but a fixed budget alone does not express whether a longer run is healthy, repeatedly failing, or stuck making the same tool call.

This MVP demonstrates a narrow adaptive layer that evaluates current runtime signals. It is deliberately small: it offers a clear extension point for later recovery and lifecycle features without claiming to provide a complete loop-detection or orchestration system.

## Runtime Signals

- **Step budget:** total steps taken in the current run.
- **Consecutive tool errors:** uninterrupted tool failures.
- **Repeated tool calls:** consecutive calls with the same tool name and equivalent JSON arguments.

`ToolCallTracker` normalizes argument dictionaries with sorted JSON keys. It detects only consecutive identical calls; it does not detect alternating or general graph cycles.

## Decision Policy

Rules are evaluated in priority order: `STOP > REPLAN > CONTINUE`.

| Condition | Action | Reason |
| --- | --- | --- |
| `step_count >= max_steps` | `STOP` | `max_steps_exceeded` |
| `consecutive_errors >= max_consecutive_errors` | `REPLAN` | `consecutive_tool_errors` |
| `repeated_tool_calls >= max_repeated_tool_calls` | `REPLAN` | `repeated_tool_calls` |
| Otherwise | `CONTINUE` | `runtime_healthy` |

## Architecture

```text
                Agent Harness
                     |
                Runtime State
                     |
         +-----------+-----------+
         |           |           |
     Step Budget   Errors    Repeated Calls
         |           |           |
         +-----------+-----------+
                     |
             Adaptive Policy
                     |
          +----------+----------+
          |          |          |
       CONTINUE    REPLAN      STOP
```

## Usage

```python
from runtime_policy import AdaptiveRuntimePolicy, RuntimeState

policy = AdaptiveRuntimePolicy(
    max_steps=10,
    max_consecutive_errors=2,
    max_repeated_tool_calls=3,
)
decision = policy.evaluate(RuntimeState(step_count=2, repeated_tool_calls=1))

print(decision.action.name)  # CONTINUE
print(decision.reason)       # runtime_healthy
```

## Run Demo

From this directory:

```bash
python example.py
```

The demo shows a healthy run, consecutive errors, repeated calls, and an exhausted step budget.

## Run Tests

From this directory:

```bash
python -m pytest test_runtime_policy.py
```

## Relation to YYGlobal Harness

YYGlobal's two provider loops are currently bounded by `agent_max_steps` and `agent_max_tool_calls`. The shared Tool Registry validates tool arguments and permissions, applies per-call timeouts and bounded retries, and persists each tool's name, arguments, result or error, status, and duration as a `ToolCall` trace. Provider failures such as timeouts, invalid arguments, and tool errors already call the planner's bounded `replan_after_failure`, while the Harness records run/step status and applies input and output guardrails.

This demo would complement that control plane by deriving a decision from counters accumulated during the provider loop. A future integration could update `RuntimeState` after each model step and tool result, feed normalized calls from the existing Tool Registry trace into `ToolCallTracker`, and map `REPLAN` to the existing planner recovery path or `STOP` to the run's `stop_reason`. No such integration is made in this standalone MVP.

## Future Work

- Context budget monitoring
- Context compaction
- Dynamic tool loading
- Failure classification
- Checkpoint and resume
- Human-in-the-loop escalation
- Runtime policy integration with the existing YYGlobal Harness

These are possible extensions only. The current version remains a standalone demo / MVP.
