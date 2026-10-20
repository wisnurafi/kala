# triage/ — crash triage pipeline (Phase 2)

Turns a directory of raw fuzzer crashes into one deduplicated HTML
report: ingest → replay → classify → dedup → minimize → report.

```sh
./kala triage ./crashes --target bmp_parser
# or: python3 -m triage ./crashes --target bmp_parser --out report.html
```

Options: `--bin PATH` (override the target binary), `--all` (ingest
every file, not only libFuzzer/AFL++-named artifacts),
`--minimize-time S` (per-step minimization budget, 0 disables),
`--timeout S` (per-input replay timeout), `--work-dir DIR`.

## Modules

- `ingest.py` — collect artifacts (libFuzzer `crash-*`/`leak-*`/
  `oom-*`/`timeout-*`, AFL++ `id:*`, or every file with `--all`).
- `runner.py` — replay one input through the instrumented binary;
  finds llvm-symbolizer (falls back to addr2line) and injects it
  into `ASAN_OPTIONS`. **Un-symbolized traces make stack-based
  triage blind** — the CLI warns loudly when that happens.
- `classify.py` — parse ASan/UBSan output into a bug class
  (heap-buffer-overflow, stack-buffer-overflow, heap-use-after-free,
  integer-overflow, SEGV-unknown, …), access direction, and top
  application frame. UBSan bounds traps on fixed arrays normalize
  to `stack-buffer-overflow`.
- `dedup.py` — group by (class, direction, top application
  function); addresses and line numbers are normalized away. SEGV
  groups merge into a same-direction buffer-overflow group at the
  same function (ASan reports one OOB access both ways depending on
  how far out it lands). Each group gets a stable stack hash.
- `minimize.py` — libFuzzer `-minimize_crash` wrapper. Results are
  the `minimized-from-*` files in the artifact dir; a candidate is
  accepted only if a verification replay shows the same class at the
  same location.
- `report.py` — one self-contained HTML file (inline CSS, PoCs
  embedded as base64 download links, no JavaScript, works offline).
  Output is deterministic: identical inputs produce a byte-identical
  report (sanitizer excerpts are normalized for PIDs/addresses).

## Design constraints

- Standard library only — runs on any Python 3.11+ with no install.
  (The roadmap listed Jinja2 for the report; a single render
  function in `report.py` keeps that swap trivial, and zero
  dependencies won for a tool meant to run inside throwaway VMs.)
- Subprocess is always invoked with argument lists, never shells.

## Tests

```sh
python3 -m unittest discover -s triage/tests -t .
```

Unit tests cover the sanitizer-output parser (shapes captured from
the Phase 1 campaign), excerpt determinism, and the dedup grouping
rules including the SEGV merge.
