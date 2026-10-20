cmake_minimum_required(VERSION 3.20)
project(Kala LANGUAGES C CXX)

# Cross-platform rules (roadmap section 9): standard C11 / C++17 only,
# no compiler extensions, no platform-specific APIs.
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE RelWithDebInfo CACHE STRING "Build type" FORCE)
endif()

# --- Sanitizer profile -------------------------------------------------------
# KALA_SANITIZER: none | asan | asan-ubsan | msan
# The same profiles live as includable modules in harness/sanitizers/ so a
# single target can opt in without reconfiguring the whole tree.
set(KALA_SANITIZER "none" CACHE STRING "Sanitizer profile: none, asan, asan-ubsan, msan")
set_property(CACHE KALA_SANITIZER PROPERTY STRINGS none asan asan-ubsan msan)

set(KALA_SANITIZER_FILE "")
if(KALA_SANITIZER STREQUAL "asan")
  set(KALA_SANITIZER_FILE "asan.cmake")
elseif(KALA_SANITIZER STREQUAL "asan-ubsan")
  set(KALA_SANITIZER_FILE "asan_ubsan.cmake")
elseif(KALA_SANITIZER STREQUAL "msan")
  set(KALA_SANITIZER_FILE "msan.cmake")
elseif(NOT KALA_SANITIZER STREQUAL "none")
  message(FATAL_ERROR "Unknown KALA_SANITIZER='${KALA_SANITIZER}' (expected: none, asan, asan-ubsan, msan)")
endif()

if(KALA_SANITIZER_FILE)
  include("${CMAKE_CURRENT_SOURCE_DIR}/harness/sanitizers/${KALA_SANITIZER_FILE}")
endif()

# --- libFuzzer ---------------------------------------------------------------
option(KALA_ENABLE_LIBFUZZER "Build libFuzzer harnesses (requires clang)" OFF)

add_compile_options(-Wall -Wextra)

add_subdirectory(harness/libfuzzer)
