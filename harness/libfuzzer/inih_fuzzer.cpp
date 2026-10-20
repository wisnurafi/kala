#include <cstddef>
#include <cstdint>
#include <cstring>

#include "ini.h"

// libFuzzer harness for inih (first real target, targets/inih).
// The parser is built with -fsanitize=fuzzer-no-link and the heap
// line-buffer configuration (INI_USE_STACK=0, INI_ALLOW_REALLOC=1).
//
// ini_parse_string_length() is length-based, so the fuzzer's bytes
// go in as-is — no NUL-termination copy, embedded NULs are data.
// The handler deliberately stores nothing: it walks the full
// section/name/value strings (their lengths are part of what the
// parser computed) and folds them into a checksum, so a crash here
// is in the parser, never in harness bookkeeping.
namespace {

int Handler(void *user, const char *section, const char *name,
            const char *value) {
  auto *checksum = static_cast<uint64_t *>(user);
  const char *parts[3] = {section, name, value};
  for (const char *part : parts) {
    if (part == nullptr) {
      continue;
    }
    for (size_t i = 0; part[i] != '\0'; ++i) {
      *checksum = *checksum * 1315423911u +
                  static_cast<unsigned char>(part[i]);
    }
    *checksum += 1;
  }
  return 1;
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  if (size > (1u << 16)) {
    return 0;
  }
  uint64_t checksum = 0;
  ini_parse_string_length(reinterpret_cast<const char *>(data), size,
                          Handler, &checksum);
  return 0;
}
