# libFuzzer harnesses

Each harness exposes the standard entry point:

```cpp
extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);
```

Harness rules:

- Cap the input size and early-exit on inputs that are clearly invalid,
  so the fuzzer does not waste executions.
- Keep the harness thin: parse/dispatch only, the target does the work.
- No platform-specific APIs (roadmap section 9) — standard C++ and POSIX
  only.

## hello_fuzzer (Phase 0)

`hello_fuzzer.cpp` wraps `kala_hello_parse()` (`hello_parse.cpp`), a dummy
parser with one planted heap-buffer-overflow behind the 4-byte magic
`FUZZ`. Finding that crash in under 60 seconds is the Phase 0 gate.

Build and run:

```sh
cmake -S . -B build-fuzzer --preset fuzzer-asan-ubsan  # or see root README
cmake --build build-fuzzer -j
mkdir -p findings-hello
./build-fuzzer/harness/libfuzzer/hello_fuzzer findings-hello corpus/hello \
  -dict=harness/dicts/hello.dict -max_total_time=60
```
