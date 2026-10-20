#pragma once

#include <cstddef>
#include <cstdint>

// Dummy parser for the hello-world smoke-test harness.
//
// Returns 0 for every input it rejects or handles cleanly. One specific
// magic pattern reaches an intentionally planted heap-buffer-overflow so
// the fuzzing loop can be calibrated end to end: fuzzer finds the pattern,
// ASan reports the bug, a crash artifact is written.
//
// This is a training target, not a real parser. The calibrated
// target is bmp_parser (5 planted bug classes).
int kala_hello_parse(const uint8_t *data, size_t size);
