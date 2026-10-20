"""Render the triage result as one self-contained HTML file.

No external assets, no JavaScript, works offline. The output is
deterministic — the same inputs produce a byte-identical report
(no timestamps or absolute paths), which the Phase 2 validation
verifies by hashing two consecutive runs.

Standard library only (the roadmap's Jinja2 slot lives here; a
single render function keeps the swap trivial if it is ever needed).
"""

import base64
import html
from dataclasses import dataclass, field
from pathlib import Path

from .dedup import Group

_CSS = """
body { font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 62rem;
       padding: 0 1rem; color: #1b1c22; }
h1 { font-size: 1.5rem; } h2 { font-size: 1.15rem; margin-top: 2rem; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ccc; padding: 0.35rem 0.6rem; text-align: left;
         font-size: 0.92rem; }
th { background: #f0f0f3; }
pre { background: #f6f6f8; border: 1px solid #ddd; padding: 0.8rem;
      overflow-x: auto; font-size: 0.8rem; }
.sev-high { color: #b00020; font-weight: 700; }
.sev-medium { color: #9a6a00; font-weight: 700; }
.sev-low { color: #555; font-weight: 700; }
.warn { background: #fff4e0; border: 1px solid #e0a800; padding: 0.6rem 1rem; }
.meta { color: #444; }
code { background: #f0f0f3; padding: 0 0.25rem; }
"""


@dataclass
class StateGroup:
    """One crash group as recorded in a campaign's state.json.

    Campaign reports reconcile these against the standalone replay:
    a group whose representative no longer crashes on its own (a
    heap-layout-dependent or timeout-flavoured find) must stay
    visible in the report, marked not-reproduced — never silently
    dropped, which is what happened to 2 of 3 groups in the Phase 3
    VM QA report.
    """
    stack_hash: str
    bug_class: str
    direction: str | None
    top_function: str | None
    count: int
    representative: str
    reproduced: bool


@dataclass
class ReportMeta:
    target: str
    binary_name: str
    total_inputs: int
    crashing_inputs: int
    non_crashing: int
    symbolized: bool
    state_groups: list[StateGroup] = field(default_factory=list)


def _esc(text: object) -> str:
    return html.escape(str(text))


def _poc_link(group: Group) -> str:
    """Base64-embedded download link for the group's best PoC."""
    minimized = getattr(group, "minimized_path", None)
    if minimized is not None:
        path = Path(minimized)
        label = f"minimized PoC ({path.stat().st_size} bytes)"
    else:
        path = group.representative.record.path
        label = f"PoC ({path.stat().st_size} bytes)"
    data = base64.b64encode(path.read_bytes()).decode()
    name = _esc(path.name)
    return (f'<a download="{name}" '
            f'href="data:application/octet-stream;base64,{data}">'
            f'{_esc(label)}</a>')


def render_report(groups: list[Group], meta: ReportMeta) -> str:
    parts = ["<!DOCTYPE html>",
             '<html lang="en"><head><meta charset="utf-8">',
             f"<title>Kala triage — {_esc(meta.target)}</title>",
             f"<style>{_CSS}</style></head><body>",
             f"<h1>Kala triage — {_esc(meta.target)}</h1>",
             f'<p class="meta">Binary: <code>{_esc(meta.binary_name)}</code>'
             f" · Inputs: {meta.total_inputs}"
             f" · Crashing: {meta.crashing_inputs}"
             f" · Non-crashing: {meta.non_crashing}"
             f" · Unique groups: {len(groups)}</p>"]
    if not meta.symbolized:
        parts.append(
            '<p class="warn"><strong>Warning:</strong> sanitizer traces '
            "were not symbolized (no llvm-symbolizer or addr2line found, "
            "or the binary lacks debug info). Grouping by stack trace "
            "is unreliable in this state.</p>")

    parts.append("<h2>Groups</h2><table><tr><th>#</th><th>Class</th>"
                 "<th>Severity</th><th>Location</th><th>Count</th>"
                 "<th>Stack hash</th><th>PoC</th></tr>")
    for i, g in enumerate(groups, 1):
        loc = g.location
        loc_text = (f"{loc.function} ({loc.file}:{loc.line})"
                    if loc else "(unknown)")
        merged = (f" <span class='meta'>[+{', '.join(g.merged_classes)} "
                  "merged]</span>" if g.merged_classes else "")
        parts.append(
            f"<tr><td>G{i}</td><td>{_esc(g.bug_class)}{merged}</td>"
            f"<td class='sev-{g.representative.info.severity}'>"
            f"{g.representative.info.severity}</td>"
            f"<td>{_esc(loc_text)}</td><td>{len(g.members)}</td>"
            f"<td><code>{g.stack_hash}</code></td>"
            f"<td>{_poc_link(g)}</td></tr>")
    parts.append("</table>")

    if meta.state_groups:
        by_hash = {g.stack_hash: i for i, g in enumerate(groups, 1)}
        parts.append("<h2>Campaign state reconciliation</h2>")
        parts.append(
            "<p>Every group the campaign recorded in "
            "<code>state.json</code>, checked against this standalone "
            "replay of its representative. A group marked "
            "<strong>not reproduced</strong> did not crash when "
            "replayed on its own — typically a heap-layout-dependent "
            "or timeout-flavoured find. It is kept here, not dropped: "
            "investigate it from the campaign artifacts before "
            "dismissing it.</p>")
        parts.append("<table><tr><th>Stack hash</th><th>Class</th>"
                     "<th>Location</th><th>Seen in campaign</th>"
                     "<th>Representative</th><th>Reproduction</th></tr>")
        for sg in meta.state_groups:
            if sg.reproduced and sg.stack_hash in by_hash:
                repro = f"reproduced (G{by_hash[sg.stack_hash]})"
            elif sg.reproduced:
                repro = "reproduced"
            else:
                repro = "NOT REPRODUCED"
            parts.append(
                f"<tr><td><code>{_esc(sg.stack_hash)}</code></td>"
                f"<td>{_esc(sg.bug_class)}</td>"
                f"<td>{_esc(sg.top_function or '(unknown)')}</td>"
                f"<td>{sg.count}</td>"
                f"<td><code>{_esc(sg.representative)}</code></td>"
                f"<td>{_esc(repro)}</td></tr>")
        parts.append("</table>")

    for i, g in enumerate(groups, 1):
        rep = g.representative
        loc = g.location
        loc_text = (f"{loc.function} ({loc.file}:{loc.line})"
                    if loc else "(unknown)")
        parts.append(f"<h2>G{i} — {_esc(g.bug_class)}</h2>")
        parts.append(
            f"<p>Direction: {_esc(g.direction or '-')} · "
            f"Representative: <code>{_esc(rep.record.path.name)}</code> · "
            f"Minimization: {_esc(getattr(g, 'minimize_note', 'not run'))}"
            f"<br>Location: {_esc(loc_text)} · "
            f"Stack hash: <code>{g.stack_hash}</code></p>")
        parts.append("<p>Members: "
                     + ", ".join(f"<code>{_esc(m.record.path.name)}</code>"
                                 for m in sorted(
                                     g.members,
                                     key=lambda m: m.record.path.name))
                     + "</p>")
        parts.append(f"<pre>{_esc(rep.info.excerpt)}</pre>")

    parts.append("<p class='meta'>Generated by kala triage. "
                 "Deterministic output: identical inputs produce an "
                 "identical report.</p>")
    parts.append("</body></html>")
    return "\n".join(parts) + "\n"
