"""Crash minimization via libFuzzer's -minimize_crash.

Results land in the artifact directory as `minimized-from-<hash>`
files — one per improvement step, so the smallest is the final
result. (Phase 2 calibration found this the hard way: an earlier
version globbed for `crash-*` and reported "no result" while the
minimizer had in fact shrunk a 163-byte PoC to 54 bytes.)

A minimized candidate is only accepted after a verification replay
proves it still crashes with the same class at the same location;
otherwise the caller keeps the original PoC and the report says so.
The budget is per internal minimization step; total wall-clock can
be a multiple of it.

An afl-tmin path would slot in here for AFL++ targets; it needs an
AFL-instrumented (non-libFuzzer) binary, which Kala does not build
yet, so libFuzzer minimization is the only backend for now.

Standard library only.
"""

import shutil
import subprocess
from pathlib import Path

from .classify import CrashInfo, parse_sanitizer_output
from .runner import replay


def minimize_crash(binary: str | Path, poc: Path, work_dir: Path,
                   budget_s: int, env: dict[str, str],
                   original: CrashInfo) -> tuple[Path | None, str]:
    """Try to shrink `poc`. Returns (minimized path or None, note)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    seed_copy = work_dir / "input.bin"
    shutil.copyfile(poc, seed_copy)
    try:
        subprocess.run(
            [str(binary), "-minimize_crash=1",
             f"-max_total_time={budget_s}",
             f"-artifact_prefix={work_dir}/", str(seed_copy)],
            capture_output=True, text=True, timeout=budget_s * 6 + 30,
            env=env, errors="replace",
        )
    except subprocess.TimeoutExpired:
        return None, f"minimizer exceeded its step budget ({budget_s}s)"
    produced = sorted(
        (p for pat in ("minimized-from-*", "crash-*")
         for p in work_dir.glob(pat)),
        key=lambda p: p.stat().st_size)
    if not produced:
        return None, f"minimizer produced no result within {budget_s}s/step"
    orig_loc = original.location.function if original.location else None
    for candidate in produced:
        if candidate.stat().st_size >= poc.stat().st_size:
            continue
        check = replay(binary, candidate, timeout=15, env=env)
        info = parse_sanitizer_output(check.output, check.exit_code,
                                       check.timed_out)
        new_loc = info.location.function if info.location else None
        if info.bug_class == original.bug_class and new_loc == orig_loc:
            return candidate, (f"{poc.stat().st_size} -> "
                               f"{candidate.stat().st_size} bytes")
    return None, "no minimized candidate kept the crash signature"
