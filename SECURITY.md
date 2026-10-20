# Security Policy — Kala

Kala is a vulnerability-discovery toolkit: it is built to find
security bugs in other software. This policy covers vulnerabilities
**in Kala itself**. For vulnerabilities Kala finds in *other*
projects, see "Findings in third-party targets" below.

## Reporting a vulnerability in Kala

- **Preferred channel:** open a private GitHub Security Advisory
  for this repository.
- If GitHub Advisories are unavailable, contact the maintainer
  privately through GitHub — do **not** open a public issue with
  exploit details.
- Include: affected component (harness, triage, orchestrate, a
  vendored target, CI), version/commit, reproduction steps, and a
  minimal proof-of-concept if you have one.

What to expect:

- Acknowledgement within 72 hours.
- Triage and a severity estimate within 7 days.
- A fix or mitigation plan after triage; public disclosure is
  coordinated with the reporter and normally happens after a patch
  is available, or within 90 days.

## Findings in third-party targets

Bugs that Kala discovers in the software it fuzzes are **not**
reported here. They follow
[`docs/responsible-disclosure.md`](docs/responsible-disclosure.md):

- Private report to the affected maintainer first; nothing is
  published before the maintainer has had a fair window.
- 90-day embargo, with a follow-up at day 45.
- A proof-of-concept for an unpatched bug never enters this
  repository.
- The public write-up comes after the fix (or after the embargo),
  and credits the reporter and the maintainer's response.

## Safe use / rules of engagement

- Only fuzz code you wrote, open-source code, or targets you have
  explicit permission to test.
- Run campaigns in an isolated environment (a dedicated VM or the
  provided Docker image) — never on a production host or a work
  network.
- Kala runs entirely locally: it has no telemetry, no accounts and
  no network calls of its own. Campaign state, corpora and reports
  stay on your machine unless you move them.
