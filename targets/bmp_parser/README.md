# bmp_parser — Phase 1 calibration target

A minimal BMP parser in C (BITMAPINFOHEADER layout, 8/16/24/32 bpp,
BI_RGB and BI_RLE8). It parses well-formed files correctly, and it
contains five deliberately planted bug classes documented in
`PLANTED_BUGS.md` — **the answer key; do not open it during a triage
validation run.**

## Files

- `bmp_parser.c` / `bmp_parser.h` — the parser.
- `bmp_dump.c` — standalone driver: parse one file, print a summary.
  Built as `bmp_dump`; the fastest way to check one input by hand.
- `gen_pocs.py` — one deterministic trigger input per planted bug.
  Run these before fuzzing: if a PoC does not produce its documented
  sanitizer report, the target's ground truth is wrong and the
  campaign would calibrate against a lie.
- `PLANTED_BUGS.md` — answer key (class, location, mechanism).

## Build & check by hand

```sh
cmake --preset asan-ubsan && cmake --build --preset asan-ubsan
python3 targets/bmp_parser/gen_pocs.py /tmp/pocs
./build-asan-ubsan/targets/bmp_parser/bmp_dump /tmp/pocs/poc1_oob_read.bmp
# expect: AddressSanitizer heap-buffer-overflow in copy_rows
```

## Fuzz it

```sh
cmake --preset fuzzer-asan-ubsan && cmake --build --preset fuzzer-asan-ubsan
mkdir -p findings-bmp
./build-fuzzer/harness/libfuzzer/bmp_fuzzer findings-bmp corpus/bmp \
  -dict=harness/dicts/bmp.dict -max_len=4096
```

Fuzzer-found PoCs for the five classes live in
`corpus/regression/bmp_parser/` once the calibration campaign has run
(see `docs/calibration-notes.md`).
