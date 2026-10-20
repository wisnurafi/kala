# Setup

Goal: zero to first fuzzing run in under 30 minutes, and a working
triage + campaign loop right after. Everything below is the exact
flow used to validate Kala itself, and the flow every campaign
follows today.

## 1. Linux environment

Primary: a Debian/Ubuntu VM (VMware / VirtualBox / Hyper-V). The VM
is where building and fuzzing happen; development (writing code)
happens on the host in an editor, and git is the only bridge — the
repo is the source of truth, never a copy edited inside the VM.

Alternative: the Docker image in `docker/`.

Toolchain the repo expects:

| Tool | Why |
|---|---|
| clang / clang++ | sanitizer + libFuzzer support |
| llvm-symbolizer (package `llvm`) | symbolized ASan traces — see §5 |
| cmake ≥ 3.20 | presets in `CMakePresets.json` |
| python3 ≥ 3.11 | triage + orchestration (standard library only) |
| gdb (optional) | manual verification, see `triage-guide.md` |
| AFL++ (optional) | only for the AFL++ harness path |

For AFL++, also set the core pattern once (the VM setup script
reminds you):

```sh
echo core | sudo tee /proc/sys/kernel/core_pattern
```

Take a VM snapshot after the toolchain is installed and again after
your first successful campaign — campaign state does not belong in
`/tmp` (a restart wiped an early campaign's artifacts; state now
lives under `campaigns/` in the repo working tree or wherever
`output_dir` points).

## 2. Build

```sh
cmake --preset fuzzer-asan-ubsan
cmake --build --preset fuzzer-asan-ubsan -j
```

Presets: `asan` (ASan only), `asan-ubsan`, `fuzzer-asan-ubsan`
(libFuzzer + ASan/UBSan — the campaign profile). Target code must be
compiled with `-fsanitize=fuzzer-no-link` when it is linked into a
libFuzzer binary; without it coverage stays blind (calibration found
3 PCs / cov 2 and a 23-second crash hunt that dropped to 0.07 s
once the flag was right).

## 3. First fuzzing run (hello target)

```sh
mkdir -p findings-hello
./build-fuzzer/harness/libfuzzer/hello_fuzzer findings-hello corpus/hello \
  -dict=harness/dicts/hello.dict -max_total_time=60
```

Done when: a `crash-*` artifact appears in `findings-hello/` in
under 60 seconds and its log shows an ASan `heap-buffer-overflow`
in `kala_hello_parse`.

## 4. The full loop, once

```sh
# Fuzz the practice target
mkdir -p findings-bmp
./build-fuzzer/harness/libfuzzer/bmp_fuzzer findings-bmp corpus/bmp \
  -dict=harness/dicts/bmp.dict -max_total_time=300

# Triage whatever it found into a self-contained report
./kala triage findings-bmp --target bmp_parser --out report.html

# Or run an unattended campaign (slices, merging, scaling, resume)
./kala run --config examples/campaign.yaml
./kala status --config examples/campaign.yaml

# Sanity: every regression PoC still crashes as documented
python3 tools/check_regression.py
```

## 5. Troubleshooting

- **ASan traces show bare addresses, no function names.** The
  symbolizer is missing and triage is effectively blind — stack
  traces are the grouping signal. Install `llvm`, or rely on the
  automatic fallback: the triage runner injects
  `ASAN_OPTIONS=external_symbolizer_path=/usr/bin/addr2line` when
  no llvm-symbolizer is in PATH. `kala triage` warns loudly when
  traces are not symbolized; do not ignore that warning.
- **Fuzzer finds nothing and coverage is flat.** Check the three
  usual suspects in order: sanitizer actually linked? seeds valid
  for the format? dictionary present (`-dict=`)? See
  `harness-writing.md` for the longer checklist.
- **A "30-second slice" finishes in seconds.** A libFuzzer process
  exits at its first crash; `kala run` restarts jobs in a loop
  until the slice's wall-clock budget is spent. Raw libFuzzer runs
  do not — that is expected, not a bug.
- **Throughput is far lower in the VM than elsewhere.** Campaign
  slices run with symbolization off (`symbolize=0`) because every
  symbolized crash spawns a symbolizer process; harvest and triage
  replay with full traces. Set `symbolize_slices: true` in the
  campaign config only when debugging a campaign live.

## 6. Portability check

```sh
grep -rn "windows.h" --include="*.c" --include="*.h" \
  --include="*.cpp" --include="*.hpp" .
# must print nothing
```

CI runs this check, both unit-test suites, the build, and the
regression replay on every push.
