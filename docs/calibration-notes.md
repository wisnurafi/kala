# Calibration notes

> This file is Kala's development and calibration log — the
> historical record of how each component was built and validated,
> written per phase while the numbers were fresh. The toolkit it
> describes is complete and in operation; this log is kept because
> the lessons in it are load-bearing (several are hard rules in
> `CONTRIBUTING.md` now).


Lessons from validating the pipeline against targets whose ground
truth is known. Written per phase, immediately after the campaign,
while the numbers are still fresh.

## Phase 1 — bmp_parser (L1: 5/5 planted bugs found)

Campaign shape: libFuzzer + ASan/UBSan (`fuzzer-asan-ubsan` preset),
seed corpus `corpus/bmp` (7 valid BMPs), dictionary
`harness/dicts/bmp.dict`. Because an ASan crash kills the process and
the easiest bug (truncated pixel data) is one mutation away from any
seed, the campaign ran as restart loops: run, harvest the artifact,
classify it (sanitizer class + top parser frame + header fields),
restart on the accumulated corpus. Focused single-seed loops were
used for the two rare bugs.

Results (fuzzer-found PoCs in `corpus/regression/bmp_parser/`):

| Bug | Found by | Effort | Note |
|---|---|---|---|
| 1 — OOB read | general rounds | seconds | Dominates: most first crashes are this |
| 5 — OOB read via bfOffBits | general rounds | seconds | Palette path fires before pixel copy on 8bpp inputs |
| 4 — Use-after-free | general rounds | ~52 rounds | Single-field mutation (`compression` 0 → 1) |
| 3 — Integer overflow | focused loop, RGB seed only | ~58 s of rounds | `height` landed at 0x40000008 — the dictionary's 2^30 boundary token did the heavy lifting |
| 2 — Stack palette overflow | focused loop, palette seed only | ~103 s of rounds | Winning mutation was `biClrUsed` 256 → 258, one low-byte increment, on the full-size (1334-byte) lineage |

### Lessons

1. **Verify planted bugs by hand before fuzzing.** The deterministic
   PoCs (`gen_pocs.py`) caught two manifestation problems up front:
   the integer-overflow trigger reported SEGV instead of a clean
   heap-buffer-overflow in its bottom-up form (the destination is
   ~stride × rows away), and the stack palette overflow is reported
   by UBSan's bounds check, not ASan, under the combined profile.
   A campaign scored against unverified ground truth would have
   misclassified both.
2. **Symbolization is part of the pipeline, not a nicety.** When
   `llvm-symbolizer` is missing, ASan prints raw addresses and
   stack-trace-based triage silently attributes *nothing*. The
   fallback `ASAN_OPTIONS=external_symbolizer_path=/usr/bin/addr2line`
   restored full frames. Phase 2's dedup hashes stack traces — it
   must check the traces are symbolized and fail loudly if not.
3. **`-fork` and `-jobs` did not keep this libFuzzer build running**
   past the first crash per worker; restart loops with per-crash
   classification worked and are trivially resumable. (Also: keep
   campaign state out of `/tmp` — an environment restart wiped the
   first run's artifacts; the campaign was reproduced from scratch in
   minutes because every step was scripted.)
4. **The easy bug starves the rare ones.** In a mixed corpus almost
   every process dies to Bug 1 within ~25 executions. Focused corpora
   (one seed lineage per rare bug) raised the hit rate more than any
   flag did.
5. **Dictionaries earn their keep on integer bugs.** Random mutation
   essentially never assembles a 2^30-scale height; the boundary-value
   tokens in `bmp.dict` did. Keep format dictionaries stocked with
   boundary values for every size/dimension field.
6. **Minimization is not free.** `libFuzzer -minimize_crash` did not
   finish within 30 s caps on these inputs, so the regression PoCs
   are stored at their found sizes (163 B – 1334 B; the palette PoC
   cannot go below ~1.1 KB by construction). Real minimization is
   Phase 2 scope. *(Phase 2 correction: the minimizer had in fact
   finished — its output files are named `minimized-from-<hash>`,
   and the Phase 1 check globbed for `crash-*`. See Phase 2, lesson
   3.)*

## Phase 2 — triage toolkit (L2: report matches the answer key)

Validation set: 590 raw artifacts from the Phase 1 campaign (the
full general-round and integer-overflow-hunt hauls, a seeded sample
of the palette-hunt haul, plus the five attributed PoCs — all
unmodified campaign output). The toolkit had no knowledge of the
answer key; scoring compared its groups against
`targets/bmp_parser/PLANTED_BUGS.md` afterwards.

Results:

- **5 unique groups for 5 planted classes** (target: 5 ± 1). Group
  sizes 454 / 125 / 5 / 5 / 1 — the easy bug dominates the raw haul
  exactly as the Phase 1 notes predicted.
- **Group classification: 5/5 correct (100%)** — heap-buffer-overflow
  READ @ copy_rows (bug 1), heap-buffer-overflow READ @ parse_palette
  (bug 5), SEGV WRITE @ copy_rows (bug 3), heap-use-after-free WRITE
  @ copy_rows (bug 4), stack-buffer-overflow @ parse_palette
  (bug 2, normalized from the UBSan bounds report).
- **Input-level purity: 93.4%.** 39 of 590 inputs (6.6%) are bug-5
  mechanism (wild `bfOffBits` on non-palette inputs) whose crash
  lands in `copy_rows` instead of `parse_palette`; their sanitizer
  evidence is identical to bug 1's, so they group with it. Only
  input-structure analysis could separate them.
- **Idempotency: verified.** Two runs produce a byte-identical
  report (verified by SHA-256) after one fix — see lesson 2.
- Replay throughput: ~75 ms per input (590 inputs in ~44 s).

### Lessons

1. **A triage tool can only group what the corpus contains.** The
   first validation run (585 inputs, found-PoCs excluded) produced
   4 groups — bug 2 was represented by essentially one artifact in
   the entire campaign haul. Corpus composition is a calibration
   variable, not a detail.
2. **Determinism leaks through the evidence you embed.** The first
   report embedded the representative's raw sanitizer excerpt —
   including its PID and raw addresses — so two runs differed.
   Normalizing PIDs/addresses out of the stored excerpt restored
   byte-identical output.
3. **Know your tools' output conventions before scoring them.**
   `-minimize_crash` writes `minimized-from-<hash>` files; globbing
   for `crash-*` made a working minimizer look broken in Phase 1
   *and* in the first Phase 2 implementation. With the fix,
   minimization shrank 4 of 5 smoke-set PoCs by 40–67% (163 B →
   54 B for bug 1) with signature verification; the palette PoC
   (bug 2) resists — shrinking it changes which bug fires first, so
   the verifier correctly rejects the candidates.
4. **The classifier labels what the sanitizer proves.** Bug 3's
   group is labeled `SEGV-unknown`, because that is what ASan can
   prove from the trace; "integer overflow" is a root-cause
   inference from the input's header math (allocation wrapped to
   192 B against 25.8 GB claimed), made by the human during scoring.
   An automated version of that inference is a possible future
   heuristic, not a classifier bug.

## Phase 3 — campaign orchestration (L3: unattended campaign)

Validation: two local campaigns against bmp_parser — a 6-minute
demo (2 jobs, 30 s slices) and a 4-minute campaign interrupted by
SIGINT after one slice and resumed with the same command.

Results:

- Demo: complete, 360/360 s budget, 12 slices, **1,770,897 summed
  executions**, jobs scaled 2 → 4 by the surge rule, one
  stagnation merge, 84 oom/timeout artifacts filed as resource
  events (not crash groups), final report 6 groups.
- Resume test: SIGINT after slice 1 → exit code 2, `state.json`
  marked `interrupted` at 30/240 s; re-running the same command
  consumed the remaining 210 s and completed (852,335 executions,
  one stagnation merge, final report 8 groups).
- **Every group in both reports maps to a Phase 1 root cause at a
  known function** — no phantom groups. The resume campaign even
  found bug 2 on its own (stack-buffer-overflow @ parse_palette).
- **Stack hashes are stable across campaigns**: the major groups
  carry identical hashes in both runs (and match Phase 2's for the
  classes whose frame sets the Phase 3 parser fix did not change —
  see lesson 2).
- New manifestations of known root causes appeared and were
  classified as ASan reported them: `memcpy-param-overlap` and
  `unknown-crash`, both at `copy_rows` (wild offsets making the
  copy's source and destination ranges collide).

### Lessons

1. **A slice is not a duration until you make it one.** The first
   engine let each job run a single libFuzzer process per slice;
   the process dies at its first crash in seconds, so a "30 s
   slice" was an accounting fiction and a 4-minute campaign
   finished in ~40 s of wall time. Jobs now restart in a loop
   until the slice's wall-clock budget is spent (the Phase 1
   restart-loop pattern, productized).
2. **Parse only the first stack.** ASan reports append "allocated
   by" / "freed by" stacks after the crash stack; the original
   frame parser swept them all up, so the same bug hashed
   differently depending on which buffer overflowed. First-stack-
   only parsing unified the variants (identical hash `c75583a009ff`
   for both) — and changed hashes versus Phase 2 for groups whose
   frame sets had been polluted, which is why hash comparisons are
   only meaningful within one parser version.
3. **A negative-offset read wears whatever the heap is wearing.**
   One artifact reported `heap-use-after-free` at `parse_palette`:
   the palette pointer walked 906 bytes *before* the input buffer
   and landed in a freed, ASan-quarantined stdio buffer belonging
   to libFuzzer itself. Same root cause as bug 5 (unvalidated
   palette pointer), three possible costumes — overflow, UAF, or
   SEGV — depending on what precedes the buffer. The toolkit
   deliberately does not merge UAF into overflow groups; the
   phenomenon is documented here instead.
4. **Test harnesses have signal dispositions too.** Two resume
   tests "failed" because background jobs launched from a
   non-interactive shell inherit SIGINT as *ignored*, and Python
   faithfully inherits that. The engine was correct; the test
   needed `env --default-signal=INT` to reproduce a real Ctrl+C.
   Check the harness before auditing the product (again).

## Phase 4 — hardening, regression lab, first private target

Three Phase 3 follow-ups closed:

- **Report/state reconciliation.** Campaign `_triage()` replayed
  only the representatives that still crashed and rendered only
  those groups; in the Phase 3 VM QA that silently dropped 2 of 3
  state groups (a timeout representative and a heap-layout-dependent
  palette read). Reports now carry a reconciliation section listing
  every `state.json` group with its reproduction status. Verified
  both ways in a 30 s smoke campaign (6 groups, all reproduced, all
  hashes present in the report) and by corrupting one
  representative into a benign input (its group renders
  NOT REPRODUCED; restored, it disappears).
- **Symbolization off during slices.** Each symbolized crash spawns
  an external symbolizer process; on the QA VM that cost dominated.
  Slices now run through `fuzz_env()` (`symbolize=0`, no external
  symbolizer, UBSan stack traces off; `symbolize_slices: true`
  opts back in), while harvest/triage replay fully symbolized.
  Verified on the bug-1 PoC: both environments crash (exit −6),
  only the replay environment produces frames.
- **Inline-helper normalization.** `get_u32le` and friends are
  skipped when computing location and stack hash, so attribution
  no longer depends on a compiler's inlining choices. Bug 1's hash
  stayed `c75583a009ff` across the change and across campaigns.

Regression lab: `kala regress` promotes a PoC only after a replay
proves the documented class (and top function); it refuses
non-crashing, mislabeled and byte-duplicate inputs, copies the
file into `corpus/regression/<target>/` and appends the README
row. `tools/check_regression.py` is the machine side: 5/5 PoCs
reproduce as documented against a fresh preset build. CI
(`.github/workflows/ci.yml`) runs the preset build, both unit
suites (triage 28, orchestrate 10 at this writing), the
portability grep and the regression replay on every push, plus a
weekly 120 s fuzz smoke with automatic triage.

Private target: **inih** (benhoyt/inih, vendored at `2bbdec4`,
BSD-3), configured `INI_USE_STACK=0` + `INI_ALLOW_REALLOC=1` — the
heap line-buffer path. Harness feeds `ini_parse_string_length()`;
handler stores nothing. Smoke campaign (3 min, 2 jobs): **clean —
8,817,559 executions, 0 artifacts, coverage 63 → 75 (features
127 → 493)** on job 0. Remaining gate: the 24-hour campaign on the
fuzzing VM, per the Phase 4 definition of done.

### Lessons

1. **A clean campaign with 0 executions is not clean — it is
   broken.** The first inih smoke "completed" with 0 artifacts
   *and 0 executions*: `ini.dict` used `\r`/`\n`/`\t` escapes,
   libFuzzer's dictionary parser rejects those (only `\\`, `\"`,
   `\xNN`), and every fuzzer process exited at startup — the slice
   loop restarted it thousands of times (1000+ run logs for one
   slice) and the harvest faithfully reported nothing. The
   tell was the exec counter. Dictionaries use `\xNN` for every
   non-printable byte, and a campaign's summed execs are a health
   signal, not a vanity metric: 0 execs = audit the harness first.
2. **`clang` the package is not the fuzzing toolchain.** A fresh
   `apt install clang` lacks the compiler-rt archives
   (`libclang_rt.fuzzer/asan`), so linking a libFuzzer binary
   fails. CI installs `libclang-rt-dev` alongside clang — found by
   rebuilding from an empty build directory locally, not by
   reading package descriptions.
8. VM QA found the external-symbolizer deadlock the container
   never showed: the VM has llvm-symbolizer installed, the
   container does not, so `find_symbolizer()` picked different
   tools per machine. With llvm-symbolizer as ASan's external
   symbolizer, two regression PoCs (stack palette overflow,
   integer-overflow SEGV) never produced a report — the sanitizer
   sat at ~0% CPU waiting on the symbolizer child until the
   replay timeout classified both as `timeout`. Proof by
   elimination on the VM: `symbolize=0` crashes in ~0.1s, and
   forcing `external_symbolizer_path=/usr/bin/addr2line` crashes
   in ~0.2s fully symbolized. Fix: addr2line is now the preferred
   candidate, and the new `replay_classified()` retries a timed-
   out classification replay once with symbolization off, so a
   wedged symbolizer can never again disguise a real crash as a
   timeout. Lessons: a "timeout" class means the *replay* timed
   out, which is a claim about the harness as much as the input;
   and per-machine tool availability is a calibration variable —
   the same `shutil.which` probe silently routes different
   machines down different code paths.

## Phase 5 — first public target: tomlc17 (hunt open)

Public target chosen by the maintainer from the Phase 4 shortlist:
**tomlc17** (cktan/tomlc17, TOML v1.1 parser in C, MIT), vendored at
`85000d08` ("Reject invalid table redefinitions via dotted keys and
headers (#59)", 2026-10-18; no release tags exist, so the commit
hash is the pin). Vendored files verified byte-identical to upstream
by git blob SHA-1 (all three match). Checked on the pin: no
`SECURITY.md` (root or `.github/`), no upstream fuzz harness, not in
OSS-Fuzz — disclosure runs per `docs/responsible-disclosure.md` via
the maintainer on GitHub, privately first.

Configuration: upstream defaults (no defines, `check_utf8` off) —
what an embedder gets by dropping the two files in. Harness feeds
`toml_parse()`, walks the result tree ITERATIVELY (the library's own
teardown/query paths are recursive; the harness refuses to be the
recursion that crashes), runs two fixed `toml_seek()` lookups, and
calls `toml_free()` on every result.

Smoke (container, clang 18, 120 s, 2-min dictionary run): seed
replay alone reaches cov 351 / ft 595 from 5 hand-written seeds;
the run completes **clean — 4,340,595 executions, 0 artifacts,
coverage 351 → 432+ (features 595 → 1441+ by the last recorded pulse)**. Baseline suites stay
green: triage 34, orchestrate 10, regression replay 5/5.

Remaining gate: the 48-hour campaign on the fuzzing VM
(`examples/campaign-tomlc17.yaml`, resumable), not to be stacked
full-jobs with the still-accumulating inih 24-hour campaign on the
same VM. M5 is done when one valid report is accepted upstream.
