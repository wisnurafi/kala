"""Metric-driven campaign scheduling rules.

The scheduler is a pure decision function over campaign metrics —
no I/O — so the rules are unit-testable without running a fuzzer.
The runner feeds it a Metrics snapshot after every slice; it
answers with zero or more actions:

- merge_and_reseed: the campaign has produced no new unique crash
  group for `stagnation_intervals` consecutive checks. Merge every
  job corpus into a minimized shared corpus and restart the jobs
  from it — fresh diversity instead of grinding a dead corpus.
- scale_up: new unique groups are arriving faster than
  `surge_threshold_per_hour` and jobs < max_jobs. A hot target
  deserves more CPU; add one job (the runner caps at max_jobs).
"""

from dataclasses import dataclass


@dataclass
class Metrics:
    elapsed_seconds: float
    unique_groups: int
    new_unique_last_interval: int
    intervals_without_new_unique: int
    active_jobs: int


@dataclass
class Action:
    kind: str  # merge_and_reseed | scale_up
    reason: str


def decide(metrics: Metrics, *, stagnation_intervals: int,
           surge_threshold_per_hour: float, max_jobs: int
           ) -> list[Action]:
    actions: list[Action] = []
    if metrics.intervals_without_new_unique >= stagnation_intervals:
        actions.append(Action(
            "merge_and_reseed",
            f"no new unique group for "
            f"{metrics.intervals_without_new_unique} checks "
            f"(threshold {stagnation_intervals})"))
    hours = max(metrics.elapsed_seconds / 3600.0, 1e-9)
    unique_rate = metrics.unique_groups / hours
    if metrics.elapsed_seconds >= 300 \
            and unique_rate > surge_threshold_per_hour \
            and metrics.active_jobs < max_jobs:
        actions.append(Action(
            "scale_up",
            f"unique-group rate {unique_rate:.1f}/h exceeds "
            f"{surge_threshold_per_hour}/h at {metrics.active_jobs} "
            f"jobs (cap {max_jobs})"))
    return actions
