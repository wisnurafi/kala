"""Parse sanitizer output into a structured crash classification.

Input is the combined stdout/stderr of replaying one crash input
through an instrumented binary. Output is a CrashInfo: which bug
class the sanitizer proved, the access direction, and where (the top
application frame).

Labels follow the Phase 2 taxonomy: heap-buffer-overflow,
stack-buffer-overflow, heap-use-after-free, integer-overflow,
SEGV-unknown, plus the sanitizer's own classes where they are more
precise (double-free, memory-leak, undefined-behavior, ...).

Standard library only.
"""

import re
from dataclasses import dataclass, field

# Frames from the sanitizer/fuzzer/libc runtime are not application
# code; they are identical for every crash and useless for triage.
_RUNTIME_FUNC_PREFIXES = (
    "__asan", "__interceptor", "__ubsan", "__sanitizer", "fuzzer::",
    "__libc", "__clone",
)
_RUNTIME_FILE_HINTS = (
    "libsanitizer", "compiler-rt", "libc.so", "libstdc++", "Fuzzer",
    "sanitizer_common", "ubsan",
)

# Small static helpers that compilers inline into their callers.
# Whether llvm-symbolizer attributes a crash to the helper or to its
# caller depends on inlining decisions that vary between compilers
# and versions (observed: clang 18 attributes a palette read to
# parse_palette, clang 21 can attribute the same read to get_u32le).
# These names are accessors, never root causes: location and stack
# hash use the first frame that is not one of them.
_INLINE_HELPERS = frozenset({
    "get_u16le", "get_u32le", "get_i32le",
})

_ASAN_HEADER = re.compile(r"ERROR: AddressSanitizer: ([a-z][a-zA-Z-]*)")
_ASAN_ATTEMPT = re.compile(r"ERROR: AddressSanitizer: attempting ([a-z-]+)")
_ASAN_SEGV = re.compile(r"ERROR: AddressSanitizer: SEGV on unknown address")
_LEAK_HEADER = re.compile(r"ERROR: LeakSanitizer: detected memory leaks")
_ACCESS = re.compile(r"\b(READ|WRITE) of size (\d+)")
_SEGV_ACCESS = re.compile(r"caused by a (READ|WRITE) memory access")
_UBSAN = re.compile(r"^(.+?):(\d+):(\d+): runtime error: (.*)$", re.M)
_FRAME = re.compile(r"^\s+#(\d+)\s+0x[0-9a-f]+\s+(.*)$", re.M)
_FRAME_LOC = re.compile(r"(\S+?\.(?:c|cc|cpp|cxx|h|hpp)):(\d+)")


@dataclass
class Frame:
    function: str | None
    file: str | None  # basename only
    line: int | None


@dataclass
class CrashInfo:
    kind: str  # asan | ubsan | timeout | crash-unknown | no-crash
    bug_class: str  # normalized label, e.g. heap-buffer-overflow
    raw_class: str  # as reported by the sanitizer, before normalization
    direction: str | None  # READ | WRITE | None
    access_size: int | None
    frames: list[Frame] = field(default_factory=list)
    symbolized: bool = False
    excerpt: str = ""  # the sanitizer report, trimmed, for the HTML report

    @property
    def app_frames(self) -> list[Frame]:
        """Frames in application code (runtime frames filtered out)."""
        out = []
        for fr in self.frames:
            if fr.function is None or fr.file is None:
                continue
            if fr.function.startswith(_RUNTIME_FUNC_PREFIXES):
                continue
            if any(hint in (fr.file or "") for hint in _RUNTIME_FILE_HINTS):
                continue
            out.append(fr)
        return out

    @property
    def normalized_frames(self) -> list[Frame]:
        """Application frames with leading inline helpers skipped.

        See _INLINE_HELPERS: the same crash must yield the same
        location and stack hash regardless of how the compiler
        inlined an accessor into its caller. If every frame is a
        helper, the last one is kept so location is never lost.
        """
        app = self.app_frames
        i = 0
        while i < len(app) - 1 and app[i].function in _INLINE_HELPERS:
            i += 1
        return app[i:]

    @property
    def location(self) -> Frame | None:
        app = self.normalized_frames
        return app[0] if app else None

    @property
    def severity(self) -> str:
        high = {"heap-use-after-free", "stack-buffer-overflow",
                "global-buffer-overflow", "double-free",
                "integer-overflow"}
        if self.bug_class in high:
            return "high"
        if self.bug_class == "heap-buffer-overflow":
            return "high" if self.direction == "WRITE" else "medium"
        if self.bug_class == "memory-leak":
            return "low"
        if self.bug_class == "timeout":
            return "low"
        return "medium"


def parse_frames(output: str) -> list[Frame]:
    """Frames of the FIRST stack trace in the output.

    Sanitizer reports contain auxiliary stacks ("allocated by",
    "freed by", "previously allocated by") after the crash stack.
    They describe other code paths entirely; including them poisons
    both the reported location and the stack hash, so parsing stops
    when the frame numbering restarts.
    """
    frames = []
    prev_idx = -1
    for m in _FRAME.finditer(output):
        idx = int(m.group(1))
        if idx <= prev_idx:
            break
        prev_idx = idx
        rest = m.group(2)
        function = None
        file = None
        line = None
        loc = _FRAME_LOC.search(rest)
        if loc:
            file = loc.group(1).rsplit("/", 1)[-1]
            line = int(loc.group(2))
            head = rest[: loc.start()].strip()
            if head.startswith("in "):
                head = head[3:]
            function = head.split()[0] if head.split() else None
            if function and function.startswith("("):
                function = None
        frames.append(Frame(function=function, file=file, line=line))
    return frames


def _excerpt(output: str, limit: int = 45) -> str:
    """The sanitizer report, trimmed for display in the HTML report.

    PIDs and raw addresses are normalized away: they change on every
    replay, and the report must be byte-identical across runs.
    """
    lines = output.splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if "ERROR: AddressSanitizer" in ln or "runtime error:" in ln \
                or "ERROR: LeakSanitizer" in ln:
            start = i
            break
    text = "\n".join(lines[start:start + limit])
    text = re.sub(r"==\d+== ?", "", text)
    text = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", text)
    return text


def parse_sanitizer_output(output: str, exit_code: int,
                           timed_out: bool = False) -> CrashInfo:
    """Classify one replay. `output` is combined stdout+stderr."""
    frames = parse_frames(output)
    symbolized = any(fr.function and fr.file and fr.line for fr in frames)
    excerpt = _excerpt(output)

    if timed_out:
        return CrashInfo("timeout", "timeout", "timeout", None, None,
                         frames, symbolized, excerpt)

    if "ERROR: libFuzzer: out-of-memory" in output:
        return CrashInfo("oom", "oom", "oom", None, None,
                         frames, symbolized, excerpt)
    if "ERROR: libFuzzer: timeout after" in output:
        return CrashInfo("timeout", "timeout", "timeout", None, None,
                         frames, symbolized, excerpt)

    direction = None
    access_size = None
    m = _ACCESS.search(output)
    if m:
        direction = m.group(1)
        access_size = int(m.group(2))

    if _LEAK_HEADER.search(output):
        return CrashInfo("asan", "memory-leak", "memory-leak", direction,
                         access_size, frames, symbolized, excerpt)

    if _ASAN_SEGV.search(output):
        if direction is None:
            m2 = _SEGV_ACCESS.search(output)
            if m2:
                direction = m2.group(1)
        return CrashInfo("asan", "SEGV-unknown", "SEGV", direction,
                         access_size, frames, symbolized, excerpt)

    m = _ASAN_ATTEMPT.search(output)
    if m:
        what = m.group(1)
        bug_class = "double-free" if what == "double-free" else "invalid-free"
        return CrashInfo("asan", bug_class, f"attempting {what}", direction,
                         access_size, frames, symbolized, excerpt)

    m = _ASAN_HEADER.search(output)
    if m:
        raw = m.group(1).strip()
        return CrashInfo("asan", raw, raw, direction, access_size,
                         frames, symbolized, excerpt)

    m = _UBSAN.search(output)
    if m:
        msg = m.group(4).strip()
        bug_class, raw = _classify_ubsan(msg)
        return CrashInfo("ubsan", bug_class, raw, direction, access_size,
                         frames, symbolized, excerpt)

    if exit_code == 0:
        return CrashInfo("no-crash", "no-crash", "no-crash", None, None,
                         frames, symbolized, "")
    return CrashInfo("crash-unknown", "crash-unknown", "crash-unknown",
                     direction, access_size, frames, symbolized, excerpt)


def _classify_ubsan(msg: str) -> tuple[str, str]:
    """Map a UBSan runtime-error message to a taxonomy label."""
    if "out of bounds for type" in msg:
        # UBSan bounds fires on fixed-size arrays (stack/global). In a
        # parser the overwhelmingly common case is a local array, and
        # ASan would call the same access a stack-buffer-overflow.
        return "stack-buffer-overflow", "ubsan-index-oob"
    if "integer overflow" in msg:
        return "integer-overflow", "ubsan-integer-overflow"
    if "division by zero" in msg:
        return "integer-divide-by-zero", "ubsan-divide-by-zero"
    if "shift" in msg:
        return "undefined-shift", "ubsan-shift"
    if "null" in msg or "nullptr" in msg:
        return "null-dereference", "ubsan-null"
    return "undefined-behavior", "ubsan"
