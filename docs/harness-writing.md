# Writing a harness

A harness is the thin layer between the fuzzer and the code under
test. This guide is the checklist distilled from the hello target
and `bmp_parser` (Phases 0–1), in the order the mistakes were
actually made.

## The contract

```c
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size < MIN_INPUT || size > MAX_INPUT) return 0;
    target_parse(data, size);
    return 0;
}
```

Rules that are not negotiable:

- **Parse from memory.** The entry point takes `(data, size)`; file
  I/O belongs in standalone drivers (`bmp_dump.c` style), not in
  the fuzz path.
- **Guard the size.** Reject inputs that are obviously too small or
  absurdly large before calling the target — cycles spent on inputs
  the parser rejects in its first check are wasted, but keep the
  guard *looser* than the parser's own validation or you will
  fence off the interesting paths.
- **Free what the target allocates** (or deliberately leak-check in
  a separate profile), otherwise LeakSanitizer drowns real crashes
  in leak reports.
- **No platform APIs.** C11 / C++17 + POSIX only (the cross-platform
  rules in the root README). No
  `windows.h`, no compiler extensions. CI greps for this.

## Build wiring

- Compile the *target* code with `-fsanitize=fuzzer-no-link` when
  it links into a libFuzzer binary. Skipping this was the single
  most expensive calibration mistake: the fuzzer ran, but coverage was
  blind (3 PCs, cov 2) and the planted crash took 23.69 s instead
  of 0.07 s.
- Build through the CMake presets (`asan`, `asan-ubsan`,
  `fuzzer-asan-ubsan`) so the harness, the target, and CI all use
  identical flags.
- Keep the harness file next to the other harnesses:
  `harness/libfuzzer/<name>_fuzzer.cpp`, target under
  `targets/<name>/`, and register a default binary for the target
  in `triage/cli.py` (`_DEFAULT_BINARIES`) so `kala triage --target
  <name>` just works.

## Seeds and dictionary

- **Seeds: 5–10 valid files**, generated from the format spec or
  the project's own test corpus — for bmp_parser, Pillow-generated
  BMPs covering the bpp/compression variants the parser accepts.
  Near-miss seeds (valid header, truncated body) are welcome; pure
  random bytes are not a corpus.
- **One lineage can matter more than a big corpus.** The easy bug
  in a mixed corpus kills almost every process within ~25
  executions and starves the rare bugs. When hunting a specific
  path, run a focused loop seeded with only the lineage that
  reaches it.
- **Dictionary: tokens + boundary values.** Magic bytes and chunk
  names, plus the numbers random mutation will never assemble:
  2^31/2^30-scale dimensions, 0, 255/256/257 for count fields.
  The calibration integer-overflow bug fell to a dictionary boundary
  token, not to luck.

## Before you fuzz: verify by hand

Write deterministic trigger inputs for any bug you *expect* the
harness to find (planted or suspected) and replay them first.
The calibration generator caught two manifestation surprises before
the campaign started — an integer overflow that reports SEGV rather
than a clean heap-buffer-overflow, and a stack overflow that only
UBSan's bounds check reports under the combined profile. A campaign
scored against unverified ground truth misclassifies both.

## When the fuzzer finds nothing

In order:

1. Sanitizer really linked? (Replay a known-bad input; no ASan
   banner = no instrumentation.)
2. Coverage moving at all? Flat coverage + valid seeds = the
   harness rejects too early or the target was built without
   `fuzzer-no-link` (see above).
3. Symbolizer present? Without it you may be crashing and not
   *seeing* attributable traces (see `setup.md` §5).
4. Dictionary loaded? (`-dict=` in the invocation, file exists.)
5. Input size cap (`-max_len`) cutting off the format's valid
   range?
