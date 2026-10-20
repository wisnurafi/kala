# orchestrate/ — campaign orchestration (Phase 3)

Runs fuzzing campaigns unattended: parallel libFuzzer jobs in time
slices, automatic crash harvesting and dedup (via the Phase 2 triage
pipeline), corpus sharing and merging, a metric-driven scheduler,
persistent state with resume, and a triage report when the time
budget is consumed.

```sh
./kala run --config examples/campaign.yaml   # run or resume
./kala status --config examples/campaign.yaml
```

Interrupting is safe: Ctrl+C (or a VM reboot) leaves `state.json`
and all corpora on disk; re-running the same command resumes until
the configured duration budget is fully consumed.

## Campaign layout

```
campaigns/<name>/
  jobs/job-<i>/corpus|artifacts|logs/   per-job state and slice logs
  shared/                               corpus shared between jobs
  crashes/                              one file per unique crash group
  state.json                            machine state (resume source)
  status.txt                            human summary, updated per slice
  report.html                           triage report (on finish)
```

## Modules

- `config.py` — YAML config (PyYAML when present, a documented-
  subset fallback parser otherwise); validates values and rejects
  unknown keys. Relative paths resolve against the repo root.
- `runner.py` — the campaign engine: slice loop, harvest + classify
  + dedup of new artifacts, corpus sync, scheduler actions,
  state persistence, final triage.
- `scheduler.py` — pure rules over campaign metrics:
  **stagnation** (no new unique group for N checks → merge all
  corpora into a minimized shared corpus and reseed) and
  **surge** (unique-group rate above threshold → add a job, capped).
- `status.py` — renders `status.txt` / `kala status` output.

## Notes and limits

- A slice is wall-clock: `slice_seconds` of fuzzing per job, then a
  harvest pass that replays and classifies every new artifact. On
  crash-dense targets the harvest can take as long as the fuzzing;
  `status.txt` is updated after each full slice round.
- Ctrl+C is the supported stop: state is saved as `interrupted`
  and the same command resumes. (SIGINT only reaches the process
  with a normal interactive disposition — a campaign daemonized
  with SIGINT ignored by its parent shell will not stop this way;
  that is a shell property, not a campaign bug.)
- libFuzzer is the only backend for now. An AFL++ backend needs an
  AFL-instrumented target binary, which Kala does not build yet;
  the `Campaign` engine is where it would plug in.
- Slice stats (executions) are summed from each slice's libFuzzer
  log; treat them as a close approximation, not an audit trail.
- Crash dedup during a campaign keys on the triage stack hash, so
  `crashes/` holds exactly one representative per unique group —
  run `kala triage` over it later for minimization and full detail.
