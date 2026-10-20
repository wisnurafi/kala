#include <cstddef>
#include <cstdint>

#include "bmp_parser.h"

// libFuzzer harness for the Phase 1 calibration target (bmp_parser).
// The parser is built with -fsanitize=fuzzer-no-link (see
// targets/bmp_parser/CMakeLists.txt) so coverage feedback comes from
// inside the parser, per the Phase 0 finding.
extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  if (size > (1u << 20)) {
    return 0;
  }
  BmpImage img;
  if (bmp_parse(data, size, &img) == 0) {
    bmp_image_free(&img);
  }
  return 0;
}
