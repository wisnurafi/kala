# inih — first real target (private validation)

Vendored snapshot of [benhoyt/inih](https://github.com/benhoyt/inih),
a small INI file parser in C (`ini.c` + `ini.h`, "a couple of pages
of code"), BSD-3-Clause — see `LICENSE.txt`.

- **Pinned commit:** `2bbdec4a366c8c39746ee0982e7ca0febbb044b6`
  ("Expose INI_MAX_SECTION and INI_MAX_NAME in ini.h (#215)",
  2026-09-27). Snapshot vendoring, not a submodule: the pinned
  files are what was reviewed, and they cannot drift.
- **Files are unmodified upstream.** Kala-side configuration lives
  in `CMakeLists.txt` and the harness, never in the vendored code.
- **Security contact:** upstream has no `SECURITY.md` (checked at
  the repo root and `.github/` on the pinned commit). Any finding
  follows `docs/responsible-disclosure.md` via the maintainer's
  GitHub contact, privately, before anything is published.

## Configuration under test

inih's behavior is largely compile-time defines. The defaults
(stack line buffer, no realloc) are also its most-audited path, so
the target builds the configuration real embedders pick for long
lines:

- `INI_USE_STACK=0` — line buffer on the heap
- `INI_ALLOW_REALLOC=1` — the buffer grows by realloc as lines get
  longer (initial allocation `INI_INITIAL_ALLOC`, default 200)

Section/name limits stay at the upstream defaults
(`INI_MAX_SECTION` / `INI_MAX_NAME`, 50).

## Harness

`harness/libfuzzer/inih_fuzzer.cpp` feeds the raw input to
`ini_parse_string_length()` (length-based; embedded NULs are data,
not terminators). The handler walks every section/name/value the
parser produces and folds them into a checksum — it stores nothing,
so anything that crashes is the parser's, not the harness's.

Seeds: `corpus/inih/` (hand-written valid files covering sections,
comments, multi-line values, `name: value`, quoted values, BOM).
Dictionary: `harness/dicts/ini.dict`.

## Validation

`kala run` finds ≥1 genuine crash, **or** a 24-hour clean campaign
with rising coverage, documented in `docs/calibration-notes.md`.
Upstream ships its own fuzz harness (`fuzzing/inihfuzz.c`), so a
clean result is a plausible and respectable outcome; a crash gets
verified by hand (clean reproduction, root cause) and handled per
the disclosure doc — its PoC does **not** enter
`corpus/regression/` while unpatched.
