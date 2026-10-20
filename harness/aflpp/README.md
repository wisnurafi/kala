# AFL++ harnesses

libFuzzer is Kala's campaign engine, and every shipped target uses
it. This directory holds the AFL++ side: no AFL++ harness ships
today, because no target has needed one yet — when one does, it
follows the conventions below and plugs into the same corpora,
dictionaries and triage pipeline (libFuzzer and AFL++ artifact
formats are both understood by `triage/ingest.py`).

Conventions for this directory:

- A harness is a `main()` that reads input from stdin or from the
  file in `argv[1]`, per AFL++ convention.
- Persistent mode is mandatory for real campaigns
  (`__AFL_LOOP(1000)` with `afl-clang-fast++`); a fork-mode-only
  harness runs 10–50x slower.
- Shared setup goes in one-time init guarded by `__AFL_INIT()`.
- Same portability rules as everywhere else: standard C/C++ and
  POSIX only, no platform APIs.
- The target must be built with an AFL++ instrumenting compiler
  for the campaign; the CMake presets build libFuzzer binaries,
  so an AFL++ build is a separate build tree.
