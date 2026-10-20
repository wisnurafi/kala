"""kala command line interface.

    kala triage <crash-dir> --target bmp_parser [--bin PATH]
                [--out report.html] [--work-dir triage-work]
                [--minimize-time 10] [--timeout 10] [--all]

Phase 2 ships `triage`; the subcommand layout leaves room for the
Phase 3 `run` (campaign orchestration) without reshaping the CLI.

Standard library only; paths via pathlib, subprocess via argument
lists (roadmap section 9).
"""

import argparse
import sys
from pathlib import Path

from .classify import parse_sanitizer_output
from .dedup import AnalyzedCrash, group_crashes
from .ingest import ingest_dir
from .minimize import minimize_crash
from .report import ReportMeta, render_report
from .runner import find_symbolizer, replay, replay_env

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_BINARIES = {
    "bmp_parser": "build-fuzzer/harness/libfuzzer/bmp_fuzzer",
    "hello": "build-fuzzer/harness/libfuzzer/hello_fuzzer",
}


def _resolve_binary(target: str, bin_arg: str | None) -> Path:
    if bin_arg:
        return Path(bin_arg)
    rel = _DEFAULT_BINARIES.get(target)
    if rel is None:
        raise SystemExit(
            f"unknown target '{target}' (known: "
            f"{', '.join(sorted(_DEFAULT_BINARIES))}); pass --bin")
    return _REPO_ROOT / rel


def cmd_triage(args: argparse.Namespace) -> int:
    binary = _resolve_binary(args.target, args.bin)
    if not binary.is_file():
        raise SystemExit(
            f"target binary not found: {binary}\n"
            "Build it first, e.g.: cmake --preset fuzzer-asan-ubsan && "
            "cmake --build --preset fuzzer-asan-ubsan")
    try:
        records = ingest_dir(args.crash_dir, all_files=args.all)
    except NotADirectoryError as exc:
        raise SystemExit(str(exc)) from exc
    if not records:
        raise SystemExit(
            f"no crash artifacts found in {args.crash_dir} "
            "(libFuzzer crash-*/leak-*/oom-*/timeout-* or AFL++ id:*; "
            "pass --all to ingest every file)")

    symbolizer = find_symbolizer()
    env = replay_env(symbolizer)
    if symbolizer is None:
        print("warning: no llvm-symbolizer or addr2line in PATH; "
              "sanitizer traces will not be symbolized", file=sys.stderr)

    analyzed: list[AnalyzedCrash] = []
    for i, record in enumerate(records, 1):
        result = replay(binary, record.path, timeout=args.timeout, env=env)
        info = parse_sanitizer_output(result.output, result.exit_code,
                                       result.timed_out)
        analyzed.append(AnalyzedCrash(record=record, info=info))
        if i % 25 == 0 or i == len(records):
            print(f"  replayed {i}/{len(records)}", file=sys.stderr)

    groups, non_crashing = group_crashes(analyzed)
    symbolized = any(a.info.symbolized for a in analyzed
                     if a.info.kind != "no-crash")

    work_dir = Path(args.work_dir)
    for idx, group in enumerate(groups, 1):
        rep = group.representative
        if args.minimize_time > 0:
            minimized, note = minimize_crash(
                binary, rep.record.path,
                work_dir / "minimized" / f"g{idx}",
                budget_s=args.minimize_time, env=env, original=rep.info)
            group.minimized_path = minimized  # type: ignore[attr-defined]
            group.minimize_note = note  # type: ignore[attr-defined]
        else:
            group.minimized_path = None  # type: ignore[attr-defined]
            group.minimize_note = "disabled"  # type: ignore[attr-defined]

    meta = ReportMeta(target=args.target, binary_name=binary.name,
                      total_inputs=len(records),
                      crashing_inputs=len(records) - len(non_crashing),
                      non_crashing=len(non_crashing),
                      symbolized=symbolized)
    out_path = Path(args.out)
    out_path.write_text(render_report(groups, meta), encoding="utf-8")

    print(f"\n{len(records)} inputs -> {len(groups)} unique groups "
          f"({len(non_crashing)} non-crashing)")
    for idx, group in enumerate(groups, 1):
        loc = group.location
        loc_text = f"{loc.function}:{loc.line}" if loc else "?"
        print(f"  G{idx} {group.bug_class} "
              f"({group.direction or '-'}) @ {loc_text} "
              f" x{len(group.members)}  [{group.stack_hash}]  "
              f"{group.minimize_note}")  # type: ignore[attr-defined]
    print(f"report: {out_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("triage", "-h", "--help"):
        argv.insert(0, "triage")  # `kala <crash-dir>` convenience
    parser = argparse.ArgumentParser(
        prog="kala", description="Kala vulnerability discovery toolkit")
    sub = parser.add_subparsers(dest="command")
    t = sub.add_parser("triage", help="triage a directory of raw crashes")
    t.add_argument("crash_dir", help="directory of fuzzer crash artifacts")
    t.add_argument("--target", default="bmp_parser",
                   help="target name (default: bmp_parser)")
    t.add_argument("--bin", default=None,
                   help="path to the instrumented target binary")
    t.add_argument("--out", default="report.html",
                   help="report output path (default: report.html)")
    t.add_argument("--work-dir", default="triage-work",
                   help="scratch dir for minimization (default: triage-work)")
    t.add_argument("--minimize-time", type=int, default=10,
                   help="per-group minimization budget in seconds "
                        "(0 disables; default: 10)")
    t.add_argument("--timeout", type=float, default=10,
                   help="per-input replay timeout in seconds (default: 10)")
    t.add_argument("--all", action="store_true",
                   help="ingest every file, not only fuzzer-named ones")
    args = parser.parse_args(argv)
    if args.command == "triage":
        return cmd_triage(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
