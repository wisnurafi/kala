add_library(inih STATIC ini.c)
target_include_directories(inih PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

# Configuration pins (see README.md): the heap line-buffer path with
# realloc growth is the configuration under test — it is the one
# whose buffer management is interesting to a fuzzer. Upstream
# defaults are INI_USE_STACK=1 / INI_ALLOW_REALLOC=0.
target_compile_definitions(inih PRIVATE INI_USE_STACK=0 INI_ALLOW_REALLOC=1)

if(KALA_ENABLE_LIBFUZZER)
  # Coverage instrumentation for the target code (Phase 0 finding:
  # without fuzzer-no-link the engine gets no feedback).
  target_compile_options(inih PRIVATE -fsanitize=fuzzer-no-link)
endif()
