"""Human-readable campaign status from state.json.

Written to <campaign>/status.txt after every slice and printed by
`kala status`. Deliberately plain text: it is the overnight
campaign's heartbeat, readable with cat at 3 a.m.
"""


def render_status(state: dict) -> str:
    elapsed_h = state["elapsed_seconds"] / 3600.0
    budget_h = state["budget_seconds"] / 3600.0
    groups = state["groups"]
    lines = [
        f"Campaign: {state['name']} (target {state['target']})",
        f"Status: {state['status']}",
        f"Elapsed: {elapsed_h:.2f}h of {budget_h:.2f}h budget "
        f"({state['slices_completed']} slices, {state['jobs']} jobs)",
        f"Executions (summed slice stats): {state['total_execs']}",
        f"Artifacts harvested: {state['artifacts_seen']} "
        f"({state['artifacts_unique']} in new groups)"
        + (f"; resource events (oom/timeout): {state['artifacts_aux']}"
           if state.get("artifacts_aux") else ""),
        f"Unique crash groups: {len(groups)}",
    ]
    for stack_hash, g in sorted(
            groups.items(),
            key=lambda kv: (-kv[1]["count"], kv[0])):
        lines.append(
            f"  [{stack_hash}] {g['bug_class']} "
            f"({g['direction'] or '-'}) @ {g['top_function'] or '?'} "
            f"x{g['count']} first seen slice {g['first_seen_slice']}")
    if state["events"]:
        lines.append("Recent events:")
        for ev in state["events"][-5:]:
            lines.append(f"  slice {ev['slice']}: {ev['kind']} — "
                         f"{ev['detail']}")
    return "\n".join(lines) + "\n"
