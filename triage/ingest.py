"""Collect crash artifacts from a fuzzer output directory.

Understands libFuzzer artifact names (crash-*, leak-*, oom-*,
timeout-*) and AFL++ output (files named id:* — a flat directory, or
an AFL output tree whose crashes live in a `crashes/` subdirectory).
With all_files=True every regular file is ingested; that is for
hand-assembled directories such as regression corpora.

Standard library only.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

_LIBFUZZER_PREFIXES = ("crash-", "leak-", "oom-", "timeout-")


@dataclass
class CrashRecord:
    path: Path
    size: int
    sha256: str
    source: str  # libfuzzer | aflpp | file


def _record(path: Path, source: str) -> CrashRecord:
    data = path.read_bytes()
    return CrashRecord(path=path, size=len(data),
                       sha256=hashlib.sha256(data).hexdigest(),
                       source=source)


def _classify_name(name: str) -> str | None:
    if name.startswith(_LIBFUZZER_PREFIXES):
        return "libfuzzer"
    if name.startswith("id:") or name.startswith("id_"):
        return "aflpp"
    return None


def ingest_dir(crash_dir: str | Path, all_files: bool = False
               ) -> list[CrashRecord]:
    """Return crash records sorted by path (deterministic order)."""
    root = Path(crash_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")
    candidates: list[Path] = []
    for entry in sorted(root.iterdir()):
        if entry.is_dir() and entry.name == "crashes":
            candidates.extend(sorted(entry.iterdir()))
        elif entry.is_file():
            candidates.append(entry)
    records = []
    for path in candidates:
        if not path.is_file():
            continue
        source = _classify_name(path.name)
        if source is None:
            if not all_files:
                continue
            source = "file"
        records.append(_record(path, source))
    records.sort(key=lambda r: str(r.path))
    return records
