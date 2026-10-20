# Kala

Vulnerability discovery toolkit: a fuzzing harness and triage pipeline that
breaks software systematically to find security bugs before someone else does.

Kala combines coverage-guided fuzzers (libFuzzer, AFL++) with sanitizers
(ASan/UBSan) and a Python triage pipeline that turns raw crashes into
deduplicated, minimized, classified reports.

> Named after Kala, the Javanese deity of destruction and time.

## Status

Phase 1 — calibration complete: the `bmp_parser` practice target's five
planted bug classes were all found by the fuzzer (L1), each with a PoC
in `corpus/regression/bmp_parser/`. See `docs/calibration-notes.md`.
Next is Phase 2, the triage toolkit.

## Success levels

| Level | Proof |
|---|---|
| L1 — Pipeline valid | Finds 100% of deliberately planted bugs in the practice target |
| L2 — Automatic triage | 50 raw crashes become at most 5 clean reports, no manual work |
| L3 — Autonomous campaign | Overnight fuzzing runs unattended, results are triaged by morning |
| L4 — Regression lab | Every found bug becomes a permanent test; CI fuzzes on every push |
| L5 — Real finding | Valid bug in an open-source library, responsibly disclosed (CVE target) |

L3 is not started before L1–L2 are solid.

## Layout

```
harness/
  libfuzzer/    libFuzzer harnesses (LLVMFuzzerTestOneInput)
  aflpp/        AFL++ harnesses (stdin/file, persistent mode)
  sanitizers/   CMake sanitizer profiles: asan, asan-ubsan, msan
  dicts/        Token dictionaries per file format
targets/        Practice targets with planted bugs (Phase 1: bmp_parser)
corpus/
  hello/        Seed corpus for the hello-world harness
  regression/   Minimized PoCs that become permanent regression tests
triage/         Python: ingest -> dedup -> minimize -> classify -> report
orchestrate/    Python: campaign manager (YAML, multi-core, watchdog)
docker/         Reproducible fuzzing environment (alternative to the VM)
docs/           Setup, harness writing, triage and disclosure guides
```

## Quick start (Linux VM)

Development happens on Windows; building and fuzzing happen on a Debian/Ubuntu
VM (or in Docker). The code is portable by rule — see Cross-platform below.

Build the hello-world fuzzer with clang:

```sh
cmake -S . -B build-fuzzer \
  -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
  -DKALA_SANITIZER=asan-ubsan -DKALA_ENABLE_LIBFUZZER=ON
cmake --build build-fuzzer -j
```

Run it against the seed corpus with the dictionary:

```sh
mkdir -p findings-hello
./build-fuzzer/harness/libfuzzer/hello_fuzzer findings-hello corpus/hello \
  -dict=harness/dicts/hello.dict -max_total_time=60
```

The hello target crashes on purpose once the fuzzer discovers the magic
pattern in `kala_hello_parse()` — finding that crash in under 60 seconds is
the Phase 0 gate.

Direct clang build (no CMake) also works:

```sh
clang++ -std=c++17 -g -O1 -fno-omit-frame-pointer \
  -fsanitize=fuzzer,address,undefined \
  harness/libfuzzer/hello_fuzzer.cpp harness/libfuzzer/hello_parse.cpp \
  -o hello_fuzzer
```

## Cross-platform rules

Strict, from day one (roadmap section 9):

- C11 / C++17 standard only, plus POSIX. No `windows.h`, no Win32 API, no
  MSVC extensions.
- CMake is the only build system; clang is the compiler.
- LF line endings and UTF-8 everywhere (enforced by `.gitattributes`).
- No hardcoded Windows paths or backslash separators.

Check before every milestone:

```sh
grep -rn "windows.h" --include="*.c" --include="*.h" \
  --include="*.cpp" --include="*.hpp" .
# must print nothing
```

## Rules of engagement

- Only fuzz code you wrote, open-source code, or targets with explicit
  permission.
- Fuzz inside the Linux VM (or Docker/WSL2) — never on the main host or a
  work network.
- Real bugs are disclosed privately to the maintainer first, with a 90-day
  window before any publication. Never push a PoC for an unpatched bug.

## Roadmap

- [x] M0: Repo scaffold + hello-world harness fuzzed (Phase 0)
- [x] M1: 5/5 planted bugs found in `bmp_parser` (Phase 1) — main gate
- [ ] M2: `kala triage` report matches the planted-bug answer key (Phase 2)
- [ ] M3: 48h autonomous campaign on a real target (Phase 3)
- [ ] M4: CI regression green (Phase 4)
- [ ] M5: Valid report accepted by a maintainer (Phase 5)
