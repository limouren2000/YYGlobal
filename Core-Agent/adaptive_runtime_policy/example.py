"""Run four illustrative adaptive runtime policy cases."""

from runtime_policy import AdaptiveRuntimePolicy, RuntimeState, ToolCallTracker


def show_case(title: str, state: RuntimeState, policy: AdaptiveRuntimePolicy) -> None:
    decision = policy.evaluate(state)
    print(f"{title}\nAction: {decision.action.name}\nReason: {decision.reason}\n")


def main() -> None:
    policy = AdaptiveRuntimePolicy(
        max_steps=10,
        max_consecutive_errors=2,
        max_repeated_tool_calls=3,
    )

    show_case(
        "[Case 1] Healthy Runtime",
        RuntimeState(step_count=2, consecutive_errors=0, repeated_tool_calls=1),
        policy,
    )
    show_case(
        "[Case 2] Consecutive Tool Errors",
        RuntimeState(step_count=3, consecutive_errors=2, repeated_tool_calls=1),
        policy,
    )

    tracker = ToolCallTracker()
    for _ in range(3):
        tracker.record("search_school", {"school": "CMU"})
    show_case(
        "[Case 3] Repeated Tool Calls",
        RuntimeState(step_count=4, repeated_tool_calls=tracker.repeated_tool_calls),
        policy,
    )
    show_case(
        "[Case 4] Step Budget Exceeded",
        RuntimeState(step_count=policy.max_steps),
        policy,
    )


if __name__ == "__main__":
    main()
