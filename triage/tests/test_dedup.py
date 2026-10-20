"""Unit tests for triage.dedup grouping."""

import unittest
from pathlib import Path

from triage.classify import parse_sanitizer_output
from triage.dedup import AnalyzedCrash, group_crashes, stack_hash
from triage.ingest import CrashRecord
from triage.tests.test_classify import HBO_READ, SEGV_WRITE, UAF_WRITE


def analyzed(name: str, output: str, size: int = 100) -> AnalyzedCrash:
    info = parse_sanitizer_output(output, exit_code=1)
    rec = CrashRecord(path=Path(name), size=size, sha256="0" * 64,
                      source="libfuzzer")
    return AnalyzedCrash(record=rec, info=info)


HBO_WRITE_COPYROWS = """\
==200==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x502000000011
WRITE of size 12 at 0x502000000011 thread T0
    #0 0xaaa in __asan_memcpy (/bin/bmp_fuzzer+0xa)
    #1 0xbbb in copy_rows /src/targets/bmp_parser/bmp_parser.c:68:5
SUMMARY: AddressSanitizer: heap-buffer-overflow in __asan_memcpy
"""


class TestDedup(unittest.TestCase):
    def test_identical_root_cause_groups_together(self):
        a = analyzed("crash-a", HBO_READ, size=300)
        b = analyzed("crash-b", HBO_READ.replace("0x508000000076",
                                                 "0x508000009999"),
                     size=120)
        groups, non = group_crashes([a, b])
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].members), 2)
        self.assertEqual(groups[0].representative.record.path.name,
                         "crash-b")  # smallest input wins
        self.assertEqual(non, [])

    def test_distinct_bugs_stay_separate(self):
        groups, _ = group_crashes([
            analyzed("crash-a", HBO_READ),
            analyzed("crash-b", UAF_WRITE),
        ])
        self.assertEqual(len(groups), 2)

    def test_segv_merges_into_matching_overflow_group(self):
        groups, _ = group_crashes([
            analyzed("crash-segv", SEGV_WRITE),
            analyzed("crash-hbo", HBO_WRITE_COPYROWS),
        ])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].bug_class, "heap-buffer-overflow")
        self.assertIn("SEGV-unknown", groups[0].merged_classes)

    def test_stack_hash_ignores_line_numbers(self):
        a = analyzed("crash-a", HBO_READ)
        shifted = HBO_READ.replace("bmp_parser.c:68", "bmp_parser.c:71")
        b = analyzed("crash-b", shifted)
        self.assertEqual(stack_hash(a.info), stack_hash(b.info))

    def test_no_crash_inputs_are_separated(self):
        from triage.classify import parse_sanitizer_output as parse
        ok = AnalyzedCrash(
            record=CrashRecord(Path("crash-ok"), 10, "0" * 64, "libfuzzer"),
            info=parse("fine\n", exit_code=0))
        groups, non = group_crashes([ok])
        self.assertEqual(groups, [])
        self.assertEqual(len(non), 1)


if __name__ == "__main__":
    unittest.main()
