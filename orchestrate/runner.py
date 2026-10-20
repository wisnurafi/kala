"""Campaign engine: unattended parallel fuzzing with resume.

A campaign runs libFuzzer jobs in parallel time slices. After each
slice the engine harvests new crash artifacts, classifies and
dedupes them with the triage pipeline, syncs corpora between jobs,
asks the scheduler whether to merge/reseed or scale up, and persists
state.json — so an interrupted campaign (Ctrl+C, VM reboot) resumes
by simply re-running the same `kala run` command, continuing from
the on-disk corpora until the configured time budget is consumed.

Layout under <output_dir>/<name>/:
  jobs/job-<i>/corpus, jobs/job-<i>/artifacts, jobs/job-<i>/logs/
  shared/    corpus units shared between jobs (merge target)
  crashes/   one representative per unique crash group
  state.json status.txt report.html (triage on finish)

Standard library only; subprocess via argument lists (section 9).
"""

import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from triage.classify import parse_sanitizer_output
from triage.dedup import AnalyzedCrash, group_crashes, stack_hash
from triage.ingest import CrashRecord, ingest_dir
from triage.report import ReportMeta, render_report
from triage.runner import find_symbolizer, fuzz_env, replay, replay_env

from .config import CampaignConfig
from .scheduler import Metrics, decide
from .status import render_status


class Campaign:
    def __init__(self, cfg: CampaignConfig, repo_root: Path,
                 binary: Path):
        self.cfg = cfg
        self.root = repo_root
        self.binary = binary
        self.dir = repo_root / cfg.output_dir / cfg.name
        self.shared = self.dir / "shared"
        self.crashes = self.dir / "crashes"
        self.state_path = self.dir / "state.json"
        self.symbolizer = find_symbolizer()
        self.env = replay_env(self.symbolizer)
        # Slices fuzz with symbolization off (see triage.runner
        # .fuzz_env); harvest and triage replay through self.env
        # and get full traces. Config can opt back in for debugging.
        self.fuzz_env = self.env if cfg.symbolize_slices \
            else fuzz_env(self.env)
        self.state = self._load_or_init_state()

    # -- state ------------------------------------------------------
    def _load_or_init_state(self) -> dict:
        if self.state_path.is_file():
            state = json.loads(self.state_path.read_text())
            state["status"] = "running"
            return state
        return {
            "name": self.cfg.name, "target": self.cfg.target,
            "status": "running",
            "budget_seconds": int(self.cfg.duration_minutes * 60),
            "elapsed_seconds": 0, "slices_completed": 0,
            "jobs": self.cfg.jobs, "total_execs": 0,
            "artifacts_seen": 0, "artifacts_unique": 0,
            "groups": {}, "seen_artifacts": [],
            "intervals_without_new_unique": 0,
            "merges": 0, "scale_ups": 0, "events": [],
        }

    def _save_state(self) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1))
        tmp.replace(self.state_path)
        (self.dir / "status.txt").write_text(render_status(self.state))

    def _event(self, kind: str, detail: str) -> None:
        self.state["events"].append(
            {"slice": self.state["slices_completed"], "kind": kind,
             "detail": detail})
        self.state["events"] = self.state["events"][-50:]
        print(f"  [event] {kind}: {detail}", file=sys.stderr)

    # -- setup --------------------------------------------------------
    def _job_dirs(self, idx: int) -> tuple[Path, Path, Path]:
        base = self.dir / "jobs" / f"job-{idx}"
        return base / "corpus", base / "artifacts", base / "logs"

    def _setup(self) -> None:
        self.shared.mkdir(parents=True, exist_ok=True)
        self.crashes.mkdir(parents=True, exist_ok=True)
        seeds = self.root / self.cfg.seed_corpus
        fresh = not any((self.dir / "jobs").glob("job-*")) \
            if (self.dir / "jobs").exists() else True
        for idx in range(self.state["jobs"]):
            corpus, artifacts, logs = self._job_dirs(idx)
            corpus.mkdir(parents=True, exist_ok=True)
            artifacts.mkdir(parents=True, exist_ok=True)
            logs.mkdir(parents=True, exist_ok=True)
            if fresh and seeds.is_dir():
                for seed in sorted(seeds.iterdir()):
                    if seed.is_file():
                        shutil.copyfile(seed, corpus / seed.name)

    # -- one slice ----------------------------------------------------
    def _run_job_slice(self, idx: int, slice_no: int) -> int:
        """Fuzz one job for a full slice of wall-clock time.

        A libFuzzer process exits at its first crash, long before
        -max_total_time — so the job is restarted in a loop until
        the slice's wall-clock budget is spent (the Phase 1 campaign
        pattern, productized). Returns summed executions.
        """
        corpus, artifacts, logs = self._job_dirs(idx)
        corpus.mkdir(parents=True, exist_ok=True)
        artifacts.mkdir(parents=True, exist_ok=True)
        logs.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.cfg.slice_seconds
        execs = 0
        run_no = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return execs
            run_no += 1
            cmd = [str(self.binary), str(corpus), str(self.shared),
                   f"-artifact_prefix={artifacts}/",
                   f"-max_total_time={max(1, int(remaining))}",
                   f"-max_len={self.cfg.max_len}"]
            if self.cfg.dictionary:
                cmd.append(f"-dict={self.root / self.cfg.dictionary}")
            log_path = logs / f"slice-{slice_no}-run-{run_no}.log"
            with log_path.open("w") as log_file:
                try:
                    subprocess.run(
                        cmd, stdout=log_file,
                        stderr=subprocess.STDOUT, env=self.fuzz_env,
                        timeout=remaining + 30)
                except subprocess.TimeoutExpired:
                    pass
            execs += _slice_execs(log_path)

    def _run_slice(self) -> None:
        slice_no = self.state["slices_completed"] + 1
        results: dict[int, int] = {}

        def worker(idx: int) -> None:
            results[idx] = self._run_job_slice(idx, slice_no)

        # Daemon threads + a polling join: a plain join() can park
        # the main thread past a SIGINT, making the campaign look
        # uninterruptible. Daemon workers die with the process; their
        # fuzzer children are time-capped and their artifacts are
        # picked up by the next resume's harvest.
        threads = [threading.Thread(target=worker, args=(idx,),
                                    daemon=True)
                   for idx in range(self.state["jobs"])]
        for t in threads:
            t.start()
        for t in threads:
            while t.is_alive():
                t.join(timeout=0.5)
        self.state["total_execs"] += sum(results.values())
        self.state["slices_completed"] = slice_no
        self.state["elapsed_seconds"] += self.cfg.slice_seconds

    def _harvest(self) -> int:
        """Classify new artifacts; returns # of new unique groups."""
        seen = set(self.state["seen_artifacts"])
        new_groups = 0
        for idx in range(self.state["jobs"]):
            _, artifacts, _ = self._job_dirs(idx)
            for art in sorted(artifacts.glob("*")):
                if not art.is_file() or art.name in seen:
                    continue
                seen.add(art.name)
                if art.name.startswith(("oom-", "timeout-")):
                    # Resource events, not crashes: count and skip so
                    # they never pollute the crash groups.
                    self.state["artifacts_aux"] = \
                        self.state.get("artifacts_aux", 0) + 1
                    continue
                self.state["artifacts_seen"] += 1
                result = replay(self.binary, art, timeout=15,
                                env=self.env)
                info = parse_sanitizer_output(
                    result.output, result.exit_code, result.timed_out)
                if info.kind == "no-crash":
                    continue
                digest = stack_hash(info)
                loc = info.location
                if digest in self.state["groups"]:
                    self.state["groups"][digest]["count"] += 1
                else:
                    dest = self.crashes / f"{digest}-{art.name}"
                    shutil.copyfile(art, dest)
                    self.state["groups"][digest] = {
                        "bug_class": info.bug_class,
                        "direction": info.direction,
                        "top_function": loc.function if loc else None,
                        "count": 1,
                        "first_seen_slice":
                            self.state["slices_completed"],
                        "representative": dest.name,
                    }
                    self.state["artifacts_unique"] += 1
                    new_groups += 1
        self.state["seen_artifacts"] = sorted(seen)
        return new_groups

    def _sync_corpus(self) -> None:
        existing = {p.name for p in self.shared.iterdir()}
        for idx in range(self.state["jobs"]):
            corpus, _, _ = self._job_dirs(idx)
            for unit in sorted(corpus.iterdir()):
                if unit.is_file() and unit.name not in existing \
                        and len(existing) < 5000:
                    shutil.copyfile(unit, self.shared / unit.name)
                    existing.add(unit.name)

    def _merge_and_reseed(self) -> None:
        merged = self.dir / "merged-tmp"
        if merged.exists():
            shutil.rmtree(merged)
        merged.mkdir()
        inputs = [str(self.shared)]
        for idx in range(self.state["jobs"]):
            corpus, _, _ = self._job_dirs(idx)
            inputs.append(str(corpus))
        subprocess.run([str(self.binary), "-merge=1", str(merged),
                        *inputs], capture_output=True, text=True,
                       env=self.fuzz_env, timeout=300)
        shutil.rmtree(self.shared)
        merged.replace(self.shared)
        self.state["merges"] += 1
        self.state["intervals_without_new_unique"] = 0

    # -- main loop ------------------------------------------------------
    def run(self) -> int:
        self._setup()
        self._save_state()
        print(f"campaign '{self.cfg.name}': "
              f"{self.state['elapsed_seconds']}s of "
              f"{self.state['budget_seconds']}s budget consumed, "
              f"{self.state['jobs']} jobs, slice "
              f"{self.cfg.slice_seconds}s", file=sys.stderr)
        try:
            while self.state["elapsed_seconds"] < \
                    self.state["budget_seconds"]:
                self._run_slice()
                new_groups = self._harvest()
                self._sync_corpus()
                if new_groups:
                    self.state["intervals_without_new_unique"] = 0
                    self._event("new-groups",
                                f"{new_groups} new unique group(s); "
                                f"total {len(self.state['groups'])}")
                else:
                    self.state["intervals_without_new_unique"] += 1
                metrics = Metrics(
                    elapsed_seconds=self.state["elapsed_seconds"],
                    unique_groups=len(self.state["groups"]),
                    new_unique_last_interval=new_groups,
                    intervals_without_new_unique=self.state[
                        "intervals_without_new_unique"],
                    active_jobs=self.state["jobs"])
                for action in decide(
                        metrics,
                        stagnation_intervals=self.cfg
                        .stagnation_intervals,
                        surge_threshold_per_hour=self.cfg
                        .surge_threshold_per_hour,
                        max_jobs=self.cfg.max_jobs):
                    if action.kind == "merge_and_reseed":
                        self._merge_and_reseed()
                    elif action.kind == "scale_up":
                        self.state["jobs"] += 1
                        self.state["scale_ups"] += 1
                    self._event(action.kind, action.reason)
                self._save_state()
                print(f"  slice {self.state['slices_completed']} done: "
                      f"{self.state['elapsed_seconds']}s elapsed, "
                      f"{len(self.state['groups'])} unique groups, "
                      f"{self.state['total_execs']} execs",
                      file=sys.stderr)
        except KeyboardInterrupt:
            self.state["status"] = "interrupted"
            self._save_state()
            print("interrupted — re-run the same command to resume",
                  file=sys.stderr)
            return 2
        self.state["status"] = "complete"
        self._save_state()
        if self.cfg.triage_on_finish and self.state["groups"]:
            self._triage()
        print(render_status(self.state))
        return 0

    def _triage(self) -> None:
        records = ingest_dir(self.crashes, all_files=True)
        analyzed = []
        for record in records:
            result = replay(self.binary, record.path, timeout=15,
                            env=self.env)
            info = parse_sanitizer_output(result.output,
                                          result.exit_code,
                                          result.timed_out)
            analyzed.append(AnalyzedCrash(record=record, info=info))
        groups, non_crashing = group_crashes(analyzed)
        for group in groups:
            group.minimized_path = None  # type: ignore[attr-defined]
            group.minimize_note = "campaign representative"  # type: ignore[attr-defined]
        meta = ReportMeta(
            target=self.cfg.target, binary_name=self.binary.name,
            total_inputs=len(records),
            crashing_inputs=len(records) - len(non_crashing),
            non_crashing=len(non_crashing),
            symbolized=any(a.info.symbolized for a in analyzed))
        (self.dir / "report.html").write_text(
            render_report(groups, meta), encoding="utf-8")
        self._event("triage", f"report.html written "
                    f"({len(groups)} groups)")


def _slice_execs(log_path: Path) -> int:
    """Executions of one fuzzer invocation, from its log.

    Prefers the final stat block; invocations that die by crashing
    never print it, so fall back to the last `#<n>` progress line.
    """
    try:
        text = log_path.read_text(errors="replace")
    except OSError:
        return 0
    total = 0
    for line in text.splitlines():
        if "stat::number_of_executed_units:" in line:
            try:
                total = int(line.rsplit(":", 1)[1])
            except ValueError:
                pass
        elif line.startswith("#"):
            try:
                total = max(total, int(line[1:].split(None, 1)[0]))
            except ValueError:
                pass
    return total


def load_state(campaign_dir: Path) -> dict | None:
    path = campaign_dir / "state.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())
