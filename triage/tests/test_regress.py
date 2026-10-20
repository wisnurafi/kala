"""Unit tests for triage.regress, using a fake fuzzer binary.

The fake prints a canned ASan report and exits non-zero when the
input contains b"CRASH", and exits 0 otherwise — enough to exercise
the verify-before-promote contract without a real build.
"""

import stat
import tempfile
import unittest
from pathlib import Path

from triage.regress import RegressError, add_regression_poc
from triage.runner import replay_env
from triage.tests.test_classify import HBO_READ

FAKE = """\
#!/usr/bin/env python3
import sys
data = open(sys.argv[1], "rb").read()
if b"CRASH" in data:
    sys.stderr.write({report!r})
    sys.exit(1)
sys.exit(0)
"""


class TestRegress(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        root = Path(self.td.name)
        self.binary = root / "fake_fuzzer"
        self.binary.write_text(FAKE.format(report=HBO_READ))
        self.binary.chmod(self.binary.stat().st_mode | stat.S_IEXEC)
        self.reg_dir = root / "regression" / "fake_target"
        self.env = replay_env(None)

    def tearDown(self):
        self.td.cleanup()

    def _poc(self, data: bytes) -> Path:
        poc = Path(self.td.name) / "candidate.bmp"
        poc.write_bytes(data)
        return poc

    def _add(self, poc: Path, **kw):
        args = dict(name="bug9_example", expect_class="heap-buffer-overflow",
                    expect_function="copy_rows", bug="9 — example",
                    expected="ASan heap-buffer-overflow READ in copy_rows",
                    trigger="contains the CRASH marker", env=self.env)
        args.update(kw)
        return add_regression_poc(self.binary, poc, self.reg_dir, **args)

    def test_verified_poc_is_promoted_and_documented(self):
        dest = self._add(self._poc(b"BM CRASH input"))
        self.assertTrue(dest.is_file())
        readme = (self.reg_dir / "README.md").read_text()
        self.assertIn("`bug9_example.bmp`", readme)
        self.assertIn("9 — example", readme)

    def test_non_crashing_poc_is_refused(self):
        with self.assertRaises(RegressError):
            self._add(self._poc(b"BM perfectly fine input"))
        self.assertFalse(self.reg_dir.exists() and
                         any(self.reg_dir.iterdir()))

    def test_wrong_expected_class_is_refused(self):
        with self.assertRaises(RegressError):
            self._add(self._poc(b"CRASH"), expect_class="double-free")

    def test_duplicate_bytes_are_refused(self):
        self._add(self._poc(b"CRASH once"))
        with self.assertRaises(RegressError):
            self._add(self._poc(b"CRASH once"), name="bug10_other")


if __name__ == "__main__":
    unittest.main()
