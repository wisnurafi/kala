#!/usr/bin/env python3
"""Generate the valid BMP seed corpus for bmp_parser.

Pure standard library (struct) on purpose: the seeds must be
reproducible anywhere without imaging dependencies. Every file here
is well-formed and must parse cleanly — a seed that crashes the
target would invalidate the calibration baseline.

Usage: python3 gen_seeds.py <output-dir>
"""

import struct
import sys
from pathlib import Path


def build_bmp(width, height, bpp, pixel_bytes, colors_used=0, palette=b""):
    bytes_pp = {8: 1, 16: 2, 24: 3, 32: 4}[bpp]
    stride = ((width * bytes_pp + 3) // 4) * 4
    rows = abs(height)
    assert len(pixel_bytes) == stride * rows, (len(pixel_bytes), stride * rows)
    data_offset = 54 + len(palette)
    image_size = stride * rows
    file_size = data_offset + image_size
    file_header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, data_offset)
    info_header = struct.pack(
        "<IiiHHIIiiII",
        40, width, height, 1, bpp, 0, image_size, 2835, 2835,
        colors_used, 0,
    )
    return file_header + info_header + palette + pixel_bytes


def pixels(width, height, bpp, seed=0):
    bytes_pp = {8: 1, 16: 2, 24: 3, 32: 4}[bpp]
    stride = ((width * bytes_pp + 3) // 4) * 4
    out = bytearray()
    for y in range(abs(height)):
        row = bytearray()
        for x in range(width):
            for c in range(bytes_pp):
                row.append((x * 7 + y * 13 + c * 29 + seed) & 0xFF)
        row.extend(b"\x00" * (stride - len(row)))
        out.extend(row)
    return bytes(out)


def palette(n, seed=0):
    out = bytearray()
    for i in range(n):
        out.extend(bytes(((i * 3 + seed) & 0xFF, (i * 5) & 0xFF,
                          (i * 7) & 0xFF, 0)))
    return bytes(out)


def main():
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds = {
        "rgb24_8x8.bmp": build_bmp(8, 8, 24, pixels(8, 8, 24)),
        "rgb24_16x16.bmp": build_bmp(16, 16, 24, pixels(16, 16, 24, seed=3)),
        "rgb24_5x7.bmp": build_bmp(5, 7, 24, pixels(5, 7, 24, seed=5)),
        "rgb24_topdown_8x8.bmp": build_bmp(8, -8, 24, pixels(8, -8, 24, seed=7)),
        "argb32_4x4.bmp": build_bmp(4, 4, 32, pixels(4, 4, 32, seed=11)),
        "pal8_16x16.bmp": build_bmp(16, 16, 8, pixels(16, 16, 8, seed=13),
                                    colors_used=256, palette=palette(256)),
        "pal8_8x8_16col.bmp": build_bmp(8, 8, 8, pixels(8, 8, 8, seed=17),
                                        colors_used=16, palette=palette(16)),
    }
    for name, blob in seeds.items():
        (out_dir / name).write_bytes(blob)
        print(f"{name}: {len(blob)} bytes")


if __name__ == "__main__":
    main()
