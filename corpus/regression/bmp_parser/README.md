# Regression PoCs — bmp_parser

One fuzzer-found proof-of-crash per planted bug class (Phase 1, L1
calibration). Each file must reproduce its documented sanitizer
report when replayed:

```sh
./build-fuzzer/harness/libfuzzer/bmp_fuzzer corpus/regression/bmp_parser/<file>
```

| File | Bug | Expected report | Trigger, in one line |
|---|---|---|---|
| `bug1_oob_read_fuzz.bmp` | 1 — OOB read, pixel copy | ASan heap-buffer-overflow READ in `copy_rows` | 5x7 header, pixel data truncated to 163-byte file |
| `bug2_stack_palette_fuzz.bmp` | 2 — Stack overflow, palette | UBSan index 256 out of bounds in `parse_palette` (ASan-only: stack-buffer-overflow) | `biClrUsed` = 258, full-size palette file |
| `bug3_int_overflow_fuzz.bmp` | 3 — Integer overflow | ASan SEGV in `copy_rows` (wrapped allocation = 192 bytes vs 25.8 GB claimed) | `height` = 1073741832 at stride 24 |
| `bug4_uaf_rle_fuzz.bmp` | 4 — Use-after-free | ASan heap-use-after-free WRITE in `copy_rows` | `compression` = 1 (BI_RLE8), malformed stream |
| `bug5_oob_palette_offset_fuzz.bmp` | 5 — OOB read via bfOffBits | ASan heap-buffer-overflow READ in `parse_palette` | `bfOffBits` = 1078 in a 189-byte file |

Ground truth: `targets/bmp_parser/PLANTED_BUGS.md`. These files are
the seed of the Phase 4 regression lab; CI will replay them on every
push there.
