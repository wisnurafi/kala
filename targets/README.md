# Targets

Everything Kala fuzzes lives here. Two kinds of target:

- **Practice target** — written for Kala, with bugs planted on
  purpose, so the pipeline is calibrated against known ground truth.
- **Real targets** — open-source parsers vendored unmodified at a
  pinned commit. Their vendored files are read-only; configuration
  lives in the target's `CMakeLists.txt`, adaptation in the harness.

## bmp_parser — practice / calibration

`bmp_parser/` — a minimal BMP parser in C with 5 planted bug
classes. The fuzzer finds 5/5 of them; their PoCs are permanent
regression tests in `corpus/regression/bmp_parser/` (see
`docs/calibration-notes.md` for the full calibration record):

1. Heap buffer overflow (out-of-bounds read)
2. Stack buffer overflow
3. Integer overflow leading to under-allocation
4. Use-after-free on an error path
5. Out-of-bounds read via a header offset

Its `PLANTED_BUGS.md` is the answer key the calibration is scored
against — do not open it during a triage validation run.

## inih — real target (vendored)

`inih/` — [benhoyt/inih](https://github.com/benhoyt/inih), a small
INI parser in C, vendored at `2bbdec4` (BSD-3) in the heap
line-buffer configuration (`INI_USE_STACK=0`,
`INI_ALLOW_REALLOC=1`). A 24-hour validation campaign runs on the
fuzzing VM (`examples/campaign-inih.yaml`).

## tomlc17 — real target (vendored)

`tomlc17/` — [cktan/tomlc17](https://github.com/cktan/tomlc17), a
TOML v1.1 parser in C, vendored at `85000d0` (MIT) in upstream
default configuration. A 48-hour hunt campaign runs on the fuzzing
VM (`examples/campaign-tomlc17.yaml`); findings follow
`docs/responsible-disclosure.md`, and a PoC for an unpatched bug
never enters this repository.

## Adding a target

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the vendoring
rules and [`docs/harness-writing.md`](../docs/harness-writing.md)
for harness design.
