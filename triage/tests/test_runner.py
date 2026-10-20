"""Unit tests for triage.runner: env builders, symbolizer choice,
and the classification replay's stuck-symbolizer fallback."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from triage.runner import (find_symbolizer, fuzz_env, replay_classified,
                           replay_env)


class TestFuzzEnv(unittest.TestCase):
    def test_symbolization_is_off(self):
        env = fuzz_env(replay_env("/usr/bin/llvm-symbolizer"))
        asan = env["ASAN_OPTIONS"]
        self.assertIn("symbolize=0", asan)
        self.assertNotIn("external_symbolizer_path", asan)
        # Crash detection behavior is unchanged.
        self.assertIn("abort_on_error=1", asan)
        self.assertIn("print_stacktrace=0", env["UBSAN_OPTIONS"])
        self.assertIn("halt_on_error=1", env["UBSAN_OPTIONS"])

    def test_user_options_survive_except_symbolizer(self):
        base = {"ASAN_OPTIONS": "detect_leaks=1:"
                                "external_symbolizer_path=/x/sym",
                "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"}
        env = fuzz_env(base)
        self.assertIn("detect_leaks=1", env["ASAN_OPTIONS"])
        self.assertNotIn("/x/sym", env["ASAN_OPTIONS"])
        self.assertIn("print_stacktrace=0", env["UBSAN_OPTIONS"])
        self.assertEqual(base["UBSAN_OPTIONS"],
                         "halt_on_error=1:print_stacktrace=1")  # unmutated

    def test_replay_env_still_symbolizes(self):
        env = replay_env("/usr/bin/llvm-symbolizer")
        self.assertIn("external_symbolizer_path=/usr/bin/llvm-symbolizer",
                      env["ASAN_OPTIONS"])
        self.assertNotIn("symbolize=0", env["ASAN_OPTIONS"])


class TestFindSymbolizer(unittest.TestCase):
    def test_addr2line_preferred_over_llvm_symbolizer(self):
        # Regression (Phase 4 VM QA): ASan's symbolizer protocol
        # deadlocked against llvm-symbolizer; addr2line must win
        # whenever both exist.
        with mock.patch("triage.runner.shutil.which",
                        side_effect=lambda n: f"/usr/bin/{n}"):
            self.assertEqual(find_symbolizer(), "/usr/bin/addr2line")

    def test_llvm_symbolizer_is_the_fallback(self):
        def which(name):
            return "/usr/bin/llvm-symbolizer-19" \
                if name == "llvm-symbolizer-19" else None
        with mock.patch("triage.runner.shutil.which", side_effect=which):
            self.assertEqual(find_symbolizer(),
                             "/usr/bin/llvm-symbolizer-19")

    def test_none_when_no_symbolizer_exists(self):
        with mock.patch("triage.runner.shutil.which", return_value=None):
            self.assertIsNone(find_symbolizer())


class TestReplayClassified(unittest.TestCase):
    def _script(self, tmp: Path, body: str) -> Path:
        script = tmp / "fake_fuzzer.sh"
        script.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        script.chmod(0o755)
        return script

    def test_fast_crash_is_not_retried(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            counter = tmp / "runs"
            script = self._script(
                tmp, f'echo run >> "{counter}"\n'
                     'echo "SUMMARY: AddressSanitizer: SEGV"\n'
                     "exit 1\n")
            result = replay_classified(script, "poc", timeout=5,
                                       env=replay_env("/usr/bin/addr2line"))
            self.assertFalse(result.timed_out)
            self.assertEqual(result.exit_code, 1)
            self.assertEqual(counter.read_text().splitlines(), ["run"])

    def test_wedged_symbolizer_falls_back_to_plain_replay(self):
        # Script mimics the VM failure: with a symbolizing env it
        # hangs (deadlocked symbolizer child); with symbolize=0 it
        # crashes immediately — the fallback must rescue the crash.
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            counter = tmp / "runs"
            script = self._script(
                tmp, f'echo run >> "{counter}"\n'
                     'case "$ASAN_OPTIONS" in\n'
                     "  *symbolize=0*) echo "
                     '"SUMMARY: AddressSanitizer: SEGV"; exit 1 ;;\n'
                     "  *) sleep 3 ;;\n"
                     "esac\n")
            result = replay_classified(script, "poc", timeout=0.5,
                                       env=replay_env("/usr/bin/addr2line"))
            self.assertFalse(result.timed_out)
            self.assertEqual(result.exit_code, 1)
            self.assertIn("SUMMARY", result.output)
            self.assertEqual(len(counter.read_text().splitlines()), 2)

    def test_genuine_hang_stays_a_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            script = self._script(tmp, "sleep 3\n")
            result = replay_classified(script, "poc", timeout=0.3,
                                       env=replay_env(None))
            self.assertTrue(result.timed_out)


if __name__ == "__main__":
    unittest.main()
