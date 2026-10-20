# libFuzzer harnesses

One harness per target. Each exposes the standard entry point:

```cpp
extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size);
```

| Harness | Target | Notes |
|---|---|---|
| `hello_fuzzer` | `hello_parse` (in this directory) | Smoke test: a dummy parser with one planted heap-buffer-overflow behind the 4-byte magic `FUZZ`. A correct setup finds the crash in seconds — run this first on any new machine. |
| `bmp_fuzzer` | `targets/bmp_parser` | Calibration target; its 5 planted bugs are the pipeline's ground truth. |
| `inih_fuzzer` | `targets/inih` | Feeds `ini_parse_string_length()`; the handler stores nothing. |
| `tomlc17_fuzzer` | `targets/tomlc17` | Feeds `toml_parse()`, walks the result tree iteratively, always calls `toml_free()`. |

Harness rules:

- Cap the input size and early-exit on inputs that are clearly
  invalid, so the fuzzer does not waste executions.
- Keep the harness thin and stateless: parse/dispatch only, the
  target does the work. A crash must be the target's, never the
  harness's bookkeeping — walk result trees iteratively, free what
  the API says to free.
- The target code is built with `-fsanitize=fuzzer-no-link`
  (wired in each target's `CMakeLists.txt`); without it the engine
  receives no coverage feedback.
- No platform-specific APIs — standard C++ and POSIX only.

Build and run (example, the smoke test):

```sh
cmake --preset fuzzer-asan-ubsan
cmake --build --preset fuzzer-asan-ubsan -j
mkdir -p findings-hello
./build-fuzzer/harness/libfuzzer/hello_fuzzer findings-hello corpus/hello \
  -dict=harness/dicts/hello.dict -max_total_time=60
```

Full harness design guidance: [`docs/harness-writing.md`](../../docs/harness-writing.md).
