"""Promote a confirmed crash into the regression corpus.

    kala regress <poc> --target bmp_parser --name bug6_short_name \
        --expect-class heap-buffer-overflow --expect-function copy_rows \
        --bug "6 — short description" \
        --expected "ASan heap-buffer-overflow READ in copy_rows" \
        --trigger "one line on what in the input triggers it"

The PoC is replayed first and must crash with the expected class
(and top function, when given) — an unreproducing or mislabeled PoC
is refused, because a regression entry that does not crash is worse
than none: it turns CI green over a live bug. On success the file is
copied to corpus/regression/<target>/ and a row is appended to that
directory's README table, which is the human-readable contract CI
checks against (tools/check_regression.py holds the machine side).

Standard library only; subprocess via argument lists (section 9).
"""

import hashlib
import shutil
from pathlib import Path

from .classify import parse_sanitizer_output
from .runner import replay


class RegressError(Exception):
    pass


def _update_readme(readme: Path, target: str, row: str) -> None:
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        lines = text.splitlines()
        last_table = max(
            (i for i, ln in enumerate(lines) if ln.startswith("| `")),
            default=None)
        if last_table is None:
            raise RegressError(
                f"{readme} has no PoC table rows to append to; "
                "add the row by hand")
        lines.insert(last_table + 1, row)
        readme.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        readme.write_text(
            f"# Regression PoCs — {target}\n\n"
            "One fuzzer-found proof-of-crash per confirmed bug. Each "
            "file must\nreproduce its documented sanitizer report when "
            "replayed (CI does this on\nevery push — see "
            "tools/check_regression.py).\n\n"
            "| File | Bug | Expected report | Trigger, in one line |\n"
            "|---|---|---|---|\n"
            f"{row}\n", encoding="utf-8")


def add_regression_poc(binary: Path, poc: Path, regression_dir: Path,
                       name: str, expect_class: str,
                       expect_function: str | None, bug: str,
                       expected: str, trigger: str, env: dict,
                       timeout: float = 15.0,
                       force: bool = False) -> Path:
    """Verify, copy and document one PoC. Returns the destination."""
    if not poc.is_file():
        raise RegressError(f"PoC not found: {poc}")
    result = replay(binary, poc, timeout=timeout, env=env)
    info = parse_sanitizer_output(result.output, result.exit_code,
                                  result.timed_out)
    if info.kind == "no-crash":
        raise RegressError(
            f"{poc.name} does not crash on replay — refusing to add "
            "a regression entry that cannot fail")
    if info.bug_class != expect_class:
        raise RegressError(
            f"class mismatch: expected {expect_class}, replay gives "
            f"{info.bug_class} ({info.raw_class})")
    loc = info.location
    if expect_function and (loc is None
                             or loc.function != expect_function):
        raise RegressError(
            f"function mismatch: expected {expect_function}, replay "
            f"location is {loc.function if loc else None}")

    digest = hashlib.sha256(poc.read_bytes()).hexdigest()
    regression_dir.mkdir(parents=True, exist_ok=True)
    for existing in sorted(regression_dir.iterdir()):
        if existing.is_file() and existing.suffix == poc.suffix and \
                hashlib.sha256(existing.read_bytes()).hexdigest() == digest:
            raise RegressError(
                f"identical bytes already in the corpus as "
                f"{existing.name} — not adding a duplicate")

    dest = regression_dir / f"{name}{poc.suffix}"
    if dest.exists() and not force:
        raise RegressError(f"{dest} already exists (pass --force to "
                           "replace the file; the README row is kept)")
    shutil.copyfile(poc, dest)

    readme = regression_dir / "README.md"
    row = (f"| `{dest.name}` | {bug} | {expected} | {trigger} |")
    if force and readme.is_file() and f"`{dest.name}`" in readme.read_text(
            encoding="utf-8"):
        pass  # replacing the file of an already-documented PoC
    else:
        _update_readme(readme, regression_dir.name, row)
    return dest
