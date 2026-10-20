"""Tests for the scheduler's two rules."""

import unittest

from orchestrate.scheduler import Metrics, decide

KW = dict(stagnation_intervals=5, surge_threshold_per_hour=3.0,
          max_jobs=4)


def metrics(**over) -> Metrics:
    base = dict(elapsed_seconds=3600, unique_groups=2,
                new_unique_last_interval=0,
                intervals_without_new_unique=0, active_jobs=2)
    base.update(over)
    return Metrics(**base)


class TestScheduler(unittest.TestCase):
    def test_quiet_campaign_no_actions(self):
        self.assertEqual(decide(metrics(), **KW), [])

    def test_stagnation_triggers_merge(self):
        acts = decide(metrics(intervals_without_new_unique=5), **KW)
        self.assertEqual([a.kind for a in acts], ["merge_and_reseed"])

    def test_below_stagnation_threshold(self):
        acts = decide(metrics(intervals_without_new_unique=4), **KW)
        self.assertEqual(acts, [])

    def test_surge_scales_up(self):
        acts = decide(metrics(elapsed_seconds=1800, unique_groups=4),
                      **KW)
        self.assertIn("scale_up", [a.kind for a in acts])

    def test_surge_respects_job_cap(self):
        acts = decide(metrics(elapsed_seconds=1800, unique_groups=9,
                              active_jobs=4), **KW)
        self.assertNotIn("scale_up", [a.kind for a in acts])

    def test_surge_needs_minimum_elapsed(self):
        acts = decide(metrics(elapsed_seconds=60, unique_groups=2),
                      **KW)
        self.assertNotIn("scale_up", [a.kind for a in acts])


if __name__ == "__main__":
    unittest.main()
