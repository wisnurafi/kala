# Sanitizer profiles

Select a profile at configure time:

```sh
cmake -S . -B build -DKALA_SANITIZER=asan-ubsan
```

| Profile | CMake value | Flags | Use when |
|---|---|---|---|
| None | `none` | — | Plain build, debugging the harness itself |
| ASan | `asan` | `-fsanitize=address` | Memory corruption: heap/stack buffer overflow, use-after-free, double-free |
| ASan + UBSan | `asan-ubsan` | `-fsanitize=address,undefined` | Default campaign profile. Adds integer overflow, null deref, misaligned access and other UB |
| MSan | `msan` | `-fsanitize=memory` | Later phase. Uninitialized-memory reads; clang/Linux only, needs an instrumented libc++ for clean results |

All profiles add `-fno-omit-frame-pointer -g` so ASan stack traces carry
usable function names for triage.

Recommended runtime options for campaigns (collect every distinct crash
instead of stopping at the first one where the fuzzer allows it):

```sh
export ASAN_OPTIONS=detect_leaks=1:halt_on_error=0:abort_on_error=1
export UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1
```
