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
from dataclasses import dataclass
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
class ReportMeta:
    target: str
    binary_name: str
    total_inputs: int
    crashing_inputs: int
    non_crashing: int
    symbolized: bool


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
