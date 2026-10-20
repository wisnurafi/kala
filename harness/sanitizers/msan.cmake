# Sanitizer profile: MemorySanitizer (later phase, not used in Phase 0/1).
# Use for: uninitialized-memory reads. Requires clang on Linux and an
# instrumented standard library for low false-positive rates.
# Included by the root CMakeLists when KALA_SANITIZER=msan.
if(NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  message(FATAL_ERROR "MSan requires clang")
endif()
add_compile_options(-fsanitize=memory -fsanitize-memory-track-origins=2 -fno-omit-frame-pointer -g)
add_link_options(-fsanitize=memory)
