#!/usr/bin/env python3
"""Generate one deterministic trigger input per planted bug.

Calibration discipline (roadmap Fase 1): each planted bug is verified
manually with these files BEFORE any fuzzing run:

    bmp_dump poc1_oob_read.bmp      # expect ASan heap-buffer-overflow READ
    ... and so on, per PLANTED_BUGS.md

If a PoC does not produce its documented sanitizer report, the bug is
mis-planted and must be fixed before the campaign starts — a fuzzer
cannot be calibrated against a target whose ground truth is wrong.

Usage: python3 gen_pocs.py <output-dir>
"""

import struct
import sys
from pathlib import Path


def header(width, height, bpp, data_offset, image_size, compression=0,
           colors_used=0):
    file_size = data_offset + image_size
    return struct.pack("<2sIHHI", b"BM", file_size, 0, 0, data_offset) + \
        struct.pack("<IiiHHIIiiII", 40, width, height, 1, bpp, compression,
                    image_size, 2835, 2835, colors_used, 0)


def main():
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    pocs = {}

    # Bug 1: header claims 16 rows of pixels, file holds almost none.
    pocs["poc1_oob_read.bmp"] = header(16, 16, 24, 54, 48 * 16) + b"\x41" * 32

    # Bug 2: 8bpp palette declares 300 entries and supplies them all;
    # the parser copies them into a 256-entry stack palette.
    pal = bytes(range(256)) * 4  # 1024 bytes, extended below to 1200
    pal = (pal + b"\x07" * 1200)[:1200]
    pocs["poc2_stack_palette.bmp"] = (
        header(8, 8, 8, 54 + 1200, 64, colors_used=300) + pal + b"\x00" * 64
    )

    # Bug 3: stride(12) * rows(0x40000000) wraps the 32-bit allocation
    # product to 0 while the copy loop trusts the row count. Top-down
    # (negative height) so rows are written sequentially from the
    # start of the zero-byte allocation and ASan reports a clean
    # heap-buffer-overflow WRITE (the bottom-up variant computes a
    # destination ~12 GB out and reports SEGV at the same line — same
    # bug, noisier report).
    pocs["poc3_int_overflow.bmp"] = header(4, -0x40000000, 24, 54, 0) + \
        b"\x42" * 64

    # Bug 4: BI_RLE8 whose stream lacks the end-of-bitmap marker; the
    # decode fails after the pixel buffer has been freed, and the raw
    # copy fallback writes into the freed buffer.
    pocs["poc4_uaf_rle.bmp"] = header(8, 8, 24, 54, 192, compression=1) + \
        b"\x41" * 192

    # Bug 5: bfOffBits (20) is smaller than the palette that supposedly
    # precedes it (16 entries * 4 = 64 bytes), so the palette is read
    # from before the start of the input buffer.
    pocs["poc5_oob_palette_offset.bmp"] = (
        header(8, 8, 8, 20, 64, colors_used=16) + b"\x00" * 64
    )

    for name, blob in pocs.items():
        (out_dir / name).write_bytes(blob)
        print(f"{name}: {len(blob)} bytes")


if __name__ == "__main__":
    main()
