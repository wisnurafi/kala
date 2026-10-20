add_library(tomlc17 STATIC tomlc17.c)
target_include_directories(tomlc17 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

# No Kala-side compile definitions: the target builds with upstream
# default options (see README.md) — the configuration most embedders
# get by dropping tomlc17.c/tomlc17.h into their tree.

if(KALA_ENABLE_LIBFUZZER)
  # Coverage instrumentation for the target code (Phase 0 finding:
  # without fuzzer-no-link the engine gets no feedback).
  target_compile_options(tomlc17 PRIVATE -fsanitize=fuzzer-no-link)
endif()
