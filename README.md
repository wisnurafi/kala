# Kala

Vulnerability discovery toolkit: a coverage-guided fuzzing and
triage pipeline that breaks software systematically to find
security bugs before someone else does.

Kala combines libFuzzer and sanitizers (ASan/UBSan) with a Python
pipeline that turns raw crashes into deduplicated, minimized,
classified reports — and a campaign engine that runs the whole
thing unattended for days, resuming where it left off after any
interruption.

> Named after Kala, the Javanese deity of destruction and time.

## What Kala does

```
seeds + dictionary ──► libFuzzer campaign (slices, parallel jobs)
                            │  crashes / timeouts / OOMs
                            ▼
                     harvest & classify ──► dedup by stack hash
                            │                    │
                            ▼                    ▼
                     scheduler:            state.json (resume)
                     stagnate → merge+reseed
                     surge    → add a job
                            │
                            ▼
                     triage report (HTML): grouped, minimized,
                     reproducible PoCs — or it didn't happen
```

Everything is validated against ground truth, not vibes: the
practice target ships with five planted bug classes, and the
pipeline is calibrated to find 5/5 of them and group 590 raw
crashes into exactly the 5 right reports (see
`docs/calibration-notes.md`).

## Components

- **Harness layer** (`harness/`) — one thin libFuzzer harness per
  target, sanitizer profiles (ASan, ASan+UBSan, MSan) and token
  dictionaries per format. Target code is always built with
  `-fsanitize=fuzzer-no-link`, or the engine gets no coverage
  feedback and fuzzes blind.
- **Triage** (`triage/`) — ingest → replay → classify → dedup →
  minimize → report. Pure Python standard library. Reports are
  deterministic: identical inputs produce a byte-identical HTML
  file, with PoCs embedded for download.
- **Orchestration** (`orchestrate/`) — campaign engine: parallel
  jobs in wall-clock slices, crash harvesting, a metric-driven
  scheduler (stagnation → merge & reseed; surge → scale up),
  persistent state with resume, and automatic triage when the
  budget is consumed.
- **Regression lab** (`tools/`, `corpus/regression/`) — every
  confirmed crash is promoted to a permanent regression PoC with
  `kala regress`; CI replays all of them against a fresh build on
  every push, plus a weekly fuzz smoke.
- **Targets** (`targets/`) — a practice parser with planted bugs
  for calibration, and real open-source parsers vendored
  unmodified at pinned commits (see the table below).

## Included targets

| Target | What it is | Role |
|---|---|---|
| `hello` | Dummy parser, one planted overflow behind a magic | Smoke test: proves a new setup end to end in seconds |
| `bmp_parser` | Hand-written BMP parser (C), 5 planted bug classes | Calibration ground truth (`targets/bmp_parser/PLANTED_BUGS.md`) |
| `inih` | [benhoyt/inih](https://github.com/benhoyt/inih) at `2bbdec4` (BSD-3) | Real target, heap line-buffer configuration |
| `tomlc17` | [cktan/tomlc17](https://github.com/cktan/tomlc17) at `85000d0` (MIT) | Real target, TOML v1.1 parser in upstream default configuration |

Vendored files are byte-identical snapshots of upstream (verified
by git blob hash at vendoring time) and are never edited; all
configuration lives in each target's `CMakeLists.txt` and harness.

## Quick start

Build and fuzz inside a Linux VM (or the Docker image in
`docker/`); see `docs/setup.md` for environment setup.

```sh
# Build everything (libFuzzer + ASan + UBSan)
cmake --preset fuzzer-asan-ubsan
cmake --build --preset fuzzer-asan-ubsan -j

# Smoke test: the hello target must crash within seconds
mkdir -p findings-hello
./build-fuzzer/harness/libfuzzer/hello_fuzzer findings-hello corpus/hello \
  -dict=harness/dicts/hello.dict -max_total_time=60

# Sanity: unit tests + regression replay
python3 -m unittest discover -s triage/tests -t .
python3 -m unittest discover -s orchestrate/tests -t .
python3 tools/check_regression.py
```

## Usage

One CLI, four verbs (`./kala`):

```sh
# Run (or resume) a campaign from a YAML config
./kala run --config examples/campaign-tomlc17.yaml
./kala status --config examples/campaign-tomlc17.yaml

# Triage a directory of raw crashes into a report
./kala triage ./crashes --target bmp_parser --out report.html

# Promote a confirmed PoC into the regression corpus
./kala regress <poc> --target bmp_parser --name bug6_short_name \
  --expect-class heap-buffer-overflow --expect-function copy_rows \
  --bug "..." --expected "..." --trigger "..."
```

Campaign configs live in `examples/` (`campaign.yaml` demo,
`campaign-inih.yaml`, `campaign-tomlc17.yaml`). A campaign is
resumable by design: Ctrl+C marks it `interrupted`, and re-running
the same command continues until the full time budget is consumed.
Two ready campaigns run continuously on the maintainer's fuzzing
VM — a 24-hour inih validation and a 48-hour tomlc17 hunt.

## Repository layout

```
harness/        libFuzzer & AFL++ harnesses, sanitizer profiles, dictionaries
targets/        Practice target + vendored real targets (pinned, read-only)
corpus/         Seed corpora per target; regression/ holds permanent PoCs
triage/         Python: ingest -> replay -> classify -> dedup -> minimize -> report
orchestrate/    Python: campaign engine (YAML config, slices, scheduler, state)
examples/       Ready-to-run campaign configurations
tools/          Regression replay checker (used by CI)
docker/         Reproducible fuzzing environment (alternative to the VM)
docs/           Setup, harness writing, triage and disclosure guides
```

The full map is in [`roadmap.txt`](roadmap.txt).

## Documentation

- [`docs/setup.md`](docs/setup.md) — VM and Docker setup
- [`docs/harness-writing.md`](docs/harness-writing.md) — writing a
  harness that tells the truth
- [`docs/triage-guide.md`](docs/triage-guide.md) — reading and
  trusting triage reports
- [`docs/responsible-disclosure.md`](docs/responsible-disclosure.md)
  — the disclosure SOP for real findings
- [`docs/calibration-notes.md`](docs/calibration-notes.md) — how
  every component was validated, with the numbers
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contributor guide and
  hard rules
- [`SECURITY.md`](SECURITY.md) — reporting vulnerabilities in Kala
  itself

## Cross-platform rules

Strict, from day one:

- C11 / C++17 standard only, plus POSIX. No `windows.h`, no Win32
  API, no MSVC extensions.
- CMake is the only build system; clang is the compiler.
- Python orchestration is standard-library only.
- LF line endings and UTF-8 everywhere (enforced by
  `.gitattributes`).
- No hardcoded Windows paths or backslash separators.

CI enforces the `windows.h` ban on every push:

```sh
grep -rn "windows\.h" --include="*.c" --include="*.h" \
  --include="*.cpp" --include="*.hpp" .
# must print nothing
```

## Rules of engagement

- Only fuzz code you wrote, open-source code, or targets with
  explicit permission.
- Fuzz inside an isolated VM (or Docker) — never on a production
  host or a work network.
- Real bugs are disclosed privately to the maintainer first, with
  a 90-day embargo before any publication. A PoC for an unpatched
  bug never enters this repository.
- Kala runs entirely locally: no telemetry, no accounts, no data
  collection. (That is also why there is no PRIVACY.md — there is
  nothing to put in it.)

## License

MIT — see [`LICENSE`](LICENSE). Vendored targets keep their own
licenses in their directories (`targets/inih/LICENSE.txt`,
`targets/tomlc17/LICENSE`).
