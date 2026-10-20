"""Unit tests for triage.classify, using sanitizer output shapes
captured from the Phase 1 bmp_parser campaign (trimmed)."""

import unittest

from triage.classify import parse_sanitizer_output

HBO_READ = """\
==100==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x508000000076
READ of size 48 at 0x508000000076 thread T0
    #0 0xaaa in __asan_memcpy (/bin/bmp_fuzzer+0xffc35)
    #1 0xbbb in copy_rows /src/targets/bmp_parser/bmp_parser.c:68:5
    #2 0xccc in bmp_parse /src/targets/bmp_parser/bmp_parser.c:138:5
    #3 0xddd in LLVMFuzzerTestOneInput /src/harness/libfuzzer/bmp_fuzzer.cpp:15:7
SUMMARY: AddressSanitizer: heap-buffer-overflow in __asan_memcpy
"""

UAF_WRITE = """\
==101==ERROR: AddressSanitizer: heap-use-after-free on address 0x5100000000e8
WRITE of size 24 at 0x5100000000e8 thread T0
    #0 0xaaa in __asan_memcpy (/bin/bmp_fuzzer+0xffc35)
    #1 0xbbb in copy_rows /src/targets/bmp_parser/bmp_parser.c:68:5
    #2 0xccc in bmp_parse /src/targets/bmp_parser/bmp_parser.c:138:5
SUMMARY: AddressSanitizer: heap-use-after-free in __asan_memcpy
"""

SEGV_WRITE = """\
==102==ERROR: AddressSanitizer: SEGV on unknown address 0x5106000000e8
The signal is caused by a WRITE memory access.
    #0 0xaaa in __asan_memcpy (/bin/bmp_fuzzer+0xa)
    #2 0xccc in copy_rows /src/targets/bmp_parser/bmp_parser.c:68:5
SUMMARY: AddressSanitizer: SEGV (/lib/libc.so.6+0x1a16fa)
"""

STACK_ASAN = """\
==103==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x71d419c00420
WRITE of size 1200 at 0x71d419c00420 thread T0
    #0 0xaaa in __asan_memcpy (/bin/bmp_fuzzer+0xa)
    #1 0xbbb in parse_palette /src/targets/bmp_parser/bmp_parser.c:33:16
SUMMARY: AddressSanitizer: stack-buffer-overflow in __asan_memcpy
"""

UBSAN_BOUNDS = """\
/src/targets/bmp_parser/bmp_parser.c:33:5: runtime error: index 256 out of \
bounds for type 'uint32_t[256]' (aka 'unsigned int[256]')
SUMMARY: UndefinedBehaviorSanitizer: undefined-behavior /src/x.c:33:5
"""

UNSYMBOLIZED = """\
==104==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x50f0000001d3
READ of size 16 at 0x50f0000001d3 thread T0
    #0 0xaaa  (/bin/bmp_fuzzer+0xffc35)
    #1 0xbbb  (/bin/bmp_fuzzer+0x1440aa)
SUMMARY: AddressSanitizer: heap-buffer-overflow (/bin/bmp_fuzzer+0xffc35)
"""


class TestClassify(unittest.TestCase):
    def test_heap_buffer_overflow_read(self):
        info = parse_sanitizer_output(HBO_READ, exit_code=1)
        self.assertEqual(info.bug_class, "heap-buffer-overflow")
        self.assertEqual(info.direction, "READ")
        self.assertEqual(info.access_size, 48)
        self.assertEqual(info.location.function, "copy_rows")
        self.assertEqual(info.location.line, 68)
        self.assertTrue(info.symbolized)
        self.assertEqual(info.severity, "medium")

    def test_use_after_free_write_is_high(self):
        info = parse_sanitizer_output(UAF_WRITE, exit_code=1)
        self.assertEqual(info.bug_class, "heap-use-after-free")
        self.assertEqual(info.direction, "WRITE")
        self.assertEqual(info.severity, "high")

    def test_segv_maps_to_taxonomy_with_direction(self):
        info = parse_sanitizer_output(SEGV_WRITE, exit_code=1)
        self.assertEqual(info.bug_class, "SEGV-unknown")
        self.assertEqual(info.raw_class, "SEGV")
        self.assertEqual(info.direction, "WRITE")
        self.assertEqual(info.location.function, "copy_rows")

    def test_stack_buffer_overflow(self):
        info = parse_sanitizer_output(STACK_ASAN, exit_code=1)
        self.assertEqual(info.bug_class, "stack-buffer-overflow")
        self.assertEqual(info.location.function, "parse_palette")

    def test_ubsan_bounds_normalizes_to_stack_overflow(self):
        info = parse_sanitizer_output(UBSAN_BOUNDS, exit_code=1)
        self.assertEqual(info.kind, "ubsan")
        self.assertEqual(info.bug_class, "stack-buffer-overflow")
        self.assertEqual(info.raw_class, "ubsan-index-oob")

    def test_unsymbolized_trace_detected(self):
        info = parse_sanitizer_output(UNSYMBOLIZED, exit_code=1)
        self.assertEqual(info.bug_class, "heap-buffer-overflow")
        self.assertFalse(info.symbolized)
        self.assertIsNone(info.location)

    def test_excerpt_is_deterministic(self):
        # PIDs and addresses vary per replay; the excerpt embedded in
        # reports must not contain them (report idempotency).
        info = parse_sanitizer_output(HBO_READ, exit_code=1)
        self.assertNotIn("==100==", info.excerpt)
        self.assertNotIn("0x508000000076", info.excerpt)
        self.assertIn("0xADDR", info.excerpt)
        self.assertIn("copy_rows", info.excerpt)

    def test_no_crash(self):
        info = parse_sanitizer_output("parsed ok\n", exit_code=0)
        self.assertEqual(info.kind, "no-crash")

    def test_timeout(self):
        info = parse_sanitizer_output("", exit_code=-9, timed_out=True)
        self.assertEqual(info.bug_class, "timeout")

    def test_unknown_crash(self):
        info = parse_sanitizer_output("garbage\n", exit_code=134)
        self.assertEqual(info.bug_class, "crash-unknown")


if __name__ == "__main__":
    unittest.main()
