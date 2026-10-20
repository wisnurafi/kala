add_library(kala_hello_parse STATIC hello_parse.cpp)
target_include_directories(kala_hello_parse PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

if(KALA_ENABLE_LIBFUZZER)
  # Target code gets coverage instrumentation (fuzzer-no-link) so the
  # fuzzer receives SanitizerCoverage feedback from inside the parser.
  # Without this the engine is effectively blind and finds bugs by brute
  # force instead of coverage guidance.
  target_compile_options(kala_hello_parse PRIVATE -fsanitize=fuzzer-no-link)
endif()

if(KALA_ENABLE_LIBFUZZER)
  if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    message(FATAL_ERROR "libFuzzer harnesses require clang (got ${CMAKE_CXX_COMPILER_ID})")
  endif()
  add_executable(hello_fuzzer hello_fuzzer.cpp)
  target_link_libraries(hello_fuzzer PRIVATE kala_hello_parse)
  target_compile_options(hello_fuzzer PRIVATE -fsanitize=fuzzer)
  target_link_options(hello_fuzzer PRIVATE -fsanitize=fuzzer)
endif()
