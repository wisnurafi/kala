# Sanitizer profile: AddressSanitizer + UndefinedBehaviorSanitizer.
# Use for: the default Kala campaign profile. ASan catches memory
# corruption; UBSan catches integer overflow and other undefined behaviour
# that ASan cannot see.
# Included by the root CMakeLists when KALA_SANITIZER=asan-ubsan.
add_compile_options(-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -g)
add_link_options(-fsanitize=address,undefined)
