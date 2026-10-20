#!/usr/bin/env python3
"""Replay every regression PoC and check its documented report.

This is the regression lab's contract (Phase 4): each PoC in
corpus/regression/<target>/ must still crash with the bug class —
and, where the sanitizer trace names one, the top function — that
its README row documents. A PoC that stops crashing, or crashes
differently, fails the check and exits non-zero: that is the "bug
came back / behavior changed" alarm CI exists for.

    python3 tools/check_regression.py [--bin PATH]

Expectations live in EXPECTED below, one entry per PoC; the README
tables are the human-readable side of the same contract. When you
promote a PoC with `kala regress`, add its entry here too (the
command reminds you).

Standard library only; subprocess via argument lists (section 9).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from triage.classify import parse_sanitizer_output  # noqa: E402
from triage.runner import find_symbolizer, replay, replay_env  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

# file name -> (acceptable bug classes, top function or None).
# A set of classes because the same root cause can legitimately be
# reported two ways by the sanitizer (see triage.dedup's SEGV merge
# rule and the Phase 3 calibration notes on heap-layout costumes).
EXPECTED = {
    "bmp_parser": {
        "bug1_oob_read_fuzz.bmp":
            ({"heap-buffer-overflow"}, "copy_rows"),
        "bug2_stack_palette_fuzz.bmp":
            ({"stack-buffer-overflow"}, None),  # UBSan trace: no frames
        "bug3_int_overflow_fuzz.bmp":
            ({"SEGV-unknown"}, "copy_rows"),
        "bug4_uaf_rle_fuzz.bmp":
            ({"heap-use-after-free"}, "copy_rows"),
        "bug5_oob_palette_offset_fuzz.bmp":
            ({"heap-buffer-overflow"}, "parse_palette"),
    },
}

DEFAULT_BINARIES = {
    "bmp_parser": "build-fuzzer/harness/libfuzzer/bmp_fuzzer",
}


def check_target(target: str, binary: Path, env: dict) -> list[str]:
    failures = []
    reg_dir = REPO_ROOT / "corpus" / "regression" / target
    expected = EXPECTED.get(target, {})
    on_disk = {p.name for p in sorted(reg_dir.iterdir()) if p.is_file()
               and p.name != "README.md"}
    for name in sorted(on_disk - set(expected)):
        failures.append(f"{target}/{name}: in corpus but has no "
                        "expectation in tools/check_regression.py")
    for name, (classes, function) in sorted(expected.items()):
        path = reg_dir / name
        if not path.is_file():
            failures.append(f"{target}/{name}: expected PoC is missing")
            continue
        result = replay(binary, path, timeout=30, env=env)
        info = parse_sanitizer_output(result.output, result.exit_code,
                                      result.timed_out)
        if info.kind == "no-crash":
            failures.append(f"{target}/{name}: does NOT crash anymore")
        elif info.bug_class not in classes:
            failures.append(
                f"{target}/{name}: class {info.bug_class}, "
                f"expected one of {sorted(classes)}")
        elif function is not None and (
                info.location is None
                or info.location.function != function):
            got = info.location.function if info.location else None
            failures.append(
                f"{target}/{name}: top function {got}, "
                f"expected {function}")
        else:
            print(f"  ok {target}/{name}: {info.bug_class}"
                  f"{' @ ' + function if function else ''}")
    return failures


def main(argv: list[str]) -> int:
    bin_override = None
    if "--bin" in argv:
        bin_override = Path(argv[argv.index("--bin") + 1])
    symbolizer = find_symbolizer()
    if symbolizer is None:
        print("warning: no symbolizer found; function checks may fail",
              file=sys.stderr)
    env = replay_env(symbolizer)
    failures: list[str] = []
    for target in sorted(EXPECTED):
        binary = bin_override or REPO_ROOT / DEFAULT_BINARIES[target]
        if not binary.is_file():
            print(f"error: binary not found: {binary}\n"
                  "Build first: cmake --preset fuzzer-asan-ubsan && "
                  "cmake --build --preset fuzzer-asan-ubsan",
                  file=sys.stderr)
            return 2
        print(f"{target} (binary: {binary.name}):")
        failures += check_target(target, binary, env)
    if failures:
        print("\nREGRESSION CHECK FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  FAIL {failure}", file=sys.stderr)
        return 1
    print("\nAll regression PoCs reproduce as documented.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
