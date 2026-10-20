# Responsible disclosure

The procedure Kala findings follow when the target is someone
else's code. Every real target — private or public — follows
these rules, no exceptions.

## Rules of engagement

- **Only fuzz what may be fuzzed:** our own code, open-source
  code, or a target with explicit permission. Never a proprietary
  product, never a live service.
- **Isolation:** fuzzing runs in the VM/Docker environment, never
  on a work machine or a third party's network.
- **Nothing public before its time:** no PoC, screenshot, or
  "found a bug in X" post anywhere public until the embargo below
  ends. Unpatched PoCs are **never** pushed to this repo — not in
  `corpus/regression/`, not in an issue, not in a commit message.

## Before you report — verify

A maintainer's time is the scarcest resource in this process. Do
not send a report until all five hold:

1. **Clean reproduction** from a fresh build of the target's
   current release (or HEAD, if that's what was fuzzed): the PoC
   crashes the *unmodified* target, not just your harness build.
2. **Minimized PoC** — smallest input that still triggers the same
   class at the same location (`kala triage` minimization, verified
   by signature). Attach the minimized file, not the raw artifact.
3. **Root cause** in one paragraph: which field/index/size the
   input controls, which check is missing, where (file:line,
   function) the invalid access happens.
4. **Affected versions** — at minimum: the version fuzzed, and
   whether the latest release reproduces.
5. **Impact, stated honestly** — what the sanitizer proved (e.g.
   "out-of-bounds read of N bytes past a heap allocation when
   parsing a crafted file"), crash-only vs. plausibly exploitable,
   without inflating. A denial-of-service in a file parser is a
   valid report; it does not need to pretend to be RCE.

## The report

Send privately, through the channel the project documents —
`SECURITY.md`, a GitHub Security Advisory, or a maintainer's
security contact — never a public issue for an unpatched bug.

Include:

- Summary line: class, component, trigger ("heap-buffer-overflow
  READ in `parse_palette` when `bfOffBits` exceeds the file size").
- Affected version(s) + commit, build flags (sanitizers on).
- The minimized PoC (attached) and the exact replay command.
- The symbolized sanitizer report (trimmed to the crash stack).
- Root-cause paragraph and, if you have one, a suggested fix —
  offered as a suggestion, not a demand.
- Your disclosure timeline (below) and how to reach you.

Template:

```
Subject: [Security] <class> in <component> via crafted <format> file

Found with a coverage-guided fuzzer (libFuzzer + ASan/UBSan)
against <project> <version/commit>.

Summary: ...
Reproduction: <command>; PoC attached (N bytes).
Sanitizer report: <excerpt>
Root cause: ...
Affected: ...
Suggested fix (optional): ...

I follow a 90-day disclosure window from this message and am
happy to coordinate an earlier date with a release. Contact: ...
```

## Timeline

- **Day 0:** private report sent (above). Log the date, target,
  version, and contact in your private findings log.
- **Day 0–90:** embargo. Answer maintainer questions, verify their
  fix against your PoC (a fix is confirmed when the PoC stops
  crashing *and* the regression check for the surrounding behavior
  still passes), agree a release date if they ask.
- **Day 90, or patch release — whichever the maintainer and you
  agree on first:** disclosure closes. Only then: request a CVE via
  the maintainer / GitHub Security Advisory if the project uses
  them (a CVE is a bonus, never the goal), publish the write-up,
  and — with the fix public — the PoC may join
  `corpus/regression/` as a permanent test via `kala regress`.
- **No response by day 45:** one polite follow-up through the same
  channel, plus any alternate contact the project lists.
- **No response by day 90:** you may disclose the *existence and
  class* of the bug with a minimal technical description. Releasing
  a working PoC for a still-unpatched, still-maintained project
  needs a deliberate decision, not a calendar default — when in
  doubt, extend once and say so in the log.

## After disclosure

- Write-up (portfolio/blog): the format, the harness, how the
  campaign found it, the root cause, the fix. Link the advisory /
  fixed release. This is the L5 evidence.
- Update the findings log: status closed, CVE if any, links.
- If the campaign was clean instead — no crash in the full run —
  that is also a valid outcome: document the coverage reached,
  duration, and corpus state, and move on. A well-run clean
  campaign is a result, not a failure.
