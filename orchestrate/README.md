# Campaign orchestration (Phase 3)

Python campaign manager:

- Campaign defined in YAML: target, fuzzer, duration, cores, seed corpus.
  One command: `kala run campaign.yaml`.
- Multi-core: libFuzzer `-jobs=N` / AFL++ multi-instance with a sync dir.
- Corpus distillation on a schedule, plus a watchdog that restarts hung
  workers and stops the campaign at its deadline.
- Monitoring: exec/s, coverage trend, unique crash count.

Not implemented in Phase 0.
