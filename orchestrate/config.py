"""Campaign configuration loading and validation.

Configs are YAML (see examples/campaign.yaml). PyYAML is used when
installed; a small fallback parser covers the documented schema
(two mapping levels, scalar values) so a bare VM without PyYAML can
still run campaigns. All relative paths resolve against the repo
root, not the config file's directory, so examples/ configs can
reference corpus/bmp etc. directly.

Standard library only (PyYAML is an optional accelerator, per the
Phase 2 zero-dependency rule).
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CampaignConfig:
    name: str = "campaign"
    target: str = "bmp_parser"
    binary: str | None = None  # override; default per triage registry
    duration_minutes: float = 60.0
    jobs: int = 2
    slice_seconds: int = 60
    max_len: int = 4096
    seed_corpus: str = "corpus/bmp"
    dictionary: str | None = "harness/dicts/bmp.dict"
    output_dir: str = "campaigns"
    triage_on_finish: bool = True
    # scheduler
    stagnation_intervals: int = 5
    surge_threshold_per_hour: float = 3.0
    max_jobs: int = 4

    def validate(self) -> None:
        if self.jobs < 1:
            raise ValueError("jobs must be >= 1")
        if self.max_jobs < self.jobs:
            raise ValueError("max_jobs must be >= jobs")
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be > 0")
        if self.slice_seconds < 5:
            raise ValueError("slice_seconds must be >= 5")
        if self.max_len < 64:
            raise ValueError("max_len must be >= 64")
        if self.stagnation_intervals < 1:
            raise ValueError("stagnation_intervals must be >= 1")


def _coerce(value: str):
    v = value.strip().strip("'").strip('"')
    if v.lower() in ("true", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    if v.lower() in ("null", "none", "~"):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def _parse_fallback(text: str) -> dict:
    """Parse the documented config subset without PyYAML.

    Supports top-level sections (`campaign:` / `scheduler:`) whose
    values are `key: scalar` lines indented by two spaces, plus flat
    top-level keys. Comments and blank lines are skipped.
    """
    root: dict = {}
    section: dict | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" "):
            key, _, val = line.partition(":")
            if val.strip():
                root[key.strip()] = _coerce(val)
                section = None
            else:
                section = {}
                root[key.strip()] = section
        else:
            if section is None:
                raise ValueError(f"indented line without section: {raw!r}")
            key, _, val = line.strip().partition(":")
            section[key.strip()] = _coerce(val)
    return root


def _flatten(raw: dict) -> dict:
    flat = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            flat.update(val)
        else:
            flat[key] = val
    return flat


_KNOWN_KEYS = {f.name for f in CampaignConfig.__dataclass_fields__.values()}


def load_config(path: str | Path) -> CampaignConfig:
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-not-found]
        raw = yaml.safe_load(text) or {}
    except ImportError:
        raw = _parse_fallback(text)
    flat = _flatten(raw)
    unknown = set(flat) - _KNOWN_KEYS
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")
    cfg = CampaignConfig(**{k: v for k, v in flat.items()
                            if k in _KNOWN_KEYS})
    cfg.validate()
    return cfg
