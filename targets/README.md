# Targets

Practice targets live here — parsers written for Kala, with bugs planted
on purpose so the pipeline can be calibrated honestly.

## Phase 1: bmp_parser

A minimal BMP parser in C with 5 planted bug classes:

1. Heap buffer overflow
2. Stack buffer overflow
3. Integer overflow leading to under-allocation
4. Use-after-free / double-free on an error path
5. Out-of-bounds read

Its `PLANTED_BUGS.md` is the answer key for the L1 validation (find 5/5)
and must not be opened during triage.

Real open-source targets (stb_image, libpng, ...) are Phase 3.
