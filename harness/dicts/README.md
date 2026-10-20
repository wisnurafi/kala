# Dictionaries

Token dictionaries per file format: magic bytes, chunk names,
keywords, and the boundary values random mutation will never
assemble on its own (2^30-scale dimensions, counts at 255/256/257).
For structured formats a good dictionary raises coverage sharply,
because the fuzzer can splice valid tokens instead of guessing
them byte by byte.

Format: libFuzzer dictionary syntax (`name="bytes"`), which AFL++
also accepts.

- `hello.dict` — the `FUZZ` magic and friends for the smoke test.
- `bmp.dict` — BMP header fields and boundary dimensions.
- `ini.dict` — INI structure, plus line-length runs that force
  inih's realloc growth path.
- `toml.dict` — TOML grammar tokens, datetime pieces, number
  boundaries, and nesting runs at the scanner's caps.

**Escape rule:** non-printable bytes are written `\xNN` only.
libFuzzer's dictionary parser rejects the `\r`, `\n` and `\t`
escapes (only `\\`, `\"` and `\xNN` are legal), and the failure is
silent from the campaign's point of view — every fuzzer process
exits at startup, the slice loop restarts it, and the run
"completes" with **zero executions**. Zero executions always means
the harness is broken, never that the target is clean.
