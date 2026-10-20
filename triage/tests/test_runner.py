"""Unit tests for triage.runner environment builders."""

import unittest

from triage.runner import fuzz_env, replay_env


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


if __name__ == "__main__":
    unittest.main()
