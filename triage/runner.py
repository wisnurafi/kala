"""Replay crash inputs through an instrumented binary.

The binary is expected to be a libFuzzer executable (running it on a
single file replays that input) — the same convention bmp_dump-style
drivers follow closely enough for exit-code purposes.

Symbolization matters: without an external symbolizer ASan prints
bare addresses and stack-trace triage goes blind (Phase 1 lesson, see
docs/calibration-notes.md). find_symbolizer() locates llvm-symbolizer
or falls back to addr2line, and the path is injected into
ASAN_OPTIONS unless the user already configured one.

Standard library only; subprocess is always called with an argument
list, never a shell string (roadmap section 9).
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_SYMBOLIZER_CANDIDATES = (
    "llvm-symbolizer", "llvm-symbolizer-21", "llvm-symbolizer-20",
    "llvm-symbolizer-19", "llvm-symbolizer-18", "llvm-symbolizer-17",
    "addr2line",
)


def find_symbolizer() -> str | None:
    for name in _SYMBOLIZER_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    return None


def replay_env(symbolizer: str | None) -> dict[str, str]:
    env = dict(os.environ)
    asan = env.get("ASAN_OPTIONS", "")
    if symbolizer and "external_symbolizer_path" not in asan:
        extra = f"external_symbolizer_path={symbolizer}"
        asan = f"{asan}:{extra}" if asan else extra
    if "abort_on_error" not in asan:
        asan = f"{asan}:abort_on_error=1" if asan else "abort_on_error=1"
    env["ASAN_OPTIONS"] = asan
    if "UBSAN_OPTIONS" not in env:
        env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    return env


@dataclass
class ReplayResult:
    exit_code: int
    output: str
    timed_out: bool


def replay(binary: str | Path, crash_file: str | Path, timeout: float,
           env: dict[str, str]) -> ReplayResult:
    try:
        proc = subprocess.run(
            [str(binary), str(crash_file)],
            capture_output=True, text=True, timeout=timeout, env=env,
            errors="replace",
        )
        return ReplayResult(proc.returncode,
                            (proc.stdout or "") + (proc.stderr or ""),
                            False)
    except subprocess.TimeoutExpired as exc:
        out = ""
        for chunk in (exc.stdout, exc.stderr):
            if chunk:
                out += chunk.decode(errors="replace") \
                    if isinstance(chunk, bytes) else chunk
        return ReplayResult(-1, out, True)
