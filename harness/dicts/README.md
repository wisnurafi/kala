# Dictionaries

Token dictionaries per file format: magic bytes, chunk names, keywords.
For structured binary formats a good dictionary raises coverage sharply,
because the fuzzer can splice valid tokens instead of guessing them byte
by byte.

Format: libFuzzer dictionary syntax (`name="bytes"`, `\xNN` escapes),
which AFL++ also accepts.

- `hello.dict` — tokens for the Phase 0 hello-world target.
- A BMP dictionary (`bmp.dict`) arrives with the Phase 1 target.
