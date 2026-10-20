"""Unit tests for triage.report rendering, incl. state reconciliation."""

import unittest
from pathlib import Path

from triage.classify import parse_sanitizer_output
from triage.dedup import AnalyzedCrash, group_crashes
from triage.ingest import CrashRecord
from triage.report import ReportMeta, StateGroup, render_report
from triage.tests.test_classify import HBO_READ


def _groups(tmp: Path):
    poc = tmp / "crash-a"
    poc.write_bytes(b"BM fake poc bytes")
    info = parse_sanitizer_output(HBO_READ, exit_code=1)
    rec = CrashRecord(path=poc, size=poc.stat().st_size,
                      sha256="0" * 64, source="libfuzzer")
    groups, _ = group_crashes([AnalyzedCrash(record=rec, info=info)])
    return groups


def _meta(groups, state_groups):
    return ReportMeta(target="bmp_parser", binary_name="bmp_fuzzer",
                      total_inputs=1, crashing_inputs=1, non_crashing=0,
                      symbolized=True, state_groups=state_groups)


class TestReport(unittest.TestCase):
    def test_state_reconciliation_lists_every_state_group(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            groups = _groups(Path(td))
            live = groups[0]
            state = [
                StateGroup(stack_hash=live.stack_hash,
                           bug_class=live.bug_class, direction="READ",
                           top_function="copy_rows", count=7,
                           representative="crash-a", reproduced=True),
                StateGroup(stack_hash="deadbeef1234",
                           bug_class="heap-buffer-overflow",
                           direction="READ", top_function="parse_palette",
                           count=3, representative="crash-ghost",
                           reproduced=False),
            ]
            html = render_report(groups, _meta(groups, state))
        self.assertIn("Campaign state reconciliation", html)
        self.assertIn("deadbeef1234", html)
        self.assertIn("NOT REPRODUCED", html)
        self.assertIn(f"reproduced (G1)", html)
        self.assertIn("crash-ghost", html)

    def test_no_state_groups_no_reconciliation_section(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            groups = _groups(Path(td))
            html = render_report(groups, _meta(groups, []))
        self.assertNotIn("reconciliation", html)


if __name__ == "__main__":
    unittest.main()
