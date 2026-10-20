#include "hello_parse.h"

#include <cstdlib>
#include <cstring>

int kala_hello_parse(const uint8_t *data, size_t size) {
  // Early exits: keep the fuzzer from wasting cycles on inputs that
  // cannot possibly reach the interesting path.
  if (data == nullptr || size < 4) {
    return 0;
  }

  // Magic gate, checked one byte at a time. Each comparison is its own
  // basic block, so coverage-guided fuzzing gets incremental feedback
  // for every correct byte and discovers the full pattern quickly.
  if (data[0] != 'F') {
    return 0;
  }
  if (data[1] != 'U') {
    return 0;
  }
  if (data[2] != 'Z') {
    return 0;
  }
  if (data[3] != 'Z') {
    return 0;
  }

  // PLANTED BUG (Phase 0 calibration only): heap-buffer-overflow.
  // A 4-byte heap buffer is written 16 bytes past its end. ASan must
  // report this as heap-buffer-overflow the moment the magic is found.
  char *buf = static_cast<char *>(std::malloc(4));
  if (buf == nullptr) {
    return 0;
  }
  std::memset(buf, 'A', 4);
  volatile char *overflow = buf + 16;
  *overflow = 'X';
  std::free(buf);
  return 1;
}
