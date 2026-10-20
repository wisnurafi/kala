# Contributing to Kala

Thanks for your interest. Kala is a fuzzing toolkit: a C/C++
harness layer (libFuzzer + sanitizers) plus a Python triage and
campaign-orchestration layer. This guide covers setup, the rules
that keep the toolkit trustworthy, and what a good change looks
like.

## Getting started

You need a Linux environment (a VM or the Docker image in
`docker/`) — development happens on the host, building and fuzzing
happen in the VM. Full instructions: [`docs/setup.md`](docs/setup.md).

```sh
cmake --preset fuzzer-asan-ubsan
cmake --build --preset fuzzer-asan-ubsan -j
python3 -m unittest discover -s triage/tests -t .
python3 -m unittest discover -s orchestrate/tests -t .
python3 tools/check_regression.py
```

All five steps must pass before a change is proposed. CI runs the
same checks on every push.

## Hard rules

- **Cross-platform by construction.** C11 / C++17 + POSIX only.
  No `windows.h`, no Win32 API, no compiler extensions, no
  hardcoded platform paths. CMake + clang are the only build
  system and compiler. LF line endings, UTF-8.
- **Python is standard-library only.** The triage/orchestrate
  layer must run in a throwaway VM with zero installs (PyYAML is
  the one tolerated optional dependency, with a built-in fallback
  parser). Subprocesses are always invoked with argument lists,
  never through a shell.
- **Vendored targets are read-only.** Files under
  `targets/inih/` and `targets/tomlc17/` are byte-identical
  snapshots of upstream at a pinned commit — never edit them.
  Configuration goes in that target's `CMakeLists.txt`, adaptation
  goes in the harness. Bumping a pin is its own change, with the
  new commit hash and blob verification recorded in the target's
  README.
- **Never commit a PoC for an unpatched bug.** Confirmed crashes
  in third-party targets follow
  [`docs/responsible-disclosure.md`](docs/responsible-disclosure.md);
  their artifacts live outside this repository until a fix is out.
- **Seeds stay valid.** Every file in `corpus/<target>/` must parse
  cleanly under a sanitizer build — a crashing seed invalidates
  the baseline for everyone.

## Adding a target

The short version (full guide: [`docs/harness-writing.md`](docs/harness-writing.md)):

1. Vendor the source, unmodified, at a pinned commit under
   `targets/<name>/`, with its license file and a README recording
   the pin, the configuration under test, and the upstream
   security contact.
2. Write a thin harness in `harness/libfuzzer/` — length-based
   API, stateless handler, capped input size. Target code always
   builds with `-fsanitize=fuzzer-no-link` under libFuzzer, or
   coverage stays blind.
3. Add hand-written valid seeds in `corpus/<name>/` and a token
   dictionary in `harness/dicts/` (non-printable bytes as `\xNN`
   only — libFuzzer's dictionary parser rejects `\r`/`\n`/`\t`
   escapes, and the symptom is a campaign that "completes" with
   zero executions).
4. Register the target in `targets/CMakeLists.txt`,
   `harness/libfuzzer/CMakeLists.txt` and
   `triage/cli.py`'s `_DEFAULT_BINARIES`; add a campaign config
   in `examples/`.
5. Smoke first: seed replay clean, executions > 0, coverage
   rising. Zero executions always means "audit the harness", never
   "target is clean".

## Commits and pull requests

- One logical change per commit, conventional-commit style
  (`feat(targets): …`, `fix(triage): …`, `docs: …`).
- Say what you verified, with the numbers: test counts, execution
  counts, coverage, hashes. "It works" is not a verification.
- Keep the working tree clean of ad-hoc helper scripts and
  campaign output; both are git-ignored on purpose.
