#include <cstddef>
#include <cstdint>

#include "hello_parse.h"

// libFuzzer entry point for the hello-world smoke-test target.
// Build: clang++ -fsanitize=fuzzer,address (see README / root CMake).
extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  // Guard: cap input size so one pathological input cannot stall the
  // campaign, and hand everything else to the dummy parser.
  if (size > 4096) {
    return 0;
  }
  kala_hello_parse(data, size);
  return 0;
}
