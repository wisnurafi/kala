# Sanitizer profile: AddressSanitizer only.
# Use for: memory corruption hunting (heap/stack overflow, use-after-free).
# Included by the root CMakeLists when KALA_SANITIZER=asan; can also be
# included directly by a target subdirectory.
add_compile_options(-fsanitize=address -fno-omit-frame-pointer -g)
add_link_options(-fsanitize=address)
