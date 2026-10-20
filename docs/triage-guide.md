# Triage guide

How raw fuzzer output becomes a report you can act on, and how to
verify a group by hand when it matters.

## The pipeline

```sh
./kala triage <crash-dir> --target bmp_parser --out report.html
```

Five stages, all in `triage/`:

1. **Ingest** — collects libFuzzer artifacts (`crash-*`, `leak-*`,
   `oom-*`, `timeout-*`) and AFL++ `id:*` files. `--all` ingests
   every file in the directory.
2. **Replay** — each input is re-run through the instrumented
   binary with a hard timeout, in its own process group. The
   runner autodetects a symbolizer (llvm-symbolizer, falling back
   to `addr2line`) and warns if traces come back unsymbolized —
   without function names, grouping is guesswork.
3. **Classify** — the sanitizer output becomes a taxonomy label
   (`heap-buffer-overflow`, `stack-buffer-overflow`,
   `heap-use-after-free`, `SEGV-unknown`, …), an access direction,
   and a location: the top *application* frame of the **first**
   stack in the report. Auxiliary stacks ("allocated by", "freed
   by") describe other code paths and are deliberately ignored —
   including them made the same bug hash differently depending on
   which buffer overflowed.
4. **Dedup** — groups by (class, direction, top function); stack
   hash = first 12 hex of SHA-256 over the normalized stack.
   Normalization skips inlined accessor helpers (`get_u32le` and
   friends): whether a crash is attributed to the helper or its
   caller is a compiler inlining coin toss, and the same bug
   carried the identical hash `c75583a009ff` on clang 18 and
   clang 21 once normalized. One merge rule exists on top: a SEGV
   group folds into a buffer-overflow group with the same
   direction and function, because ASan reports the same wild
   access both ways depending on how far out it lands.
5. **Minimize + report** — each group's representative (smallest
   member) is minimized with libFuzzer `-minimize_crash` under a
   signature check: the candidate must reproduce the same class
   and location or it is rejected. Note the minimizer writes
   `minimized-from-<hash>`, **not** `crash-*` — globbing for the
   wrong name made a working minimizer look broken twice. The
   report is one self-contained HTML file, byte-identical across
   runs (excerpts are normalized: PIDs and addresses stripped).

`oom-*` / `timeout-*` artifacts are resource events, not crash
groups; campaigns count them separately and the classifier labels
what the sanitizer *proved* — a group labeled `SEGV-unknown` whose
input claims 25.8 GB against a 192-byte allocation is an integer
overflow by human inference, and the report leaves that inference
to the human on purpose.

## Reading a report

- The groups table is sorted by size: the biggest group is
  usually the easiest bug, not the most severe. Check severity
  (from class + direction) before count.
- Campaign reports add a **state reconciliation** section: every
  group in `state.json` with its standalone reproduction status.
  A group marked **NOT REPRODUCED** did not crash when replayed
  alone — typically heap-layout-dependent (a wild pointer landing
  in a freed buffer only under campaign conditions) or
  timeout-flavoured. It stays in the report precisely so it cannot
  vanish silently; work it from the campaign's `crashes/`
  representative and logs before dismissing it.

## Verifying a group by hand

```sh
# Reproduce, symbolized
./build-fuzzer/harness/libfuzzer/bmp_fuzzer <representative>

# Or under gdb for a look at the actual state
gdb -args ./build-fuzzer/harness/libfuzzer/bmp_fuzzer <representative>
```

Confirm: same sanitizer class, same top function, deterministic
across 3 runs. Then ask the root-cause questions the classifier
cannot: which input field controls the failing index/size/offset,
what the valid range is, and which check is missing. That analysis
is what goes into a disclosure (see `responsible-disclosure.md`).

## Promoting a confirmed crash

```sh
./kala regress <poc> --target bmp_parser --name bug6_example \
  --expect-class heap-buffer-overflow --expect-function copy_rows \
  --bug "6 — ..." --expected "ASan heap-buffer-overflow READ in copy_rows" \
  --trigger "one line"
python3 tools/check_regression.py   # must stay green
```

`kala regress` replays first and refuses anything that does not
crash exactly as documented — a regression entry that cannot fail
would turn CI green over a live bug. Register the new PoC in
`tools/check_regression.py` when the command reminds you; CI then
replays the whole corpus on every push.

## Known limits

- Input-level purity was 93.4% in Phase 2 validation: two distinct
  root causes whose sanitizer evidence is identical group together.
  Only input-structure analysis could separate them; when a group
  looks suspiciously large, split it by hand along input fields.
- A negative-offset read wears whatever the heap is wearing:
  overflow, use-after-free, or SEGV for one root cause. The
  toolkit does not merge UAF into overflow groups — if a UAF group
  shares a function with an overflow group, suspect this before
  assuming two bugs.
