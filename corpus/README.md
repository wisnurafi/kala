# Corpus

- `hello/` — seed corpus for the hello-world harness. Seeds are valid or
  near-miss inputs on purpose: they give coverage-guided fuzzing a
  starting slope instead of a flat plain. Committed.
- `regression/` — minimized PoCs from confirmed unique crashes. Every
  file here is a permanent regression test (Phase 4 CI replays them).
  Committed.
- Campaign output does not belong in git: raw findings and generated
  corpora are ignored (see `.gitignore`) and distilled before anything
  is promoted into `regression/`.
