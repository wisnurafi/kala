add_library(bmp_parser STATIC bmp_parser.c)
target_include_directories(bmp_parser PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(bmp_dump bmp_dump.c)
target_link_libraries(bmp_dump PRIVATE bmp_parser)

if(KALA_ENABLE_LIBFUZZER)
  # Coverage instrumentation for the target code (see Fase 0 finding:
  # without fuzzer-no-link the engine gets no feedback from the parser).
  target_compile_options(bmp_parser PRIVATE -fsanitize=fuzzer-no-link)
  # The replay tool links the same instrumented library, so it needs
  # the coverage runtime symbols too.
  target_link_options(bmp_dump PRIVATE -fsanitize=fuzzer-no-link)
endif()
