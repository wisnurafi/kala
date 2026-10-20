# Setup

Goal: zero to first fuzzing run in under 30 minutes.

## 1. Linux environment

Primary: a Debian/Ubuntu VM (VMware / VirtualBox / Hyper-V). Run the VM
setup script once inside the VM — it installs clang, AFL++ (from source),
cmake, gdb + GEF, and Python + Pillow, then prints the `core_pattern`
reminder for AFL++ and the snapshot checklist.

Alternative: the Docker image in `docker/`.

Development (writing code) happens on Windows in VS Code; the only bridge
to the VM is git (or a shared folder — pick one and stick to it). Source
of truth is the repo, never a copy edited inside the VM.

## 2. Build the hello-world fuzzer

```sh
cmake -S . -B build-fuzzer \
  -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
  -DKALA_SANITIZER=asan-ubsan -DKALA_ENABLE_LIBFUZZER=ON
cmake --build build-fuzzer -j
```

## 3. First fuzzing run

```sh
mkdir -p findings-hello
./build-fuzzer/harness/libfuzzer/hello_fuzzer findings-hello corpus/hello \
  -dict=harness/dicts/hello.dict -max_total_time=60
```

Done when: a `crash-*` artifact appears in `findings-hello/` in under 60
seconds and its log shows an ASan `heap-buffer-overflow` in
`kala_hello_parse`.

## 4. Portability check

```sh
grep -rn "windows.h" --include="*.c" --include="*.h" \
  --include="*.cpp" --include="*.hpp" .
# must print nothing
```
