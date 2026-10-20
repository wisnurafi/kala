# PLANTED_BUGS — answer key for bmp_parser

> **Do not open this file during a triage validation run.** It is the
> ground truth the Phase 1 (L1) and Phase 2 (L2) validations are scored
> against. Every bug below also has a deterministic trigger in
> `gen_pocs.py` and, once the calibration campaign has run, a
> fuzzer-found PoC in `corpus/regression/bmp_parser/`.

All locations are in `bmp_parser.c`.

## Bug 1 — Heap buffer overflow (read), pixel copy

- **Where:** `copy_rows()` (memcpy at line 68), called from
  `bmp_parse()` line 138.
- **Mechanism:** the copy loop trusts the header's dimensions
  (`stride * rows` bytes from `bfOffBits`) and never checks that the
  input actually holds that many pixel bytes. A truncated file — or a
  height field inflated past the real data — makes memcpy read past
  the end of the input buffer.
- **Trigger shape:** valid header, `height` rows claimed, pixel data
  cut short (see `poc1_oob_read.bmp`).
- **Expected report:** ASan `heap-buffer-overflow`, READ, in
  `copy_rows`.

## Bug 2 — Stack buffer overflow (write), palette copy

- **Where:** `parse_palette()` line 33, called from `bmp_parse()`
  line 112.
- **Mechanism:** palette entries are copied into a fixed
  `uint32_t palette[256]` stack array, looping `biClrUsed` times with
  no cap. A palette that declares more than 256 entries (legal to
  declare, and the file can really contain them) walks off the array.
- **Trigger shape:** 8bpp, `biClrUsed` > 256, at least
  `bfOffBits`-relative palette bytes present so the read side survives
  until entry 256 (see `poc2_stack_palette.bmp`).
- **Expected report:** ASan `stack-buffer-overflow`, WRITE, in
  `parse_palette`. Under the `asan-ubsan` profile UBSan's bounds check
  usually reports first: `index 256 out of bounds for type
  'uint32_t[256]'` at the same line — same bug, different sanitizer
  winning the race.

## Bug 3 — Integer overflow → under-allocation

- **Where:** allocation size computed at `bmp_parse()` line 115,
  overflow crashes in `copy_rows()` line 68.
- **Mechanism:** `uint32_t alloc_size = stride * rows;` wraps modulo
  2^32. Dimensions whose true product is a small residue past a
  multiple of 2^32 (e.g. stride 12 × rows 0x40000000 → 0) allocate a
  tiny buffer while the copy loop still trusts the full row count.
- **Trigger shape:** extreme `width`/`height` pair whose
  `stride * rows` wraps (see `poc3_int_overflow.bmp`, top-down so the
  write is sequential).
- **Expected report:** ASan `heap-buffer-overflow`, WRITE, in
  `copy_rows`. A bottom-up variant of the same trigger computes a
  destination gigabytes out and reports SEGV at the same line — same
  root cause; the header math (wrapped allocation ≪ claimed size) is
  how it is told apart from Bug 1.

## Bug 4 — Use-after-free on the RLE error path

- **Where:** free at `bmp_parse()` line 131, use in `copy_rows()`
  line 68.
- **Mechanism:** for BI_RLE8 input the pixel buffer is freed before
  decoding; if `rle8_decompress()` then fails, the code falls through
  to the raw-copy fallback with the freed pointer — the
  "fallback" branch never re-allocates and never returns the error.
- **Trigger shape:** `compression = 1` (BI_RLE8) with a stream that
  lacks the end-of-bitmap marker (see `poc4_uaf_rle.bmp`).
- **Expected report:** ASan `heap-use-after-free`, WRITE, in
  `copy_rows`.

## Bug 5 — Out-of-bounds read via bfOffBits-derived palette pointer

- **Where:** pointer computed at `parse_palette()` line 30, read at
  line 33.
- **Mechanism:** the palette is located by walking back from
  `bfOffBits` (`data + data_offset - colors_used * 4`) with no
  validation of `bfOffBits` against the input size or the palette
  size. A `bfOffBits` that is too small (or beyond the input) points
  the palette read outside the buffer.
- **Trigger shape:** 8bpp with a `bfOffBits` inconsistent with the
  palette (see `poc5_oob_palette_offset.bmp`, `bfOffBits` = 20 with a
  64-byte palette).
- **Expected report:** ASan `heap-buffer-overflow`, READ, in
  `parse_palette` (via `get_u32le`). A far-out `bfOffBits` reports
  SEGV at the same site.
