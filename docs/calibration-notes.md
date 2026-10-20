# Calibration notes

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
   Phase 2 scope.
