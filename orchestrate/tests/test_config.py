"""Tests for orchestrate.config (both YAML paths must agree)."""

import tempfile
import unittest
from pathlib import Path

from orchestrate.config import _parse_fallback, load_config

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "campaign.yaml"


class TestConfig(unittest.TestCase):
    def test_example_loads(self):
        cfg = load_config(EXAMPLE)
        self.assertEqual(cfg.name, "bmp-demo")
        self.assertEqual(cfg.target, "bmp_parser")
        self.assertEqual(cfg.jobs, 2)
        self.assertEqual(cfg.duration_minutes, 30)
        self.assertEqual(cfg.stagnation_intervals, 5)
        self.assertEqual(cfg.max_jobs, 4)
        self.assertTrue(cfg.triage_on_finish)

    def test_fallback_parser_matches(self):
        raw = _parse_fallback(EXAMPLE.read_text())
        self.assertEqual(raw["campaign"]["name"], "bmp-demo")
        self.assertEqual(raw["campaign"]["jobs"], 2)
        self.assertEqual(raw["scheduler"]["max_jobs"], 4)
        self.assertIs(raw["campaign"]["triage_on_finish"], True)

    def test_unknown_key_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml",
                                         delete=False) as fh:
            fh.write("campaign:\n  name: x\n  bogus_key: 1\n")
            path = fh.name
        with self.assertRaises(ValueError):
            load_config(path)

    def test_invalid_values_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml",
                                         delete=False) as fh:
            fh.write("campaign:\n  name: x\n  jobs: 0\n")
            path = fh.name
        with self.assertRaises(ValueError):
            load_config(path)


if __name__ == "__main__":
    unittest.main()
