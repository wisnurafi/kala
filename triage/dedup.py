"""Deduplicate analyzed crashes into unique groups.

Grouping key: (bug class, access direction, top application
function). Addresses, offsets and line numbers are normalized away —
they change between builds and even between runs of the same binary,
while the class/direction/function triple is the root-cause signal.

One merge rule exists beyond the key, and it exists because ASan
itself reports the same out-of-bounds access two ways: a
heap-buffer-overflow when the access lands in shadow-mapped memory,
or a SEGV when it lands too far out for the shadow map. SEGV groups
therefore merge into a buffer-overflow group with the same direction
and top function; an unmatched SEGV group stays its own group.

The stack hash is a stable fingerprint of the normalized application
stack, suitable for tracking a group across campaigns.

Standard library only.
"""

import hashlib
from dataclasses import dataclass, field

from .classify import CrashInfo
from .ingest import CrashRecord


@dataclass
class AnalyzedCrash:
    record: CrashRecord
    info: CrashInfo


@dataclass
class Group:
    bug_class: str
    direction: str | None
    top_function: str | None
    stack_hash: str
    members: list[AnalyzedCrash] = field(default_factory=list)
    merged_classes: list[str] = field(default_factory=list)

    @property
    def representative(self) -> AnalyzedCrash:
        """Smallest member input (ties: first by path) — the PoC."""
        return min(self.members, key=lambda m: (m.record.size,
                                                str(m.record.path)))

    @property
    def location(self):
        return self.representative.info.location


def stack_hash(info: CrashInfo) -> str:
    funcs = [fr.function for fr in info.app_frames[:4]]
    norm = "|".join([info.bug_class, info.direction or "-",
                     *[f or "?" for f in funcs]])
    return hashlib.sha256(norm.encode()).hexdigest()[:12]


def _key(info: CrashInfo) -> tuple[str, str | None, str | None]:
    loc = info.location
    return (info.bug_class, info.direction,
            loc.function if loc else None)


def group_crashes(analyzed: list[AnalyzedCrash]
                  ) -> tuple[list[Group], list[AnalyzedCrash]]:
    """Group crashing inputs; returns (groups, non-crashing)."""
    non_crashing = [a for a in analyzed if a.info.kind == "no-crash"]
    crashing = [a for a in analyzed if a.info.kind != "no-crash"]

    groups: dict[tuple, Group] = {}
    order: list[tuple] = []
    for a in crashing:
        key = _key(a.info)
        if key not in groups:
            loc = a.info.location
            groups[key] = Group(
                bug_class=key[0], direction=key[1], top_function=key[2],
                stack_hash=stack_hash(a.info))
            order.append(key)
        groups[key].members.append(a)

    # SEGV merge pass (see module docstring).
    for key in list(order):
        grp = groups.get(key)
        if grp is None or grp.bug_class != "SEGV-unknown":
            continue
        for target_key, target in groups.items():
            if target is grp:
                continue
            if target.bug_class.endswith("buffer-overflow") \
                    and target.direction == grp.direction \
                    and target.top_function == grp.top_function:
                target.members.extend(grp.members)
                target.merged_classes.append("SEGV-unknown")
                del groups[key]
                order.remove(key)
                break

    result = [groups[key] for key in order]
    result.sort(key=lambda g: (-len(g.members), g.bug_class,
                               g.top_function or ""))
    return result, non_crashing
