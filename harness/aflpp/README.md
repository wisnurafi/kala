# AFL++ harnesses

Placeholder in Phase 0 — libFuzzer is the Phase 0 engine. AFL++ harnesses
land when a target needs AFL++ (Phase 1+ as needed).

Conventions for this directory:

- A harness is a `main()` that reads input from stdin or from the file in
  `argv[1]`, per AFL++ convention.
- Persistent mode is mandatory for real campaigns (`__AFL_LOOP(1000)` with
  `afl-clang-fast++`); a fork-mode-only harness runs 10–50x slower.
- Shared setup goes in `LLVMFuzzerInit`-equivalent one-time init guarded
  by `__AFL_INIT()`.
- Same portability rules as everywhere else: standard C/C++ and POSIX
  only, no platform APIs.
