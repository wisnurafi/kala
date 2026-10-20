#include <cstddef>
#include <cstdint>
#include <vector>

#include "tomlc17.h"

// libFuzzer harness for tomlc17 (Phase 5 public target,
// targets/tomlc17). The library is built with
// -fsanitize=fuzzer-no-link and upstream default options.
//
// toml_parse() is length-based (src need not be NUL-terminated), so
// the fuzzer's bytes go in as-is; embedded NULs are data. On success
// the harness walks the whole result tree ITERATIVELY (explicit
// heap stack, no recursion of its own) folding types, keys and
// string bytes into a checksum, and runs two fixed toml_seek()
// lookups, so query-API code is exercised too. It stores nothing
// beyond the walk, so a crash here is in the library, never in
// harness bookkeeping. toml_free() is called on every result, as
// the API requires, success or failure.
namespace {

void FoldDatum(uint64_t *checksum, const toml_datum_t &datum) {
  *checksum = *checksum * 1315423911u + static_cast<uint64_t>(datum.type);
  *checksum = *checksum * 1315423911u + static_cast<uint32_t>(datum.lineno);
  if (datum.type == TOML_STRING && datum.u.str.ptr != nullptr) {
    for (int i = 0; i < datum.u.str.len; ++i) {
      *checksum = *checksum * 1315423911u +
                  static_cast<unsigned char>(datum.u.str.ptr[i]);
    }
  }
}

}  // namespace

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  if (size > (1u << 16)) {
    return 0;
  }
  toml_result_t result =
      toml_parse(reinterpret_cast<const char *>(data), static_cast<int>(size));
  if (result.ok) {
    uint64_t checksum = 0;
    std::vector<toml_datum_t> stack;
    stack.push_back(result.toptab);
    // The tree is finite (every node was allocated while parsing a
    // bounded input); the visit cap is a belt-and-braces guard so a
    // corrupt tree can never spin the harness itself forever.
    size_t visited = 0;
    while (!stack.empty() && visited < 100000) {
      toml_datum_t datum = stack.back();
      stack.pop_back();
      ++visited;
      FoldDatum(&checksum, datum);
      if (datum.type == TOML_TABLE) {
        for (int32_t i = 0; i < datum.u.tab.size; ++i) {
          if (datum.u.tab.key != nullptr && datum.u.tab.key[i] != nullptr) {
            for (int j = 0; j < datum.u.tab.len[i]; ++j) {
              checksum = checksum * 1315423911u +
                         static_cast<unsigned char>(datum.u.tab.key[i][j]);
            }
          }
          if (datum.u.tab.value != nullptr) {
            stack.push_back(datum.u.tab.value[i]);
          }
        }
      } else if (datum.type == TOML_ARRAY) {
        if (datum.u.arr.elem != nullptr) {
          for (int32_t i = 0; i < datum.u.arr.size; ++i) {
            stack.push_back(datum.u.arr.elem[i]);
          }
        }
      }
    }
    toml_datum_t probe = toml_seek(result.toptab, "a.b");
    FoldDatum(&checksum, probe);
    probe = toml_seek(result.toptab, "server.host");
    FoldDatum(&checksum, probe);
    (void)checksum;
  }
  toml_free(result);
  return 0;
}
