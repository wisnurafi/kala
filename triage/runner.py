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
    """Replay one input with a hard timeout.

    The child runs in its own session so a timeout can kill the
    whole process group; if it still does not reap within a grace
    period (e.g. stuck in uninterruptible I/O), the replay is
    abandoned and reported as a timeout rather than hanging the
    whole triage/campaign on one pathological input.
    """
    import os
    import signal

    proc = subprocess.Popen(
        [str(binary), str(crash_file)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=env, errors="replace", start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
        return ReplayResult(proc.returncode, (out or "") + (err or ""),
                            False)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        try:
            out, err = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        return ReplayResult(-1, (out or "") + (err or ""), True)
