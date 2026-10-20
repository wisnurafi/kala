"""kala command line interface.

    kala triage <crash-dir> --target bmp_parser [--bin PATH]
                [--out report.html] [--work-dir triage-work]
                [--minimize-time 10] [--timeout 10] [--all]
    kala run --config examples/campaign.yaml [--bin PATH]
    kala status [--config examples/campaign.yaml | <campaign-dir>]
    kala regress <poc> --target bmp_parser --name bugN_name
                --expect-class <class> [--expect-function <fn>]
                --bug "..." --expected "..." --trigger "..."

`triage` is Phase 2; `run`/`status` drive Phase 3 campaigns.

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
from .runner import find_symbolizer, replay_classified, replay_env

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_BINARIES = {
    "bmp_parser": "build-fuzzer/harness/libfuzzer/bmp_fuzzer",
    "hello": "build-fuzzer/harness/libfuzzer/hello_fuzzer",
    "inih": "build-fuzzer/harness/libfuzzer/inih_fuzzer",
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
        print("warning: no addr2line or llvm-symbolizer in PATH; "
              "sanitizer traces will not be symbolized", file=sys.stderr)

    analyzed: list[AnalyzedCrash] = []
    for i, record in enumerate(records, 1):
        result = replay_classified(binary, record.path,
                                   timeout=args.timeout, env=env)
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


def cmd_regress(args: argparse.Namespace) -> int:
    from .regress import RegressError, add_regression_poc

    binary = _resolve_binary(args.target, args.bin)
    if not binary.is_file():
        raise SystemExit(
            f"target binary not found: {binary}\n"
            "Build it first, e.g.: cmake --preset fuzzer-asan-ubsan && "
            "cmake --build --preset fuzzer-asan-ubsan")
    symbolizer = find_symbolizer()
    env = replay_env(symbolizer)
    regression_dir = _REPO_ROOT / "corpus" / "regression" / args.target
    try:
        dest = add_regression_poc(
            binary, Path(args.poc), regression_dir, name=args.name,
            expect_class=args.expect_class,
            expect_function=args.expect_function, bug=args.bug,
            expected=args.expected, trigger=args.trigger, env=env,
            timeout=args.timeout, force=args.force)
    except RegressError as exc:
        raise SystemExit(f"regress: {exc}") from exc
    print(f"added {dest.relative_to(_REPO_ROOT)} "
          f"(verified: {args.expect_class}"
          f"{' @ ' + args.expect_function if args.expect_function else ''})")
    print("README table updated — remember to register the PoC in "
          "tools/check_regression.py so CI replays it")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    from orchestrate.config import load_config
    from orchestrate.runner import Campaign

    cfg_path = Path(args.config)
    if not cfg_path.is_file() and (_REPO_ROOT / args.config).is_file():
        cfg_path = _REPO_ROOT / args.config
    try:
        cfg = load_config(cfg_path)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"config error: {exc}") from exc
    binary = _resolve_binary(cfg.target, args.bin or cfg.binary)
    if not binary.is_file():
        raise SystemExit(
            f"target binary not found: {binary}\n"
            "Build it first, e.g.: cmake --preset fuzzer-asan-ubsan && "
            "cmake --build --preset fuzzer-asan-ubsan")
    return Campaign(cfg, _REPO_ROOT, binary).run()


def cmd_status(args: argparse.Namespace) -> int:
    from orchestrate.runner import load_state
    from orchestrate.status import render_status

    if args.config:
        from orchestrate.config import load_config
        cfg_path = Path(args.config)
        if not cfg_path.is_file() and (_REPO_ROOT / args.config).is_file():
            cfg_path = _REPO_ROOT / args.config
        cfg = load_config(cfg_path)
        campaign_dir = _REPO_ROOT / cfg.output_dir / cfg.name
    else:
        campaign_dir = Path(args.campaign)
    state = load_state(campaign_dir)
    if state is None:
        raise SystemExit(f"no campaign state in {campaign_dir}")
    print(render_status(state), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ("triage", "run", "status", "regress",
                                "-h", "--help"):
        argv.insert(0, "triage")  # `kala <crash-dir>` convenience
    parser = argparse.ArgumentParser(
        prog="kala", description="Kala vulnerability discovery toolkit")
    sub = parser.add_subparsers(dest="command")
    r = sub.add_parser("run", help="run or resume a fuzzing campaign")
    r.add_argument("--config", required=True,
                   help="campaign YAML config (e.g. examples/campaign.yaml)")
    r.add_argument("--bin", default=None,
                   help="path to the instrumented target binary")
    g = sub.add_parser("regress",
                       help="promote a verified PoC into "
                            "corpus/regression/<target>/")
    g.add_argument("poc", help="the crash input to promote")
    g.add_argument("--target", default="bmp_parser",
                   help="target name (default: bmp_parser)")
    g.add_argument("--bin", default=None,
                   help="path to the instrumented target binary")
    g.add_argument("--name", required=True,
                   help="file stem for the PoC, e.g. bug6_oob_example")
    g.add_argument("--expect-class", required=True,
                   help="bug class the replay must prove, "
                        "e.g. heap-buffer-overflow")
    g.add_argument("--expect-function", default=None,
                   help="top application function the replay must show")
    g.add_argument("--bug", required=True,
                   help="README 'Bug' cell, e.g. '6 — OOB read, example'")
    g.add_argument("--expected", required=True,
                   help="README 'Expected report' cell")
    g.add_argument("--trigger", required=True,
                   help="README 'Trigger' cell, one line")
    g.add_argument("--timeout", type=float, default=15,
                   help="replay timeout in seconds (default: 15)")
    g.add_argument("--force", action="store_true",
                   help="replace an existing file with the same name")
    s = sub.add_parser("status", help="show campaign status")
    s.add_argument("campaign", nargs="?", default=None,
                   help="campaign directory (or use --config)")
    s.add_argument("--config", default=None,
                   help="campaign YAML config to locate the campaign")
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
    if args.command == "run":
        return cmd_run(args)
    if args.command == "regress":
        return cmd_regress(args)
    if args.command == "status":
        return cmd_status(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
