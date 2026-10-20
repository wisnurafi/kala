# Docker environment

The VM is the primary test environment; this image is the lightweight,
identical-everywhere alternative (roadmap section 3.5).

```sh
docker build -t kala docker/
docker run --rm -it -v "$PWD":/kala -w /kala kala
```

Inside the container the quick-start from the root README works unchanged
(clang + libFuzzer are in the image). AFL++ is installed from source in
the VM setup script; adding it to this image is a follow-up once Phase 1
needs AFL++ side by side with libFuzzer.
