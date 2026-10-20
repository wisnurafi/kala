# tomlc17 — first public target

Vendored snapshot of [cktan/tomlc17](https://github.com/cktan/tomlc17),
a lightweight, strictly compliant TOML v1.1 parser for C and C++
(`tomlc17.c` + `tomlc17.h`, two files, ~92 KB of C), MIT — see
`LICENSE`.

- **Pinned commit:** `85000d0836ce6089065b4241220e1e6f4aec2310`
  ("Reject invalid table redefinitions via dotted keys and headers
  (#59)", 2026-10-18). The project has no release tags to pin, so
  the commit hash is the pin. Snapshot vendoring, not a submodule:
  the pinned files are what was reviewed, and they cannot drift.
- **Files are byte-identical to upstream.** Upstream keeps them in
  `src/`; they sit directly in this directory instead, but the
  contents are unmodified — verified at vendoring time by git blob
  SHA-1 (`tomlc17.c` `a7de87db…`, `tomlc17.h` `c53be3e9…`,
  `LICENSE` `173779e2…`, all matching upstream at the pin).
  Kala-side build choices live in `CMakeLists.txt` and the harness,
  never in the vendored code.
- **Not vendored:** `src/tomlcpp.hpp`, the C++20 wrapper. The C API
  is the surface under test; the wrapper forwards to it.
- **Security contact:** upstream has no `SECURITY.md` (checked at
  the repo root and `.github/` on the pinned commit; `.github/`
  contains only workflows). Any finding follows
  `docs/responsible-disclosure.md`: privately to the maintainer via
  GitHub first (private vulnerability reporting if enabled, else the
  maintainer's GitHub contact), embargo 90 days, follow-up at day
  45 — before anything is published.
- **Why this target:** widely embeddable TOML parser, actively
  maintained (commits within days of the pin), passes the full
  `toml-test` suite — and, checked on the pinned commit, ships **no
  fuzz harness of its own** and is **not in OSS-Fuzz**. Correctness
  testing is thorough; coverage-guided fuzzing is the gap Kala
  fills.

## Configuration under test

Upstream defaults, no compile definitions and no option overrides:

- `toml_parse()` with default `toml_option_t` (`check_utf8` off,
  standard `realloc`/`free` allocators) — the configuration an
  embedder gets by dropping the two files into their tree.
- Scanner nesting is capped upstream (`BRACKET_LEVEL_MAX` /
  `BRACE_LEVEL_MAX` = 30); tree teardown and query paths are
  recursive in the library, which is part of what the campaign
  probes.

## Harness

`harness/libfuzzer/tomlc17_fuzzer.cpp` feeds the raw input to
`toml_parse()` (length-based; embedded NULs are data, not
terminators), walks the result tree iteratively folding types, keys
and string bytes into a checksum, runs two fixed `toml_seek()`
lookups, and calls `toml_free()` on every result as the API
requires. It stores nothing, so anything that crashes is the
library's, not the harness's.

Seeds: `corpus/tomlc17/` (hand-written valid files covering every
scalar type, dotted/quoted keys, nested and array tables, all four
string forms, inline tables, datetimes).
Dictionary: `harness/dicts/toml.dict`.

## The hunt

`kala run` with `examples/campaign-tomlc17.yaml` (48 hours,
resumable) finds ≥1 genuine crash, **or** the campaign completes
clean with rising coverage. A crash is verified by hand (clean
reproduction on a fresh build, root cause, harness artifact ruled
out), minimized, and disclosed per the SOP above — its PoC does
**not** enter this repo while unpatched. The hunt succeeds when
one valid report is accepted by the maintainer; a CVE is the
jackpot, not a requirement.
